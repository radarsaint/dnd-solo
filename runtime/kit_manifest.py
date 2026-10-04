"""Three-layer one-pass packets (plan update #3, PR2): SessionManifest, RoomManifest, TurnDelta.

The live host is one long chat that keeps earlier tool output in context (see
docs/architecture/MANIFESTS.md). Re-sending ~53 KB of unchanged instructions, schema and
personality core every turn makes the packet slow to read and fills the chat until it is cut.
So the packet is split by how often each part changes, stable material first, so the
unchanged prefix can be cached:

* ``session_manifest``: the core, the instructions (invariants) and the output contract
  (schema, limits, retry note). Changes only if the code or the voice files change.
* ``room_manifest``: the room's static DM truth for the scene (source ids, constraints,
  dm_only, missing layers). Changes when the room or area does.
* the turn delta: everything else, i.e. what this turn is (the move, the event, attitudes,
  positions, reveal status, story pressure, memory, history).

Each manifest is content-hashed. Once the host has been sent a manifest's body, later packets
carry only ``{'hash': h, 'cached': True}``. Kit echoes both hashes with her output
(``manifest``: {session, room}); a missing or wrong echo is refused with a pointer to
``rehydrate``, which returns the full bodies, so a lost copy costs one retry, not a bad turn.
Nothing is trimmed: ``join(split(packet))`` is the full packet, byte for byte.
"""
import copy
import hashlib
import json

from .state_context import InvalidChange, encode, require

SESSION_KEYS = ('performance_variant', 'instructions', 'schema', 'performance_limits', 'host_retry')
SESSION_PRIVATE_KEYS = ('personality_core',)
ROOM_DM_KEYS = ('source_id', 'source_ref', 'map_ref', 'fixture_only', 'level_context', 'campaign_context',
                'constraints', 'dm_only', 'missing_production_layers')
FULL_EVERY = 8               # re-send both bodies at least every 8 prepared turns
REJECT_STREAK = 2            # and after a turn with this many rejections
MANIFEST_RULE = ('session_manifest and room_manifest hold this session\'s core, instructions, output '
                 'contract and the room\'s static truth. "cached": true means unchanged since you were '
                 'sent the body; use that copy. Echo both hashes with your output as "manifest": '
                 '{"session": ..., "room": ...}. If you no longer have a body, do not guess: run rehydrate '
                 'for this turn_id (CLI: rehydrate --turn-id T) and you get both in full.')


class ManifestMismatch(InvalidChange):
    """The output did not echo the manifest hashes of the packet it answers."""


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()[:16]


def split(packet):
    """(session body, room body, delta) of a full one-pass packet. The delta keeps the
    packet's key order with the manifest parts removed."""
    delta = copy.deepcopy(packet)
    private = delta['input']['private']
    session = {key: delta.pop(key) for key in SESSION_KEYS if key in delta}
    session.update({key: private.pop(key) for key in SESSION_PRIVATE_KEYS if key in private})
    dm = private.get('dm_context') or {}
    room = {key: dm.pop(key) for key in ROOM_DM_KEYS if key in dm}
    return session, room, delta


def join(session, room, delta):
    """The full packet again (key order aside), for tests and for a host that rehydrates."""
    packet = copy.deepcopy(delta)
    for key in ('session_manifest', 'room_manifest', 'manifest_rule'):
        packet.pop(key, None)
    packet.update({key: session[key] for key in SESSION_KEYS if key in session})
    private = packet['input']['private']
    private.update({key: session[key] for key in SESSION_PRIVATE_KEYS if key in session})
    if 'dm_context' in private:
        private['dm_context'].update(room)
    return packet


def layered(packet, cached_session=False, cached_room=False):
    """The packet as three layers, stable first. Returns (layered packet, hashes, room body)."""
    session, room, delta = split(packet)
    hashes = {'session': digest(session), 'room': digest(room)}
    out = {'session_manifest': {'hash': hashes['session'], **({'cached': True} if cached_session else {'body': session})},
           'room_manifest': {'hash': hashes['room'], **({'cached': True} if cached_room else {'body': room})},
           'manifest_rule': MANIFEST_RULE, **delta}
    return out, hashes, room


def plan_sends(recent):
    """Which bodies the host already holds: hashes sent in full within the last FULL_EVERY
    prepared turns, unless a turn since then hit the rejection streak."""
    held = {'session': set(), 'room': set()}
    for row in list(recent)[-FULL_EVERY:]:
        record = row.get('manifest') or {}
        rejected = sum(1 for a in row.get('attempts') or () if a.get('outcome') == 'rejected')
        if rejected >= REJECT_STREAK:
            held = {'session': set(), 'room': set()}
            continue
        for layer in ('session', 'room'):
            if layer in (record.get('sent') or ()):
                held[layer].add(record[layer])
    return held


def check_echo(output, record):
    """A layered turn's output echoes the hashes it was sent."""
    if not record:
        return
    echo = output.get('manifest')
    expected = {'session': record['session'], 'room': record['room']}
    if echo != expected:
        raise ManifestMismatch(
            f'manifest echo {json.dumps(echo)} does not match this turn\'s manifests '
            f'{json.dumps(expected)}. If you lost a manifest body, run rehydrate for this turn_id '
            '(CLI: rehydrate --turn-id T), then resubmit the same output with "manifest" set to these hashes.')

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
carry only ``{'hash': h, 'cached': True}``. Every body and room diff carries a short random
nonce; Kit echoes the nonces of the copies she holds in the private ``manifest.check`` of her
output. A missing or wrong nonce is refused with a pointer to ``rehydrate``, which returns only
the layers she lacks, so a lost or stale copy costs one retry, not a bad turn.
Nothing is trimmed: ``join(split(packet))`` is the full packet, byte for byte.
"""
import copy
import hashlib
import json
import re
import secrets

from .state_context import InvalidChange, encode, require

SESSION_KEYS = ('performance_variant', 'instructions', 'schema', 'performance_limits', 'host_retry')
SESSION_PRIVATE_KEYS = ('personality_core',)
ROOM_DM_KEYS = ('source_id', 'source_ref', 'map_ref', 'fixture_only', 'level_context', 'campaign_context',
                'constraints', 'dm_only', 'missing_production_layers')
LAYERS = ('session', 'room')
NONCE_HEX = 6                # a nonce: one digit, then 6 hex characters ("3f09a2c"); never an English word
CHECK_MATCH = 0.6            # an echo passes when this share of the expected words is in it, in any order
MANIFEST_RULE = ('session_manifest and room_manifest hold this session\'s core, instructions, output '
                 'contract and the room\'s static truth. "cached": true means unchanged since you were '
                 'sent the body; use that copy. "diff" means the room changed: apply it to the copy whose hash '
                 'is "base" (each entry sets "value" at "path", or removes "path") and use the result. Answer '
                 'manifest_check in "manifest" with your output. If you no longer have a body, do not guess: run '
                 'rehydrate for this turn_id (CLI: rehydrate --turn-id T); you get the layers you lack in full.')
CHECK_RULE = ('Manifest check (every turn): each manifest body or room diff you are sent carries a "nonce". '
              'Add "check": {"session": <the nonce of your session_manifest copy>, "room": <the nonce of your '
              'room_manifest copy, the latest diff\'s if you applied one>} inside "manifest". It is private: '
              'never say a nonce, a hash or this check aloud. If you do not have a copy, do not guess: run '
              'rehydrate for this turn_id first.')
CHECK_LINES = {'session': 'the nonce of your session_manifest copy',
               'room': 'the nonce of your room_manifest copy (the latest diff\'s, if you applied one)'}

WORD = re.compile(r"[a-z0-9']+")
WORD_ANY_CASE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


class ManifestMismatch(InvalidChange):
    """The output did not echo the manifest hashes or nonces of the packet it answers.
    ``layers``: the layers whose copy the host does not hold (re-sent on the next turn)."""

    def __init__(self, message, layers=LAYERS):
        super().__init__(message)
        self.layers = tuple(layers)


def new_nonce():
    """A short random nonce for a layer or diff just sent. It starts with a digit so it can
    never be an English word in spoken (the spoken guard refuses any nonce)."""
    return str(secrets.randbelow(10)) + secrets.token_hex(NONCE_HEX // 2)


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


def layered(packet, cached_session=False, cached_room=False, room_base=None, nonces=None):
    """The packet as three layers, stable first. Returns (layered packet, hashes, room body).
    ``room_base``: (hash, body) of the room copy the host holds; a changed room is then sent
    as a diff against it when that is smaller than the body. ``nonces``: {layer: nonce} put on
    each layer whose body or diff goes out (a cached layer carries none)."""
    session, room, delta = split(packet)
    nonces = nonces or {}
    hashes = {'session': digest(session), 'room': digest(room)}
    tag = lambda layer: {'nonce': nonces[layer]} if nonces.get(layer) else {}
    room_layer = {'hash': hashes['room'], **({'cached': True} if cached_room else {**tag('room'), 'body': room})}
    if not cached_room and room_base is not None:
        entries = diff(room_base[1], room)
        if len(encode(entries)) < len(encode(room)):
            room_layer = {'hash': hashes['room'], 'base': room_base[0], **tag('room'), 'diff': entries}
    session_layer = {'hash': hashes['session'],
                     **({'cached': True} if cached_session else {**tag('session'), 'body': session})}
    out = {'session_manifest': session_layer, 'room_manifest': room_layer, 'manifest_rule': MANIFEST_RULE, **delta}
    return out, hashes, room


def diff(old, new, path=()):
    """Entries that turn ``old`` into ``new``: [{'path': [...], 'value': v}] sets a key,
    [{'path': [...], 'remove': True}] drops one. Dicts are compared key by key; anything else
    that changed is replaced whole."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in old:
            if key not in new:
                out.append({'path': [*path, key], 'remove': True})
        for key, value in new.items():
            if key not in old:
                out.append({'path': [*path, key], 'value': value})
            elif old[key] != value:
                out.extend(diff(old[key], value, (*path, key)))
        return out
    return [] if old == new else [{'path': list(path), 'value': new}]


def apply_diff(base, entries):
    """``base`` with ``entries`` applied (a copy; ``base`` is unchanged)."""
    out = copy.deepcopy(base)
    for entry in entries:
        path = entry['path']
        require(bool(path), 'A manifest diff entry needs a path')
        node = out
        for key in path[:-1]:
            node = node.setdefault(key, {})
        if entry.get('remove'):
            node.pop(path[-1], None)
        else:
            node[path[-1]] = copy.deepcopy(entry['value'])
    return out


def held_by_host(previous):
    """What the host holds before this turn: {layer: (hash, nonce) or None}. The latest layered
    turn's record says which bodies the host had after reading that packet and their nonces; a
    layer it missed (wrong or missing nonce) is not held, and is re-sent alone."""
    if not previous:
        return {layer: None for layer in LAYERS}
    missed = set(previous.get('miss') or ())
    if previous.get('cache_miss'):   # a record from before the nonce check: both layers
        missed |= set(LAYERS)
    held = previous.get('held') or {}
    nonces = previous.get('nonce') or {}
    return {layer: (held[layer], nonces[layer]) if held.get(layer) and nonces.get(layer) and layer not in missed
            else None for layer in LAYERS}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _check_passes(answer, expected):
    """Lenient: the share of ``expected`` words found anywhere in ``answer`` (case, punctuation,
    order and extra words ignored) is at least CHECK_MATCH. A one-word nonce must be there."""
    found = set(WORD.findall(str(answer or '').casefold()))
    expected = [word.casefold() for word in expected]
    if not expected:
        return True
    return sum(1 for word in expected if word in found) >= max(1, round(CHECK_MATCH * len(expected) + 1e-9))


def internals(record):
    """Strings that must never appear in spoken: this turn's hashes and nonces and the check's lines."""
    out = [record.get(layer) for layer in LAYERS] + list((record.get('nonce') or {}).values())
    out += list(CHECK_LINES.values()) + ['manifest_check', 'session_manifest', 'room_manifest']
    return [item for item in out if item]


def check_spoken(texts, record):
    """Refuse spoken that carries a manifest hash, a nonce or the check (p99 leak probe)."""
    if not record:
        return
    said = ' '.join(texts).casefold()
    for item in internals(record):
        if re.search(r'(?<![0-9a-z])' + re.escape(item.casefold()) + r'(?![0-9a-z])', said):
            raise InvalidChange('Spoken carries manifest internals (a hash, a nonce or the manifest check). '
                                'They are private: keep them in "manifest" only and say nothing about them.')


def check_echo(output, record):
    """A layered turn's output echoes the hashes it was sent and the nonce of each copy it holds
    (manifest.check). Raises ManifestMismatch naming the layers to re-send."""
    if not record:
        return
    echo = output.get('manifest')
    echo = echo if isinstance(echo, dict) else {}
    expected = {'session': record['session'], 'room': record['room']}
    # The hashes are optional (a cached layer carries its own hash, so echoing it proves nothing);
    # if Kit gives them they must match. The nonces are the proof.
    got = {key: value for key, value in echo.items() if key in expected}
    if any(got[key] != expected[key] for key in got):
        raise ManifestMismatch(
            f'manifest echo {json.dumps(got)} does not match this turn\'s manifests '
            f'{json.dumps(expected)}. If you lost a manifest body, run rehydrate for this turn_id '
            '(CLI: rehydrate --turn-id T), then resubmit the same output with "manifest" set to these hashes.')
    wanted = record.get('nonce') or {}
    if not wanted:
        return            # a record from before the nonce check
    answers = echo.get('check') if isinstance(echo.get('check'), dict) else {}
    failed = [layer for layer in LAYERS if layer in wanted and not _check_passes(answers.get(layer), [wanted[layer]])]
    if failed:
        raise ManifestMismatch(
            f'manifest check failed for {" and ".join(failed)}: that is not the nonce of the copy you were sent '
            'last, so the copy was lost, trimmed or not updated. Run rehydrate for this turn_id (CLI: rehydrate '
            '--turn-id T); you get only those layers, with a new nonce. Then write this turn again from them.',
            failed)

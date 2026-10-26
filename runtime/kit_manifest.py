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
import re

from .state_context import InvalidChange, encode, require

SESSION_KEYS = ('performance_variant', 'instructions', 'schema', 'performance_limits', 'host_retry')
SESSION_PRIVATE_KEYS = ('personality_core', 'available_reactions')
ROOM_DM_KEYS = ('source_id', 'source_ref', 'map_ref', 'fixture_only', 'level_context', 'campaign_context',
                'constraints', 'dm_only', 'missing_production_layers')
FULL_EVERY = 8               # re-send both bodies at least every 8 prepared turns
REJECT_STREAK = 2            # after this many rejections the next packet gets rejection_notice
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
    session = compact_session(session)
    dm = private.get('dm_context') or {}
    room = {key: dm.pop(key) for key in ROOM_DM_KEYS if key in dm}
    return session, room, delta


def join(session, room, delta):
    """The full packet again (key order aside), for tests and for a host that rehydrates."""
    packet = copy.deepcopy(delta)
    for key in ('session_manifest', 'room_manifest', 'manifest_rule'):
        packet.pop(key, None)
    session = expand_session(session)
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
    prepared turns. A rejection streak no longer clears them: the host still holds the body,
    so re-sending ~50 KB after every bad turn only made the retry slower. See rejection_notice;
    a host or model that really lost the body runs rehydrate."""
    held = {'session': set(), 'room': set()}
    for row in list(recent)[-FULL_EVERY:]:
        record = row.get('manifest') or {}
        for layer in ('session', 'room'):
            if layer in (record.get('sent') or ()):
                held[layer].add(record[layer])
    return held


def rejection_notice(recent, session_hash):
    """After a prepared turn that hit REJECT_STREAK rejections, the next packet carries the
    last rejection reasons and the session hash to re-read, not the full body again.
    None when the latest prepared turn had no streak."""
    rows = list(recent)
    if not rows:
        return None
    attempts = [a for a in rows[-1].get('attempts') or () if a.get('outcome') == 'rejected']
    if len(attempts) < REJECT_STREAK:
        return None
    reasons = _distinct_reasons(a.get('reason') for a in attempts)
    return {'rejections': len(attempts), 'reasons': reasons, 'session_hash': session_hash,
            'note': ('Your last turn needed several tries before it went through. Before you write '
                     'this decision, check it against every reason below so the same thing is not '
                     'refused again, using the session_manifest you already hold (same hash). If '
                     'you no longer have that body, run rehydrate for this turn_id (CLI: rehydrate '
                     '--turn-id T) instead of guessing.')}


# Host boilerplate the engine appends to many refusals; the notice keeps it once, not per reason.
# The engine's standing advice appended to a reason (resubmit, degraded mode, abandon) is not
# a reason. The degraded and abandon paragraphs also match when an older record cut them short.
_BOILERPLATE = re.compile(r'\s*(?:No turn was committed\.|Resubmit[^.]*\.|Revise[^.]*and resubmit\.|'
                          r'Degraded mode is available for this turn\..*?(?:still checked\.|$)|'
                          r'This turn keeps failing\..*?(?:simpler decision\.|$))\s*', re.S)


def strip_boilerplate(reason):
    """A rejection reason without the engine's standing advice, ready to be stored or cut."""
    return _BOILERPLATE.sub(' ', str(reason or '')).strip()


def _distinct_reasons(raw):
    """Every rejection reason, in order, without repeats or repeated boilerplate."""
    out = []
    for reason in raw:
        if not reason:
            continue
        text = strip_boilerplate(reason)
        if text and text not in out:
            out.append(text)
    return out


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


# Compact output contract (latency PR): the one-pass JSON Schema is ~9.5 KB, most of it
# boilerplate ("type": "string", "additionalProperties": false, a "required" list repeating
# every key). The session manifest carries this lossless shorthand instead; expand_schema
# turns it back into the exact JSON Schema (tests/test_kit_latency.py checks the round trip).
SCHEMA_NOTATION = ('schema shorthand: "string" "integer" "boolean" "number" are those types; '
                   '"string(a..b)" has that length range (either end may be empty); "enum:x|y" is one of '
                   'those strings, "int:0|1" one of those integers; [T] is an array of T; an object '
                   'lists its keys, every key required unless it ends in "?", no other keys allowed; '
                   '"//" is a note; {"$raw": ...} is plain JSON Schema.')
_SCALARS = ('string', 'integer', 'boolean', 'number')


def compact_schema(node):
    keys = set(node)
    kind = node.get('type')
    if keys == {'type'} and kind in _SCALARS:
        return kind
    if keys == {'type', 'enum'} and kind == 'string' and all(
            isinstance(v, str) and '|' not in v and v for v in node['enum']):
        return 'enum:' + '|'.join(node['enum'])
    if keys == {'type', 'enum'} and kind == 'integer' and all(
            isinstance(v, int) and not isinstance(v, bool) for v in node['enum']):
        return 'int:' + '|'.join(str(v) for v in node['enum'])
    if kind == 'string' and keys - {'type'} and keys <= {'type', 'minLength', 'maxLength'}:
        return f"string({node.get('minLength', '')}..{node.get('maxLength', '')})"
    if keys == {'type', 'items'} and kind == 'array':
        return [compact_schema(node['items'])]
    if (kind == 'object' and node.get('additionalProperties') is False and 'properties' in node
            and keys <= {'type', 'additionalProperties', 'properties', 'required', 'description'}
            and not any(name.endswith('?') or name.startswith('$') or name == '//'
                        for name in node['properties'])):
        names = list(node['properties'])
        required = node.get('required')
        in_order = [name for name in names if name in (required or ())]
        if required is not None and list(required) != in_order:
            return {'$raw': node}
        out = {}
        if 'description' in node:
            out['//'] = node['description']
        for name in names:
            optional = required is None or name not in required
            out[name + ('?' if optional else '')] = compact_schema(node['properties'][name])
        if required is None:
            out['$no_required'] = True
        return out
    return {'$raw': node}


def expand_schema(node):
    if isinstance(node, list):
        return {'type': 'array', 'items': expand_schema(node[0])}
    if isinstance(node, str):
        if node in _SCALARS:
            return {'type': node}
        if node.startswith('enum:'):
            return {'type': 'string', 'enum': node[5:].split('|')}
        if node.startswith('int:'):
            return {'type': 'integer', 'enum': [int(v) for v in node[4:].split('|')]}
        low, high = node[len('string('):-1].split('..')
        out = {'type': 'string'}
        if low:
            out['minLength'] = int(low)
        if high:
            out['maxLength'] = int(high)
        return out
    if '$raw' in node:
        return node['$raw']
    out = {'type': 'object', 'additionalProperties': False, 'properties': {}}
    required = []
    for name, child in node.items():
        if name in ('//', '$no_required'):
            continue
        bare = name[:-1] if name.endswith('?') else name
        out['properties'][bare] = expand_schema(child)
        if not name.endswith('?'):
            required.append(bare)
    if not node.get('$no_required'):
        out['required'] = required
    if '//' in node:
        out['description'] = node['//']
    return out


def compact_session(session):
    """The session body as sent: the schema in shorthand, with the notation beside it."""
    if isinstance(session.get('schema'), dict) and 'schema_notation' not in session:
        session = dict(session, schema=compact_schema(session['schema']), schema_notation=SCHEMA_NOTATION)
    return session


def expand_session(session):
    if 'schema_notation' in session:
        session = {key: value for key, value in session.items() if key != 'schema_notation'}
        session['schema'] = expand_schema(session['schema'])
    return session

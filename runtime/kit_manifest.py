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
SESSION_PRIVATE_KEYS = ('personality_core',)
ROOM_DM_KEYS = ('source_id', 'source_ref', 'map_ref', 'fixture_only', 'level_context', 'campaign_context',
                'constraints', 'dm_only', 'missing_production_layers')
CHECK_EVERY = 4              # a manifest check at least every 4 layered turns (never a full re-send)
REJECT_STREAK = 2            # and on the turn after one with this many rejections
CHECK_PROMPT_WORDS = 6       # the check quotes this many words of a line from the body...
CHECK_WORDS = 8              # ...and Kit writes the next this many words from her copy
CHECK_PASS = 6               # of which this many must match, in place
MANIFEST_RULE = ('session_manifest and room_manifest hold this session\'s core, instructions, output '
                 'contract and the room\'s static truth. "cached": true means unchanged since you were '
                 'sent the body; use that copy. "diff" means the room changed: apply it to the copy whose hash '
                 'is "base" (each entry sets "value" at "path", or removes "path") and use the result. Echo both '
                 'hashes with your output as "manifest": {"session": ..., "room": ...}. If you no longer have a '
                 'body, do not guess: run rehydrate for this turn_id (CLI: rehydrate --turn-id T) and you get '
                 'both in full.')
CHECK_RULE = ('Manifest check: each line below is the start of a sentence in your copy of a manifest body '
              '("instructions" and "core" in session_manifest, "room" in room_manifest). Add "check": {<same '
              f'keys>: "<the next {CHECK_WORDS} words, copied from that body>"}} inside "manifest". If you cannot '
              'find a line, do not guess: run rehydrate for this turn_id first.')


WORD = re.compile(r"[a-z0-9']+")
WORD_ANY_CASE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


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


def layered(packet, cached_session=False, cached_room=False, room_base=None):
    """The packet as three layers, stable first. Returns (layered packet, hashes, room body).
    ``room_base``: (hash, body) of the room copy the host holds; a changed room is then sent
    as a diff against it when that is smaller than the body."""
    session, room, delta = split(packet)
    hashes = {'session': digest(session), 'room': digest(room)}
    room_layer = {'hash': hashes['room'], **({'cached': True} if cached_room else {'body': room})}
    if not cached_room and room_base is not None:
        entries = diff(room_base[1], room)
        if len(encode(entries)) < len(encode(room)):
            room_layer = {'hash': hashes['room'], 'base': room_base[0], 'diff': entries}
    out = {'session_manifest': {'hash': hashes['session'], **({'cached': True} if cached_session else {'body': session})},
           'room_manifest': room_layer, 'manifest_rule': MANIFEST_RULE, **delta}
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
    """What the host holds before this turn: the latest layered turn's record says which bodies
    it had after reading that packet. A cache miss on it (wrong or missing echo, a failed check)
    means nothing is held."""
    if not previous or previous.get('cache_miss'):
        return {'session': None, 'room': None}
    held = previous.get('held')
    if held is None:  # a record from before PR-T: only what that turn sent
        held = {layer: previous[layer] if layer in (previous.get('sent') or ()) else None
                for layer in ('session', 'room')}
    return dict(held)


def check_due(previous, rejected):
    """A manifest check is due every CHECK_EVERY layered turns since the last full session send
    or the last check, again if the last check never committed, and after a rejection streak."""
    if not previous or previous.get('cache_miss'):
        return False      # this turn re-sends the bodies anyway
    if previous.get('check') and not previous.get('check_passed'):
        return True
    return rejected >= REJECT_STREAK or previous.get('since_check', 0) + 1 >= CHECK_EVERY


def _sentences(text):
    """(words, original opening) for each long enough sentence: the opening is the sentence's
    own text up to its CHECK_PROMPT_WORDS-th word, so Kit can find it by eye."""
    for part in re.split(r'(?<=[.!?:])\s+|\n+', text or ''):
        spans = list(WORD_ANY_CASE.finditer(part))
        if len(spans) >= CHECK_PROMPT_WORDS + CHECK_WORDS:
            yield [m.group(0).casefold() for m in spans], part[spans[0].start():spans[CHECK_PROMPT_WORDS - 1].end()]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def check_lines(session, room, delta, seed):
    """One line to continue from each of the instructions, the core and the room: the first
    CHECK_PROMPT_WORDS words of a sentence whose continuation the delta does not carry (so only a
    host holding the body can answer). Returns ({key: prompt}, {key: expected words})."""
    seen = ' ' + ' '.join(WORD.findall(encode(delta).casefold())) + ' '
    sources = {'instructions': [session.get('instructions') or ''],
               'core': [session.get('personality_core') or ''],
               'room': list(_strings(room))}
    layer_text = {'session': ' ' + ' '.join(WORD.findall(' '.join(_strings(session)).casefold())) + ' ',
                  'room': ' ' + ' '.join(WORD.findall(' '.join(_strings(room)).casefold())) + ' '}
    lines, expected = {}, {}
    for key, texts in sources.items():
        pool = [(found, opening) for text in texts for found, opening in _sentences(text)
                if ' ' + ' '.join(found[:CHECK_PROMPT_WORDS + CHECK_WORDS]) + ' ' not in seen]
        # The prompt must point at one place in the body, or the answer is ambiguous.
        body = layer_text['room' if key == 'room' else 'session']
        pool = [(found, opening) for found, opening in pool
                if body.count(' ' + ' '.join(found[:CHECK_PROMPT_WORDS]) + ' ') == 1]
        if not pool:
            continue
        found, opening = pool[int(hashlib.sha256(f'{seed}:{key}'.encode()).hexdigest(), 16) % len(pool)]
        lines[key] = opening
        expected[key] = found[CHECK_PROMPT_WORDS:CHECK_PROMPT_WORDS + CHECK_WORDS]
    return lines, expected


def _check_passes(answer, expected):
    found = WORD.findall(str(answer or '').casefold())
    return sum(1 for a, b in zip(found, expected) if a == b) >= min(CHECK_PASS, len(expected))


def check_echo(output, record):
    """A layered turn's output echoes the hashes it was sent, and answers its manifest check."""
    if not record:
        return
    echo = output.get('manifest')
    expected = {'session': record['session'], 'room': record['room']}
    got = {key: value for key, value in echo.items() if key != 'check'} if isinstance(echo, dict) else echo
    if got != expected:
        raise ManifestMismatch(
            f'manifest echo {json.dumps(got)} does not match this turn\'s manifests '
            f'{json.dumps(expected)}. If you lost a manifest body, run rehydrate for this turn_id '
            '(CLI: rehydrate --turn-id T), then resubmit the same output with "manifest" set to these hashes.')
    wanted = record.get('check_expected') or {}
    answers = echo.get('check') if isinstance(echo.get('check'), dict) else {}
    failed = sorted(key for key, words in wanted.items() if not _check_passes(answers.get(key), words))
    if failed:
        raise ManifestMismatch(
            f'manifest check failed for {", ".join(failed)}: those words are not what your copy of the body '
            'says, so it was lost or trimmed. Run rehydrate for this turn_id (CLI: rehydrate --turn-id T), '
            'then write this turn again from the full bodies and answer the check from them.')

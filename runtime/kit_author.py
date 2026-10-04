"""Source-to-room authoring: Kit writes a room file from a keyed area's source text, the
engine checks it (docs/architecture/SOURCE_TO_ROOM.md).

No hand-written room files. When play nears a keyed area, the runtime builds an **authoring
packet**: that area's keyed text, its **source manifest** (the fidelity checklist a pluggable
extractor pulls from the text: creatures and counts, named NPCs, items, traps and hazards,
secrets, the numbers it states, the ways out it names; runtime/kit_extract.py), the level DM
layer's notes, its geometry, the room schema with its limits, and the hard rules. The host
model (Kit) returns one room JSON object. ``submit`` validates it: the authoring rules, the
fidelity diff against the manifest (runtime/kit_fidelity.py, source-agnostic), the room
loader's own checks with every compiler's problems collected, then a real mount probe. A
failure returns a **repair packet** with every error at once; one repair is allowed. A second
failure is a **fallback**: the PC still walks in; Kit improvises the area in persona from its
keyed text (a minimal stand-in room carries it dm_only), every such turn flagged
``authoring_fallback`` in the session DB and the handoff trace, and authoring is retried in
the background (``author_ahead``). A later good room replaces the fallback on the next entry.
A fallback belongs to one session (its id in the DB): a new session on the same --db starts
clean. Accepted rooms are cached beside the session DB (``<db>.authored/``) under the area id
plus a hash of what they were written from and the validator version; every mount
re-validates the file, so a hand-edited cache entry never mounts unchecked.

Area links: an area's ``room_link`` may be ``{"author": {"level": "01", "area": "17b"}}`` (and
an optional ``area`` in that room, default its ``starting_area``). Moving into it mounts the
accepted room, else the fallback stand-in; every prepare packet carries ``author_ahead`` for
every neighbour of the current area (two steps out from an approach).

No model calls, no API, no network. The book text is read from a local path
(``kit_source.source_text_path``) and never written into the repo.
"""
import argparse
import copy
import json
import re
import sqlite3
import sys
import tempfile
import warnings
from pathlib import Path

from . import kit_extract, kit_fidelity, kit_rooms, kit_source, srd_creatures

SCHEMA_VERSION = 'source-to-room/1'
VALIDATOR_VERSION = 'fidelity/2'  # part of every cache key: a stricter validator re-authors
MAX_ATTEMPTS = 2  # the first try and one repair
ROOM_MAX_BYTES = 16000
FALLBACK_TEXT_BYTES = 7000
FORBIDDEN_KEYS = {'code', 'script', 'eval', 'exec', 'python', 'function', 'lambda', 'import'}
# Story hook conditions any room may use (kit_brief has more, for procedures a room declares).
HOOK_CONDITIONS = ('fact_known', 'claim_learned', 'said', 'any', 'exposed', 'actor_damaged', 'attitude_at_most',
                   'since_noticed')
TRIGGER_RULE = (
    'Write every condition the keyed text sets off as data. Creatures that wake: a trigger {"on": {"disturb": '
    '<the handled fact>} or {"enter": <area>}, "actors": [...], "starts_combat": true, "reveal": <one public '
    'line>}, its actors "status": "hidden", "visible": false until it fires; a lurker gets "surprise": '
    '{"stealth": null}. A trap or hazard (damage the text prints): a traps entry (schema.traps). Looking at a '
    'feature never sets anything off; handling it (moving, opening, prying, taking what it holds) can. Never '
    'narrate an ambush or a trap the room file does not declare.')
PARTS_RULE = (
    'A feature with graspable parts or a held item must list them: "handling": {"nouns", "parts": [the claw, the '
    'lid, the hand...], "holds": "<fact id>"}, and the held item is its own fact (hidden allowed: "visible": '
    'false). Then "I pry the claw open" or "I take the orb from the claw" disturbs that feature and fires its '
    'trigger; the item comes into view when it is handled.')
LAYER_RULE = (
    'Progressive reveal: a visible fact may carry "layer": "obvious" (what the PC takes in at first look and '
    'decides on: who is here, the way on, what invites a decision) or "detail" (visible, held until the player '
    'looks there). The way on and the exits are always obvious, and so is a fact a trigger or a held item hangs '
    'on; leave "layer" out when unsure (the engine works it out from the room data).')
LAYERS = ('obvious', 'detail')
# Words that name a graspable part of a feature ("the basilisk's claw", "the coffin's lid").
PART_WORDS = ('claw', 'claws', 'talon', 'talons', 'hand', 'hands', 'fist', 'jaw', 'jaws', 'mouth', 'paw', 'paws',
              'foreleg', 'wing', 'lid', 'drawer', 'handle', 'hilt', 'strap', 'clasp', 'latch', 'chain', 'hook')
HELD_IN = re.compile(r"\b(?:in|inside|under|beneath|within|on|clutched in|clenched in|held in|gripped in|"
                     r"wears|wearing|holds|holding)\b")
HARD_RULES = [
    'Data only: one JSON object in the room format. No code, no prose outside fields, no comments but "_note".',
    'Fidelity: source_manifest is the checklist. Every creature it lists, with its count and its visibility; '
    'every named NPC; every item and treasure; every trap and hazard; every secret sentence; the numbers it '
    'states. Nothing it does not have: no invented creatures, items, exits, or numbers. Where the manifest '
    'cannot place something (one beast in two sentences, a creature that is really a named NPC), add '
    'source_claims: [{"quote": "<words copied from keyed_text>", "actors": [ids], "facts": [ids]}].',
    'Deception and true natures stay: a liar keeps her lie in public and the truth in her secrets and claims; '
    'a disguised or secret creature stays hidden or disguised until play reveals it.',
    "Numbers: DCs, hit points, damage dice and gp values only as the keyed text gives them. A stat block is "
    '{"srd": "<name>"} from schema.srd_creatures (it may restate "hp" or "ac" only with the text\'s own number), '
    "else the text's own stat block, else \"needs_stats\": true and no stat_block (never invent one).",
    'Geometry: ways out only to areas source_manifest.exits marks way (or sibling); with no geometry ledger every '
    'exit to another keyed area carries "uncertain": true. No secret door the text does not name. Area and exit '
    "names use the text's own words. Every area carries \"source_area\".",
    TRIGGER_RULE,
    'Nothing hidden reaches the player: no visible fact, handling line, exit name, label or go_text, tease, '
    'heard sound, visible actor, or area name may name a hidden creature or a secret. No DC, bonus or hit '
    'points in any player-visible text.',
    'Every alarm or escalation (bell, horn, shout for help) lists its responders on its fact: '
    '"alarm": {"responders": [{"who", "count", "stat_block"}], "arrives_in_rounds"}.',
    'The approach is tease-only: its tease says what is seen or heard from outside; nothing from inside that '
    'the PC could not sense from there.',
    "A hidden truth found by a check is a claim (claims.<thing>, ROOM_LOADER section 2), with the text's DC "
    "or none (the engine's default).",
    'Next areas: an outside area joined to a named way carries "room_link": {"author": {"level", "area"}} so '
    'the next room is authored on demand, not invented.',
    PARTS_RULE,
    LAYER_RULE,
]
ROOM_SCHEMA = {
    'format': 'docs/architecture/ROOM_LOADER.md section 2 (the loader refuses anything else)',
    'required': {'id': 'exactly room_id', 'source_ref': 'names the keyed area', 'starting_area': 'the approach',
                 'areas': '{id: {name, called, source_area, outside?, beyond?, arrival?, tease? (approach), room_link?}}',
                 'exits': '{id: {name, areas: [a, b], secret, labels: {a: text, b: text}, go_text?, uncertain?}}',
                 'facts': '{id: {area, text, visible, handling?: {nouns, parts?, look?, move?, enter?, handle?, '
                          'holds?}, alarm?, layer? (obvious|detail)}}',
                 'actors': '{id: {name, location, status (alive|hidden), visible, motive, knowledge, secrets, '
                           'stat_block? | needs_stats?, communication_profile? (optional), guards?, armed?}}'},
    'optional': ['story (about, purposes, hooks with by/primary/within_beats/delivered_when, endings)', 'claims',
                 'triggers', 'traps', 'source_claims', 'attitudes', 'leak_phrases', 'leak_keywords',
                 'public_performance', 'resources'],
    'hook_conditions': list(HOOK_CONDITIONS),
    'tease': {'text': 'what reaches the PC outside', 'points_to': 'a story hook id',
              'heard': [{'actor': '<actor id>', 'sound': 'what is heard'}]},
    'triggers': [{'id': 'unique', 'on': {'disturb': '<fact id with handling>'}, 'starts_combat': True,
                  'actors': ['<hidden actor ids>'], 'surprise': {'stealth': None}, 'reveal': '<public line, <=300 chars>'}],
    'traps': [{'id': 'unique', 'on': {'step|enter': '<area>', 'disturb|open': '<fact with handling>'},
               'feature': '<hidden fact id: what it is>',
               'effect': {'save': 'dex (or "check": "<skill>")', 'dc': "<the text's DC, or null with \"needs_dc\": true>",
                          'damage': [{'dice': 'XdY', 'type': '<type>'}], 'half_on_success': 'true|false',
                          'condition': '<optional>', 'attack': {'to_hit': "<optional: the text's bonus>"}},
               'detect': {'skill': 'perception', 'dc': '<text DC>'},
               'disarm': [{'method': 'thieves_tools|sleight_of_hand', 'dc': '<text DC>'},
                          {'method': 'jam', 'with': '<what the text says stops it>'},
                          {'method': 'break', 'object': {'material': 'wood|stone|iron|...',
                                                         'size': 'tiny|small|medium|large', 'resilient': 'true|false'}}],
               'reset': 'once|auto|manual', 'reveal': '<public line when it goes off>',
               'spotted': '<public line when noticed>'}],
    'srd_creatures': sorted(srd_creatures.CREATURES),
    'limits': {'room_bytes': ROOM_MAX_BYTES, 'dm_only_bytes': kit_rooms.DM_ONLY_ROOM_MAX_BYTES,
               'claims_here_bytes': kit_rooms.CLAIMS_HERE_MAX_BYTES, 'attempts': MAX_ATTEMPTS},
}
FALLBACK_NOTE = ('Authoring has not produced a valid room for this area yet. You run it in persona by improvising '
                 "from its keyed text (dm_only: the unrevealed facts). Describe only what the PC perceives; keep "
                 "its secrets; use the text's numbers; never say the room is not ready. The engine is retrying "
                 'the room in the background (author_ahead).')


class RoomNotAuthored(kit_rooms.RoomMountError):
    """An author link that cannot resolve at all (no book configured): a host problem."""

    def __init__(self, room, problems, authoring):
        super().__init__(room, problems)
        self.authoring = authoring

    def host_view(self):
        return {**super().host_view(), 'error': 'room_not_authored', 'authoring': self.authoring}


# ---------------------------------------------------------------- where things live

def session_dir(db):
    """The session's cache of authored rooms: next to its database, gitignored (*.authored/)."""
    return Path(str(db) + '.authored')


def session_id(db):
    """The play session's id (state_context.Runtime keeps it in the DB), or None before start."""
    if not db or str(db) == ':memory:' or not Path(db).is_file():
        return None
    try:
        con = sqlite3.connect(f'file:{Path(db).resolve()}?mode=ro', uri=True)
        try:
            row = con.execute("SELECT value FROM session_meta WHERE key='session_id'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def room_id(level, area):
    return f'authored-level-{kit_source.level_key(level)}-area-{area}'


def _command(verb, level, area, db=None):
    where = f' --db {db}' if db else ''
    tail = ' --input-file <room.json>' if verb == 'submit' else ''
    return f'python3 -m runtime.kit_author {verb}{where} --level {kit_source.level_key(level)} --area {area}{tail}'


# ---------------------------------------------------------------- the authoring packet

_BOOKS = {}


def book_from(directory, level):
    """The source a session authored this level from (its ``sources.json``), else the
    configured book."""
    path = Path(directory) / 'sources.json' if directory else None
    if path and path.is_file():
        origin = json.loads(path.read_text(encoding='utf-8')).get(kit_source.level_key(level))
        if origin:
            key = (kit_source.level_key(level), json.dumps(origin, sort_keys=True),
                   *(Path(p).stat().st_mtime if p and Path(p).is_file() else None for p in origin.values()))
            if key not in _BOOKS:
                _BOOKS[key] = Book(level, **origin)
            return _BOOKS[key]
    return book_for(level)


def book_for(level):
    """The configured book for a level, parsed once per source file version."""
    path = kit_source.source_text_path()
    stamp = path.stat().st_mtime if path and path.is_file() else None
    key = (kit_source.level_key(level), str(path), stamp)
    if key not in _BOOKS:
        _BOOKS[key] = Book(level)
    return _BOOKS[key]


class Book:
    """The configured book text, one level's keyed areas, its DM layer and geometry."""

    extractor = 'keyed_prose'  # how this source is written (runtime/kit_extract.py)

    def __init__(self, level, text=None, source=None, map_index=None, ledger=None):
        self.level = kit_source.level_key(level)
        self.binding = kit_source.level_binding(level, map_index)
        self.text = text if text is not None else kit_source.read_source(source)
        self.areas = kit_source.keyed_areas(self.text, self.binding['headings'])
        layer = self.binding.get('layer')
        layer_path = kit_source.ROOT / layer if layer else None
        self.layer_text = layer_path.read_text(encoding='utf-8') if layer_path and layer_path.is_file() else ''
        self.layer = layer
        self.ledger = ledger
        # Where this source came from, so a session can re-check its rooms against it later
        # (None for a text handed in directly: those rooms re-check against the configured book).
        self.origin = None if text is not None else {
            'source': str(Path(source).resolve()) if source else None,
            'map_index': str(Path(map_index).resolve()) if map_index else None,
            'ledger': str(Path(ledger).resolve()) if ledger else None}

    def area(self, key):
        key = str(key).strip().lower()
        if key not in self.areas:
            raise kit_source.SourceUnavailable(f'no keyed area {key!r} on level {self.level}')
        return self.areas[key]


def _strip_artifacts(lines):
    return [l for l in lines if l.strip() and l.strip() != 'View Player Version']


def area_inputs(book, key, extractor=None):
    """Everything the room is written from (and hashed for the cache), with its source
    manifest (runtime/kit_extract.py: the fidelity checklist the validator diffs against)."""
    area = book.area(key)
    parent = book.areas.get(area['parent']) if area['parent'] else None
    keyed = _strip_artifacts(area['lines'])
    intro = _strip_artifacts(parent['lines']) if parent else []
    own = [k for k in area_refs_in(intro + keyed)]
    found = {}
    for k in own:
        if k != area['key'] and k in book.areas and k != area['parent']:
            found[k] = {'area': k, 'quotes': kit_extract.naming_sentences(intro + keyed, k)}
            # Whether the other side names this area as a way counts too (its text stays out).
            found[k]['quotes'] += kit_extract.naming_sentences(_strip_artifacts(book.areas[k]['lines']), area['key'])
            found[k]['shown'] = len(kit_extract.naming_sentences(intro + keyed, k))
    # Back-references: an area whose text names this one is its neighbour too. Only whether
    # that sentence reads as a way (a door, a tunnel, flight) is kept; its text stays out.
    for k, other in book.areas.items():
        if k in (area['key'], area['parent']) or k in found:
            continue
        quotes = kit_extract.naming_sentences(_strip_artifacts(other['lines']), area['key'])
        if quotes:
            found[k] = {'area': k, 'quotes': quotes, 'back': True}
    for k in area['subareas'] + ([s for s in parent['subareas'] if s != area['key']] if parent else []):
        found.setdefault(k, {'area': k, 'quotes': []})['sibling'] = True
    for k, item in found.items():
        item['title'] = book.areas[k]['title']
    # The source decides its extractor (a book's keyed prose, or a design doc that carries its
    # own manifest); the checker only ever sees the manifest.
    extractor = extractor or area.get('extractor') or getattr(book, 'extractor', 'keyed_prose')
    manifest = kit_extract.extract({'key': area['key'], 'title': area['title'], 'lines': keyed, 'intro': intro,
                                    'neighbours': list(found.values()),
                                    **({'manifest': area['manifest']} if 'manifest' in area else {})}, extractor)
    for item in manifest['exits']:
        if item.get('back_reference') or not found[item['area']].get('shown', 0):
            item['quote'] = ''  # another area's text never enters this packet
    named = [{'area': k, 'title': item['title'], **{f: True for f in ('back', 'sibling') if item.get(f)}}
             for k, item in found.items()]
    return {
        'level': book.level, 'level_name': book.binding['name'],
        'area': {'key': area['key'], 'title': area['title'], 'keyed_text': keyed,
                 **({'parent': {'key': parent['key'], 'title': parent['title'], 'intro': intro}} if parent else {}),
                 **({'subareas': area['subareas']} if area['subareas'] else {})},
        'named_neighbours': named,
        'manifest': manifest,
        'level_notes': {'layer': book.layer, **kit_source.level_notes(book.layer_text, area, ' '.join(keyed))},
        'geometry': {'dm_map': book.binding.get('dm_map'),
                     'dm_map_present': bool(book.binding.get('dm_map')) and (kit_source.ROOT / book.binding['dm_map']).is_file(),
                     **kit_source.geometry(book.level, area['key'], book.ledger)},
    }


def area_refs_in(lines):
    return kit_source.area_refs(' '.join(lines))


def source_hash(inputs):
    return kit_source.fingerprint(SCHEMA_VERSION, VALIDATOR_VERSION, kit_extract.VERSION, inputs)


def checklist(manifest):
    """The manifest as Kit sees it in the packet: what the room must carry, quoted from this
    area's own text (sentences are referenced, not repeated)."""
    sentences = {s['id']: s for s in manifest['sentences']}
    out = {key: manifest[key] for key in ('creatures', 'npcs', 'items', 'hazards', 'scripted', 'numbers',
                                          'secret_ways') if manifest.get(key)}
    out['creatures_in_parent_intro'] = manifest.get('context_creatures') or []
    out['must_carry'] = [{'sentence': sid, 'secret': sentences[sid]['secret'],
                          **({'deception': True} if sentences[sid].get('deception') else {}),
                          'quote': sentences[sid]['text'][:140]} for sid in manifest['must_carry']]
    out['exits'] = [{k: v for k, v in e.items() if v not in ('', None, False) or k == 'way'}
                    for e in manifest['exits']]
    out['extractor'] = manifest.get('extractor')
    return out


def packet(book, key, db=None):
    """The authoring packet for one keyed area: only that area's text (and its parent's intro),
    never another area's."""
    inputs = area_inputs(book, key)
    digest = source_hash(inputs)
    public = {k: v for k, v in inputs.items() if k != 'manifest'}
    return {
        'stage': 'author_room', 'schema_version': SCHEMA_VERSION, 'validator': VALIDATOR_VERSION,
        'source_hash': digest[:16], 'room_id': room_id(book.level, inputs['area']['key']),
        'task': ('You are Kit, prepping this keyed area before the player walks in. Write the room file for it: '
                 'one JSON object in the room format below, from keyed_text, source_manifest, level_notes and '
                 'geometry only. Save it to a file and run the submit command. Say nothing at the table about '
                 'this step.'),
        **public,
        'source_manifest': checklist(inputs['manifest']),
        'schema': ROOM_SCHEMA,
        'hard_rules': HARD_RULES,
        'submit': _command('submit', book.level, inputs['area']['key'], db),
    }


# ---------------------------------------------------------------- validation

def _walk(value, path=''):
    if isinstance(value, dict):
        for k, v in value.items():
            yield path + str(k), k, v
            yield from _walk(v, f'{path}{k}.')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk(v, f'{path}{i}.')


CONDITION_LIST = re.compile(r'one condition of [a-z_, ]+')


def _generic(problem):
    """A compiler message in the authoring vocabulary (no procedure-only conditions)."""
    return CONDITION_LIST.sub('one condition of ' + ', '.join(HOOK_CONDITIONS), problem)


def authoring_problems(room, inputs):
    """What the authoring rules refuse, the fidelity diff included (the loader's own checks run
    alongside). (errors, warnings)."""
    if not isinstance(room, dict):
        return ['the room must be one JSON object'], []
    problems, warns = [], []
    size = len(json.dumps(room, ensure_ascii=False).encode())
    if size > ROOM_MAX_BYTES:
        problems.append(f'room is {size} bytes (limit {ROOM_MAX_BYTES}); keep it to what the keyed text gives')
    for path, key, value in _walk(room):
        if str(key).casefold() in FORBIDDEN_KEYS:
            problems.append(f'{path}: room files hold data only (no {key!r})')
        if isinstance(value, str) and re.match(r'\s*(def |import |lambda |<script|function\s*\()', value):
            problems.append(f'{path}: room files hold data only (that value reads as code)')
    if 'authoring' in room:
        problems.append('authoring is the engine\'s stamp on an accepted room: leave it out')
    area = inputs['area']
    want_id = room_id(inputs['level'], area['key'])
    if room.get('id') != want_id:
        problems.append(f'id must be {want_id!r}')
    if area['key'] not in str(room.get('source_ref', '')):
        problems.append(f"source_ref must name keyed area {area['key']}")
    allowed = {area['key']} | {n['area'] for n in inputs['named_neighbours']}
    parent = (area.get('parent') or {}).get('key')
    areas = room.get('areas') if isinstance(room.get('areas'), dict) else {}
    for key, item in areas.items():
        if not isinstance(item, dict):
            continue
        src = item.get('source_area')
        if src is None:
            problems.append(f'area {key} needs source_area (the keyed area it stands for)')
        elif src not in allowed and src != parent:
            problems.append(f'area {key} source_area {src!r} is neither {area["key"]} nor a named neighbour '
                            f'({", ".join(sorted(allowed - {area["key"]})) or "none"}): no invented geometry')
        elif src != area['key'] and not item.get('outside'):
            problems.append(f'area {key} stands for {src}, another keyed area: mark it outside (that room is '
                            'authored on its own)')
        link = item.get('room_link')
        if isinstance(link, dict) and 'author' in link:
            target = link['author'] if isinstance(link['author'], dict) else {}
            if target.get('area') not in allowed - {area['key']}:
                problems.append(f"area {key} room_link author area {target.get('area')!r} is not a named neighbour")
            elif kit_source.level_key(target.get('level', inputs['level'])) != inputs['level']:
                problems.append(f'area {key} room_link author level must be {inputs["level"]}')
            elif target.get('area') != src:
                problems.append(f"area {key} links to {target.get('area')} but stands for {src}")
    geometry = inputs['geometry']
    if geometry.get('bound'):
        mapped = {e.get('to') for e in geometry.get('exits') or () if isinstance(e, dict)}
        for key, edge in (room.get('exits') or {}).items():
            ends = [areas.get(a, {}).get('source_area') for a in (edge or {}).get('areas', ())]
            others = {e for e in ends if e and e != area['key']}
            for other in others - mapped - ({parent} if parent else set()):
                problems.append(f'exit {key} joins {other}, which the geometry ledger does not connect to '
                                f'{area["key"]}')
    else:
        warns.append('geometry unbound: exits follow the keyed text only, each marked uncertain')
    actors = room.get('actors') if isinstance(room.get('actors'), dict) else {}
    triggers = room.get('triggers') if isinstance(room.get('triggers'), list) else []
    woken = {a for t in triggers if isinstance(t, dict) for a in (t.get('actors') or ())}
    for key in woken:
        actor = actors.get(key)
        if isinstance(actor, dict) and not actor.get('needs_stats') and \
                srd_creatures.stat_block(actor.get('stat_block')) is None:
            problems.append(f'actor {key} is woken by a trigger and needs a stat_block ({{"srd": ...}}) or needs_stats')
    for t in triggers:
        if isinstance(t, dict) and isinstance(t.get('on'), dict) and set(t['on']) - {'disturb', 'enter'}:
            problems.append(f"trigger {t.get('id')}: on is disturb or enter (looking never sets anything off)")
    hidden = {k: a for k, a in actors.items() if isinstance(a, dict) and a.get('status') == 'hidden'}
    for key, actor in hidden.items():
        if actor.get('visible') is not False:
            problems.append(f'actor {key} is hidden and must be "visible": false until its trigger fires')
        if key not in woken:
            problems.append(f'actor {key} is hidden but no trigger wakes it')
    for area_key, story in (room.get('story') or {}).items():
        for hook in (story or {}).get('hooks') or () if isinstance(story, dict) else ():
            if isinstance(hook, dict) and hook.get('by') in hidden:
                problems.append(f"story {area_key} hook {hook.get('id')}: by {hook['by']!r}, a hidden actor, who cannot "
                                'raise it before its trigger fires; give the hook to a visible actor, or make it '
                                "the feature's own pull and leave the story to the trigger")
    try:
        found, more = kit_fidelity.check(room, inputs['manifest'], {
            'bound': bool(geometry.get('bound')), 'parent': parent,
            'intro': (area.get('parent') or {}).get('intro') or []})
    except (AttributeError, TypeError, KeyError, ValueError) as exc:
        found, more = [f'malformed room data for the fidelity check ({type(exc).__name__}: {exc})'], []
    problems += [p for p in found if p not in problems]
    try:
        shape = held_and_part_problems(room) + layer_problems(room)
    except (AttributeError, TypeError, KeyError, ValueError) as exc:
        shape = [f'malformed room data for the parts/layer check ({type(exc).__name__}: {exc})']
    problems += [p for p in shape if p not in problems]
    warns += more
    return problems, warns


def _exit_words(room, area):
    """Content words of the exits out of ``area`` (their names and that side's labels)."""
    words = set()
    for edge in (room.get('exits') or {}).values():
        if not isinstance(edge, dict) or area not in (edge.get('areas') or ()):
            continue
        text = ' '.join([str(edge.get('name') or '')] + [str(v) for v in (edge.get('labels') or {}).values()])
        words |= {w for w in re.findall(r"[a-z]{4,}", text.casefold())} - _LAYER_STOP
    return words


_LAYER_STOP = frozenset('back down into from through runs leads east west north south with that this the'.split())


def _anchored(room):
    """Fact ids a trigger fires on or that hold an item: always obvious. Read from those fields only, so
    an id that is also a word elsewhere (a "fire" damage type) never counts."""
    out = set()
    for trigger in room.get('triggers') or ():
        target = ((trigger or {}).get('on') or {}).get('disturb') if isinstance(trigger, dict) else None
        if isinstance(target, str):
            out.add(target)
    for key, fact in (room.get('facts') or {}).items():
        handling = fact.get('handling') if isinstance(fact, dict) else None
        if isinstance(handling, dict) and handling.get('holds'):
            out.add(key)
    return out


def layer_problems(room):
    """``layer`` is obvious or detail; the way on and anything a trigger or a held item hangs on is never
    held back as detail."""
    problems = []
    anchored = _anchored(room)
    for key, fact in (room.get('facts') or {}).items():
        if not isinstance(fact, dict) or fact.get('layer') is None:
            continue
        if fact['layer'] not in LAYERS:
            problems.append(f'fact {key} layer must be obvious or detail')
            continue
        if fact['layer'] != 'detail' or not fact.get('visible'):
            continue
        if key in anchored:
            problems.append(f'fact {key} is what a trigger or a held item hangs on: its layer must be obvious')
            continue
        own = set(re.findall(r"[a-z]{4,}", str(fact.get('text') or '').casefold()))
        places = {w for a in (room.get('areas') or {}).values() if isinstance(a, dict)
                  for w in re.findall(r"[a-z]{4,}", f"{a.get('name') or ''} {a.get('called') or ''}".casefold())}
        shared = (own & _exit_words(room, fact.get('area'))) - places
        if len(shared) >= 2:
            problems.append(f'fact {key} describes the way on ({", ".join(sorted(shared))}): the way on and the '
                            'exits are always obvious, so its layer must be obvious')
    return problems


def held_and_part_problems(room):
    """A fact that sits in, under, or in the grip of a handled feature must be that feature's
    ``holds``; a graspable part named on a handled feature or its held item must be in ``parts``."""
    problems = []
    facts = room.get('facts') if isinstance(room.get('facts'), dict) else {}
    handled = {key: fact for key, fact in facts.items()
               if isinstance(fact, dict) and isinstance(fact.get('handling'), dict)}
    held_by = {fact['handling'].get('holds'): key for key, fact in handled.items() if fact['handling'].get('holds')}
    for key, fact in facts.items():
        if not isinstance(fact, dict) or key in handled or not isinstance(fact.get('text'), str):
            continue
        text = fact['text'].casefold()
        for owner, feature in handled.items():
            if owner == key or feature.get('area') != fact.get('area'):
                continue
            nouns = [str(n).casefold() for n in list(feature['handling'].get('nouns') or ()) +
                     list(feature['handling'].get('parts') or ())]
            named = next((n for n in nouns if re.search(r'\b' + re.escape(n) + r's?\b', text)), None)
            if named and HELD_IN.search(text) and key not in held_by:
                problems.append(f'fact {key} is in or on {owner} ("{named}"): list it as {owner}\'s handling.holds '
                                'so handling the feature finds it and disturbs it')
    for owner, feature in handled.items():
        listed = {str(n).casefold() for n in list(feature['handling'].get('nouns') or ()) +
                  list(feature['handling'].get('parts') or ())}
        texts = [feature.get('text') or '']
        held = facts.get(feature['handling'].get('holds'))
        if isinstance(held, dict):
            texts.append(held.get('text') or '')
        words = set(re.findall(r"[a-z]+", ' '.join(texts).casefold()))
        missing = sorted(w for w in PART_WORDS if w in words and w not in listed and w.rstrip('s') not in listed)
        if missing:
            problems.append(f'fact {owner} has graspable parts ({", ".join(missing)}): list them in handling.parts '
                            'so "I pry the claw open" disturbs it')
    return problems


def loader_problems(room):
    """The room loader's own checks, every compiler's problems collected (not the first per
    stage), alarm warnings as errors (Kit would invent responders)."""
    found = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', kit_rooms.RoomWarning)
        try:
            kit_rooms.check_room(copy.deepcopy(room), room.get('id', 'authored room'))
        except kit_rooms.RoomMountError as exc:
            found = list(exc.problems)
        except (AttributeError, TypeError, KeyError, ValueError, IndexError) as exc:
            found = [f'malformed room data ({type(exc).__name__}: {exc})']
    try:
        later = kit_rooms.unsupported(room) + kit_rooms.later_stage_problems(copy.deepcopy(room))
    except (AttributeError, TypeError, KeyError, ValueError, IndexError):
        later = []
    found += [p for p in later if p not in found]
    found += [str(w.message).split(': ', 1)[-1] for w in caught if issubclass(w.category, kit_rooms.RoomWarning)]
    return [_generic(p) for p in found]


def alarm_problems(room):
    try:
        return kit_rooms.alarm_warnings(room)
    except (AttributeError, TypeError, KeyError, ValueError):
        return []


def mount_probe(room):
    """Mount it for real in a throwaway session and build the first packet: what start does.
    Returns (problems, first packet bytes)."""
    from .kit_agent import start_session
    from .state_context import InvalidChange
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'room.json'
        path.write_text(json.dumps(room, ensure_ascii=False), encoding='utf-8')
        try:
            started = start_session(Path(tmp) / 'probe.sqlite', room=str(path), manifests=False, _verified=True)
        except kit_rooms.RoomMountError as exc:
            return list(exc.problems), None
        except (InvalidChange, KeyError, TypeError, ValueError, AttributeError) as exc:
            return [f'mount probe: {type(exc).__name__}: {exc}'], None
    prepared = started['prepared']
    problems = []
    hidden = [k for k, a in (room.get('actors') or {}).items() if isinstance(a, dict) and a.get('status') == 'hidden']
    public = json.dumps((prepared.get('input') or {}).get('public') or {}, ensure_ascii=False)
    problems += [f'mount probe: hidden actor {k} reaches the public packet' for k in hidden if f'"{k}"' in public]
    return problems, len(json.dumps(prepared, ensure_ascii=False, separators=(',', ':')).encode())


def static_problems(room, inputs):
    """Everything but the mount probe: (errors, warnings)."""
    problems, warns = authoring_problems(room, inputs) if isinstance(room, dict) else (['the room must be one JSON object'], [])
    if isinstance(room, dict):
        found = loader_problems(room)
        found += [p for p in alarm_problems(room) if p not in found]
        problems = problems + [p for p in found if p not in problems]
    return problems, warns


def validate(room, inputs):
    """{'ok', 'errors', 'warnings', 'first_packet_bytes'}: every error at once (the repair
    gets one try)."""
    problems, warns = static_problems(room, inputs)
    first = None
    if not problems:
        problems, first = mount_probe(room)
    return {'ok': not problems, 'errors': problems, 'warnings': warns, 'first_packet_bytes': first,
            'validator': VALIDATOR_VERSION}


def _unstamped(room):
    return {k: v for k, v in room.items() if k != 'authoring'}


def verify_room(source, book=None, directory=None):
    """A room claiming to be authored (``authoring`` stamp or an ``authored-`` id), checked
    again against its source before it mounts: start --room and every author link call this.
    Returns None or raises RoomMountError naming the problems."""
    stamp = source.get('authoring') if isinstance(source.get('authoring'), dict) else None
    if stamp is None and not str(source.get('id', '')).startswith('authored-'):
        return None
    ref = source.get('id', 'authored room')
    if stamp and stamp.get('fallback'):
        problems = fallback_problems(source)
        if problems:
            raise kit_rooms.RoomMountError(ref, problems)
        return None
    level = (stamp or {}).get('level')
    area = (stamp or {}).get('area')
    if not (level and area):
        m = re.match(r'^authored-level-(\d+)-area-([0-9a-z]+)$', str(source.get('id', '')))
        if not m:
            raise kit_rooms.RoomMountError(ref, ['an authored room needs its authoring stamp (level, area)'])
        level, area = m.group(1), m.group(2)
    try:
        book = book or book_from(directory, level)
        inputs = area_inputs(book, area)
    except kit_source.SourceUnavailable as exc:
        raise kit_rooms.RoomMountError(ref, [f'cannot re-check an authored room without its source: {exc}']) from None
    problems, _ = static_problems(_unstamped(source), inputs)
    if stamp and stamp.get('source_hash') != source_hash(inputs)[:16]:
        problems.append('authored from a different source text or validator version: author it again')
    if problems:
        raise kit_rooms.RoomMountError(ref, problems)
    return None


# ---------------------------------------------------------------- the fallback stand-in

FALLBACK_HIDDEN_WORDS = re.compile(r'\b(concealed|hidden|secret|trap|pit|ambush|lair|demiplane|spiked)\b', re.I)


def fallback_room(inputs, session=None, reason='authoring_failed'):
    """A minimal, valid room standing in for an area whose authoring failed (or is not done):
    the PC is inside it; its keyed text is dm_only (hidden facts) for Kit to improvise from;
    its named ways out are author links. Flagged ``authoring.fallback``."""
    area = inputs['area']
    lines, used = [], 0
    for line in area['keyed_text']:
        chunk = line[:900]
        if used + len(chunk) > FALLBACK_TEXT_BYTES:
            break
        lines.append(chunk)
        used += len(chunk)
    facts = {f'keyed_{i + 1}': {'area': 'inside', 'visible': False, 'text': text} for i, text in enumerate(lines)}
    areas = {'inside': {'name': 'The next area', 'called': 'here', 'source_area': area['key'],
                        'arrival': 'A newcomer comes in.'}}
    exits = {}
    ways = [e for e in inputs['manifest']['exits'] if e.get('way') or e.get('sibling')]
    for n, way in enumerate(ways):
        title = way.get('title') or ''
        name = f'the way toward {title.lower()}' if title and not FALLBACK_HIDDEN_WORDS.search(title) else \
            f'another way on ({n + 1})'
        key = f'to_{way["area"]}'
        areas[key] = {'name': name[0].upper() + name[1:], 'called': name, 'source_area': way['area'], 'outside': True,
                      'beyond': True, 'room_link': {'author': {'level': inputs['level'], 'area': way['area']}}}
        exits[key] = {'name': name, 'areas': ['inside', key], 'secret': False, 'uncertain': True,
                      'labels': {'inside': name[0].upper() + name[1:] + '.', key: 'Back the way you came.'}}
    return {'id': room_id(inputs['level'], area['key']) + '-fallback',
            'source_ref': f"Level {inputs['level']} / {area['key']} (fallback: Kit improvises from the keyed text)",
            'authoring': {'fallback': True, 'level': inputs['level'], 'area': area['key'], 'session': session,
                          'reason': reason, 'note': FALLBACK_NOTE},
            'starting_area': 'inside', 'areas': areas, 'exits': exits, 'facts': facts, 'actors': {}, 'resources': {}}


def fallback_problems(source):
    """A fallback stand-in carries nothing but the engine's own shape."""
    problems = []
    if set(source) - {'id', 'source_ref', 'authoring', 'starting_area', 'areas', 'exits', 'facts', 'actors', 'resources'}:
        problems.append('a fallback room holds only the stand-in the engine writes')
    if source.get('actors') or any(f.get('visible') for f in (source.get('facts') or {}).values() if isinstance(f, dict)):
        problems.append('a fallback room has no actors and no visible facts')
    return problems


def fallback_flag(source):
    """The authoring_fallback flag for a turn in this room, or None."""
    stamp = (source or {}).get('authoring') if isinstance((source or {}).get('authoring'), dict) else None
    if not (stamp and stamp.get('fallback')):
        return None
    return {'level': stamp.get('level'), 'area': stamp.get('area'), 'reason': stamp.get('reason'),
            'session': stamp.get('session')}


# ---------------------------------------------------------------- the session's jobs and cache

class Session:
    """Authored rooms for one play session, keyed by area id plus source hash (which carries
    the validator version). A fallback is the session's own (``session``: its DB id)."""

    def __init__(self, directory, session=None):
        self.dir = Path(directory).resolve()
        self.session = session if session is not None else session_id(_db_of(self.dir))

    def _key(self, level, area, digest):
        return f'{kit_source.level_key(level)}-{area}-{digest[:16]}'

    def room_path(self, level, area, digest):
        return self.dir / f'{self._key(level, area, digest)}.json'

    def job_path(self, level, area, digest):
        return self.dir / f'{self._key(level, area, digest)}.job.json'

    def job(self, level, area, digest):
        path = self.job_path(level, area, digest)
        if not path.is_file():
            return None
        job = json.loads(path.read_text(encoding='utf-8'))
        if job.get('status') == 'fallback' and job.get('session') != self.session:
            # Another session's fallback: this session authors the room afresh.
            job = {**job, 'status': 'requested', 'attempts': [], 'previous_session_fallback': job.get('session')}
        return job

    def _save_job(self, level, area, digest, job):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.job_path(level, area, digest).write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding='utf-8')

    def _bind(self, book):
        """Remember which source this session authors the level from."""
        if not getattr(book, 'origin', None):
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / 'sources.json'
        bound = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        if bound.get(book.level) != book.origin:
            bound[book.level] = book.origin
            path.write_text(json.dumps(bound, indent=1), encoding='utf-8')

    def _fresh(self, level, key, digest, inputs):
        return {'status': 'requested', 'level': level, 'area': key, 'source_hash': digest,
                'validator': VALIDATOR_VERSION, 'attempts': [], 'keyed_text': inputs['area']['keyed_text']}

    def request(self, book, area, db=None):
        """A cached room (a hit, nothing regenerated) or the authoring packet. After a fallback
        the packet comes again: a good room submitted later replaces the fallback."""
        self._bind(book)
        built = packet(book, area, db)
        inputs = area_inputs(book, area)
        digest = source_hash(inputs)
        key = built['area']['key']
        job = self.job(book.level, key, digest)
        if job and job['status'] == 'accepted' and Path(job['room_path']).is_file():
            return {'stage': 'cached', 'room_path': job['room_path'], 'room_id': built['room_id'],
                    'source_hash': digest[:16]}
        if not job or job.get('previous_session_fallback'):
            self._save_job(book.level, key, digest, self._fresh(book.level, key, digest, inputs))
        if job and job['status'] == 'fallback':
            return {**built, 'stage': 'author_room', 'after_fallback': fallback_view(job)}
        return built

    def submit(self, book, area, room, db=None):
        self._bind(book)
        inputs = area_inputs(book, area)
        digest = source_hash(inputs)
        key = inputs['area']['key']
        job = self.job(book.level, key, digest) or self._fresh(book.level, key, digest, inputs)
        if job['status'] == 'accepted' and Path(job['room_path']).is_file():
            return {'stage': 'cached', 'room_path': job['room_path'], 'room_id': room_id(book.level, key),
                    'source_hash': digest[:16]}
        result = validate(room, inputs)
        job['attempts'].append({'ok': result['ok'], 'errors': result['errors'], 'warnings': result['warnings']})
        if result['ok']:
            path = self.room_path(book.level, key, digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            stamped = {**room, 'authoring': {'level': book.level, 'area': key, 'source_hash': digest[:16],
                                             'validator': VALIDATOR_VERSION}}
            path.write_text(json.dumps(stamped, ensure_ascii=False, indent=1), encoding='utf-8')
            replaced = job['status'] == 'fallback'
            job.update(status='accepted', room_path=str(path))
            job.pop('previous_session_fallback', None)
            self._save_job(book.level, key, digest, job)
            return {'stage': 'accepted', 'room_path': str(path), 'room_id': room['id'], 'source_hash': digest[:16],
                    'attempt': len(job['attempts']), 'warnings': result['warnings'],
                    'first_packet_bytes': result['first_packet_bytes'],
                    **({'replaces_fallback': True} if replaced else {}),
                    'next_step': f'python3 -m runtime.kit_agent start --db {db or "<db>"} --room {path}'
                                 ' (or walk into its room_link: it mounts on arrival)'}
        if job['status'] == 'fallback' or len(job['attempts']) >= MAX_ATTEMPTS:
            job.update(status='fallback', session=self.session)
            self._save_job(book.level, key, digest, job)
            return fallback_view(job)
        job['status'] = 'repair'
        self._save_job(book.level, key, digest, job)
        return {'stage': 'repair', 'attempt': len(job['attempts']), 'attempts_left': MAX_ATTEMPTS - len(job['attempts']),
                'errors': result['errors'], 'warnings': result['warnings'],
                'task': ('Your room did not validate. Fix every error below and submit the whole room again; '
                         'change nothing the errors do not name. This is the last try before the fallback.'),
                'packet': packet(book, key, db) | {'previous_room': room}}

    def resolve_link(self, link, book=None):
        """A room_link {"author": {level, area}} -> {room: absolute path, area} for
        kit_rooms.arrive: the accepted room for the current source (re-checked), else the
        fallback stand-in (the PC still walks in; Kit improvises, flagged)."""
        target = link['author']
        level, area = kit_source.level_key(target.get('level')), str(target.get('area'))
        try:
            book = book or book_from(self.dir, level)
            inputs = area_inputs(book, area)
        except kit_source.SourceUnavailable as exc:
            raise RoomNotAuthored(f'level {level} area {area}', [str(exc)],
                                  {'level': level, 'area': area, 'why': 'no source text configured'}) from None
        digest = source_hash(inputs)
        job = self.job(level, inputs['area']['key'], digest)
        reason = 'not_authored_yet'
        if job and job['status'] == 'accepted' and Path(job['room_path']).is_file():
            room = json.loads(Path(job['room_path']).read_text(encoding='utf-8'))
            try:
                verify_room(room, book)
                return {'room': str(Path(job['room_path']).resolve()),
                        'area': link.get('area') or room.get('starting_area')}
            except kit_rooms.RoomMountError:
                reason = 'cached_room_failed_recheck'
                job.update(status='repair', attempts=job.get('attempts', [])[:1])
                self._save_job(level, inputs['area']['key'], digest, job)
        elif job and job['status'] == 'fallback':
            reason = 'authoring_failed'
        self.dir.mkdir(parents=True, exist_ok=True)
        stand_in = fallback_room(inputs, self.session, reason)
        path = self.dir / f'{self._key(level, inputs["area"]["key"], digest)}.fallback-{self.session or "none"}.json'
        path.write_text(json.dumps(stand_in, ensure_ascii=False, indent=1), encoding='utf-8')
        return {'room': str(path), 'area': 'inside', 'fallback': True}


def _db_of(directory):
    name = str(directory)
    return name[:-len('.authored')] if name.endswith('.authored') else None


def fallback_view(job):
    return {'stage': 'fallback', 'flag': 'authoring_fallback', 'level': job['level'], 'area': job['area'],
            'improvise_from': 'keyed_text', 'keyed_text': job.get('keyed_text', []),
            'errors': (job['attempts'][-1]['errors'] if job.get('attempts') else []), 'note': FALLBACK_NOTE,
            'retry': 'submit a corrected room any time: an accepted room replaces the fallback on the next entry'}


def _links(source):
    out = []
    for key, item in (source.get('areas') or {}).items():
        link = (item or {}).get('room_link') if isinstance(item, dict) else None
        if isinstance(link, dict) and isinstance(link.get('author'), dict):
            out.append((key, kit_source.level_key(link['author'].get('level')), str(link['author'].get('area'))))
    return out


def author_ahead(source, state, db):
    """Every neighbour of the current area that is authored on demand, with its status: the
    host authors them in the background while the player plays this area, so the next room is
    ready by entry. From an approach (the room's starting area or an outside area) it reaches
    two steps: the neighbours' named ways too. A fallback here is listed for retry."""
    if db is None:
        return []
    session = Session(session_dir(db))
    found, seen = [], set()

    def add(level, area, via, depth):
        if (level, area) in seen:
            return
        seen.add((level, area))
        try:
            inputs = area_inputs(book_from(session.dir, level), area)
        except kit_source.SourceUnavailable:
            found.append({'level': level, 'area': area, 'via': via, 'status': 'no_source'})
            return
        job = session.job(level, inputs['area']['key'], source_hash(inputs))
        status = job['status'] if job else 'not_requested'
        item = {'level': level, 'area': area, 'via': via, 'status': status, **({'depth': depth} if depth > 1 else {})}
        if status != 'accepted':
            item['request'] = _command('request', level, area, db)
        found.append(item)
        return inputs

    flag = fallback_flag(source)
    if flag:
        add(kit_source.level_key(flag['level']), flag['area'], 'here (fallback: retry)', 1)
    here = state.get('area')
    at_approach = here == source.get('starting_area') or bool(((source.get('areas') or {}).get(here) or {}).get('outside'))
    for via, level, area in _links(source):
        inputs = add(level, area, via, 1)
        if at_approach and inputs:
            for way in inputs['manifest']['exits']:
                if (way.get('way') or way.get('sibling')) and way['area'] != area:
                    add(level, way['area'], f'{via} > {area}', 2)
    return found


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description='Source-to-room authoring (docs/architecture/SOURCE_TO_ROOM.md)')
    parser.add_argument('command', choices=['request', 'submit', 'status'])
    parser.add_argument('--db', help='the play session database; authored rooms live in <db>.authored/')
    parser.add_argument('--cache', help='an explicit authored-room directory (default <db>.authored)')
    parser.add_argument('--level', required=True)
    parser.add_argument('--area', required=True)
    parser.add_argument('--source', help=f'the book text (default ${kit_source.ENV_TEXT} or config/kit_source.json)')
    parser.add_argument('--map-index', help='the level map index (default docs/architecture/runtime/MAP_INDEX.md)')
    parser.add_argument('--ledger', help='a geometry ledger (default $KIT_LEVEL_GEOMETRY, '
                                         'docs/campaign/levels/LEVEL_NN_GEOMETRY.json or '
                                         'docs/campaign/levels/geometry/LEVEL_NN.json)')
    parser.add_argument('--input-file', help='submit: the room JSON Kit wrote; - reads stdin')
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args(argv)
    if not (args.db or args.cache):
        parser.error('give --db (the session) or --cache')
    session = Session(args.cache or session_dir(args.db), session=session_id(args.db) if args.db else None)
    try:
        book = Book(args.level, source=args.source, map_index=args.map_index, ledger=args.ledger)
        if args.command == 'request':
            result = session.request(book, args.area, args.db)
        elif args.command == 'submit':
            if not args.input_file:
                parser.error('submit requires --input-file')
            raw = sys.stdin.read() if args.input_file == '-' else Path(args.input_file).read_text(encoding='utf-8')
            try:
                room = json.loads(raw)
            except ValueError as exc:
                room = f'not JSON: {exc}'
            result = session.submit(book, args.area, room, args.db)
        else:
            inputs = area_inputs(book, args.area)
            job = session.job(book.level, inputs['area']['key'], source_hash(inputs))
            result = {'stage': 'status', 'job': job and {k: v for k, v in job.items() if k != 'keyed_text'}}
    except kit_source.SourceUnavailable as exc:
        print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
    return 0


if __name__ == '__main__':
    sys.exit(main())

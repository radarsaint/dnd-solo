"""Source-to-room authoring: Kit writes a room file from the book's keyed text, the engine
checks it (docs/architecture/SOURCE_TO_ROOM.md).

No hand-written room files. When play nears a keyed area, the runtime builds an **authoring
packet** (that area's keyed text, the level DM layer's notes for it, its geometry, the room
schema with its limits, and the hard rules). The host model (Kit, through the same bridge
flow as her decisions) returns one room JSON object. ``submit`` validates it: the authoring
rules here, then the room loader's own mount checks (``kit_rooms.check_room``), then a real
mount probe (a throwaway session that builds the first packet). A failure returns a
**repair packet** with every error; one repair is allowed. A second failure stops cleanly
with a **fallback**: Kit runs the area by improvising from its keyed text, flagged, with no
engine support for its mechanics. An accepted room is cached per session (``<db>.authored/``)
under the area id plus a hash of what it was written from, so re-entry never regenerates.

Area links: an area's ``room_link`` may be ``{"author": {"level": "01", "area": "17b"}}`` (and
an optional ``area`` in that room, default its ``starting_area``). Moving into it mounts the
cached room; if it is not authored yet, the move is a pending ruling naming the command, and
every prepare packet one step from such a link carries ``author_ahead`` so the host can
author it while the player reads the doorway.

No model calls, no API, no network. The book text is read from a local path
(``kit_source.source_text_path``) and never written into the repo.
"""
import argparse
import copy
import json
import re
import sys
import tempfile
import warnings
from pathlib import Path

from . import kit_rooms, kit_source, srd_creatures

SCHEMA_VERSION = 'source-to-room/1'
MAX_ATTEMPTS = 2  # the first try and one repair
ROOM_MAX_BYTES = 16000
FORBIDDEN_KEYS = {'code', 'script', 'eval', 'exec', 'python', 'function', 'lambda', 'import'}
TRIGGER_WORDS = re.compile(
    r"\b(if (?:it|the \w+(?: \w+)?|anyone|a character) (?:is |are )?(?:disturbed|touched|harmed|opened|moved|"
    r"approached)|(?:emerge|burst|spring|lunge)s? (?:out )?and attack|attacks? (?:all|anyone|any creature|"
    r"interlopers|intruders|those) (?:who|that|on sight)|attack (?:on sight|immediately)|ambush)", re.I)
DC_IN_TEXT = re.compile(r'\bDC (\d{1,2})\b')
TRIGGER_RULE = (
    'Emit triggers yourself from the keyed text: a condition like "if the corpse is disturbed, the centipedes '
    'emerge and attack" is a trigger {"on": {"disturb": <the handled fact>}, "actors": [...], "starts_combat": true, '
    '"reveal": <one public line>} whose actors are "status": "hidden", "visible": false until it fires; "attack all '
    'who enter" is {"on": {"enter": <area>}}. A creature lurking out of sight gets "surprise": {"stealth": null} '
    '(its stat block\'s Stealth). Never narrate an ambush the room file does not declare.')
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
    'Contents, creatures, traps, treasure, DCs and scripted conditions come from keyed_text and nowhere else. '
    'Use the book\'s numbers (DCs, hit points, damage) exactly; add none it does not give.',
    'Geometry comes from geometry and named_neighbours only: no invented doors, corridors, distances or secret '
    'passages. Every area carries "source_area": the keyed area it stands for.',
    'Every creature that can fight has a stat_block: {"srd": "<name>"} from srd_creatures, or inline '
    '{"ac", "hp", "attacks": [{"name", "to_hit", "damage", "type", "save"?}]}. A save rider is '
    '"save": {"ability", "dc", "damage", "type", "half", "at_zero"}.',
    TRIGGER_RULE,
    'Hidden actors stay dm_only until their trigger fires: no visible fact, tease, arrival line, area name or '
    'exit label may name them or what they are.',
    'Every alarm or escalation (bell, horn, shout for help) lists its responders on its fact: '
    '"alarm": {"responders": [{"who", "count", "stat_block"}], "arrives_in_rounds"}.',
    'The approach is tease-only: its tease says what is seen or heard from outside that points toward the hook; '
    'nothing from inside that the PC could not sense from there.',
    'A hidden truth found by a check is a claim (claims.<thing>, ROOM_LOADER section 2), with the book\'s DC.',
    'Next areas: an outside area joined to a named neighbour carries "room_link": {"author": {"level", "area"}} '
    'so the next room is authored on demand, not invented.',
    PARTS_RULE,
    LAYER_RULE,
]
ROOM_SCHEMA = {
    'format': 'docs/architecture/ROOM_LOADER.md section 2 (the loader refuses anything else)',
    'required': {'id': 'exactly room_id', 'source_ref': 'names the keyed area', 'starting_area': 'the approach',
                 'areas': '{id: {name, called, source_area, outside?, beyond?, arrival?, tease? (approach), room_link?}}',
                 'exits': '{id: {name, areas: [a, b], secret, labels: {a: text, b: text}, go_text?}}',
                 'facts': '{id: {area, text, visible, handling?: {nouns, parts?, look?, move?, enter?, handle?, '
                          'holds?}, alarm?, layer? (obvious|detail)}}',
                 'actors': '{id: {name, location, status (alive|hidden), visible, motive, knowledge, secrets, '
                           'communication_profile: {rhythm, humor}, stat_block?, guards?, armed?}}'},
    'optional': ['story (about, purposes, hooks with by/primary/within_beats/delivered_when, endings)', 'claims',
                 'triggers', 'attitudes', 'leak_phrases', 'leak_keywords', 'public_performance', 'resources'],
    'tease': {'text': 'what reaches the PC outside', 'points_to': 'a story hook id', 'heard': [{'actor': '<actor id>', 'sound': 'what is heard'}]},
    'triggers': [{'id': 'unique', 'on': {'disturb': '<fact id with handling>'}, 'starts_combat': True,
                  'actors': ['<hidden actor ids>'], 'surprise': {'stealth': None}, 'reveal': '<public line, <=300 chars>'}],
    'srd_creatures': sorted(srd_creatures.CREATURES),
    'limits': {'room_bytes': ROOM_MAX_BYTES, 'dm_only_bytes': kit_rooms.DM_ONLY_ROOM_MAX_BYTES,
               'claims_here_bytes': kit_rooms.CLAIMS_HERE_MAX_BYTES, 'attempts': MAX_ATTEMPTS},
}
FALLBACK_NOTE = ('Authoring failed twice. Kit runs this area by improvising from its keyed text: every check, '
                 'fight and secret is off-engine and the turn is flagged authoring_fallback. Geometry stays the '
                 "book's; invent nothing.")


class RoomNotAuthored(kit_rooms.RoomMountError):
    """A room_link to an area with no accepted room in this session (yet, or after a fallback)."""

    def __init__(self, room, problems, authoring):
        super().__init__(room, problems)
        self.authoring = authoring

    def host_view(self):
        return {**super().host_view(), 'error': 'room_not_authored', 'authoring': self.authoring}


# ---------------------------------------------------------------- where things live

def session_dir(db):
    """The session's cache of authored rooms: next to its database, gitignored (*.authored/)."""
    return Path(str(db) + '.authored')


def room_id(level, area):
    return f'authored-level-{kit_source.level_key(level)}-area-{area}'


def _command(verb, level, area, db=None):
    where = f' --db {db}' if db else ''
    tail = ' --input-file <room.json>' if verb == 'submit' else ''
    return f'python3 -m runtime.kit_author {verb}{where} --level {kit_source.level_key(level)} --area {area}{tail}'


# ---------------------------------------------------------------- the authoring packet

class Book:
    """The configured book text, one level's keyed areas, its DM layer and geometry."""

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

    def area(self, key):
        key = str(key).strip().lower()
        if key not in self.areas:
            raise kit_source.SourceUnavailable(f'no keyed area {key!r} on level {self.level}')
        return self.areas[key]


def _strip_artifacts(lines):
    return [l for l in lines if l.strip() and l.strip() != 'View Player Version']


def area_inputs(book, key):
    """Everything the room is written from (and hashed for the cache)."""
    area = book.area(key)
    parent = book.areas.get(area['parent']) if area['parent'] else None
    keyed = _strip_artifacts(area['lines'])
    intro = _strip_artifacts(parent['lines']) if parent else []
    own = [k for k in area_refs_in(intro + keyed)]
    neighbours = [k for k in own if k != area['key'] and k in book.areas]
    # Back-references: an area whose text names this one is its neighbour too (ids and titles
    # only; its text stays out of this packet).
    neighbours += [k for k, other in book.areas.items() if k not in (area['key'], area['parent']) and
                   k not in neighbours and area['key'] in area_refs_in(_strip_artifacts(other['lines']))]
    neighbours = [k for k in neighbours if k != area['parent']]  # the parent is the container, not a way out
    neighbours += [k for k in area['subareas'] if k not in neighbours]
    if parent:
        neighbours += [k for k in parent['subareas'] if k != area['key'] and k not in neighbours]
    named = [{'area': k, 'title': book.areas[k]['title']} for k in neighbours]
    return {
        'level': book.level, 'level_name': book.binding['name'],
        'area': {'key': area['key'], 'title': area['title'], 'keyed_text': keyed,
                 **({'parent': {'key': parent['key'], 'title': parent['title'], 'intro': intro}} if parent else {}),
                 **({'subareas': area['subareas']} if area['subareas'] else {})},
        'named_neighbours': named,
        'level_notes': {'layer': book.layer, **kit_source.level_notes(book.layer_text, area, ' '.join(keyed))},
        'geometry': {'dm_map': book.binding.get('dm_map'),
                     'dm_map_present': bool(book.binding.get('dm_map')) and (kit_source.ROOT / book.binding['dm_map']).is_file(),
                     **kit_source.geometry(book.level, area['key'], book.ledger)},
    }


def area_refs_in(lines):
    return kit_source.area_refs(' '.join(lines))


def source_hash(inputs):
    return kit_source.fingerprint(SCHEMA_VERSION, inputs)


def packet(book, key, db=None):
    """The authoring packet for one keyed area: only that area's text (and its parent's intro),
    never another area's."""
    inputs = area_inputs(book, key)
    digest = source_hash(inputs)
    return {
        'stage': 'author_room', 'schema_version': SCHEMA_VERSION, 'source_hash': digest[:16],
        'room_id': room_id(book.level, inputs['area']['key']),
        'task': ('You are Kit, prepping this keyed area before the player walks in. Write the room file for it: '
                 'one JSON object in the room format below, from keyed_text, level_notes and geometry only. Save it '
                 'to a file and run the submit command. Say nothing at the table about this step.'),
        **inputs,
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


def _words(text):
    """Content words, singular ("centipedes" and "centipede" are one tell)."""
    return {w[:-1] if w.endswith('s') and not w.endswith('ss') else w
            for w in re.findall(r"[a-z]{4,}", str(text).casefold())}


GENERIC = {'with', 'from', 'that', 'this', 'into', 'their', 'there', 'they', 'room', 'floor', 'wall', 'door',
           'doors', 'hall', 'giant', 'large', 'small', 'creature', 'creatures', 'shadow', 'dark', 'body'}


def authoring_problems(room, inputs):
    """What the authoring rules refuse (the loader's own checks run after these pass)."""
    if not isinstance(room, dict):
        return ['the room must be one JSON object']
    problems, warns = [], []
    size = len(json.dumps(room, ensure_ascii=False).encode())
    if size > ROOM_MAX_BYTES:
        problems.append(f'room is {size} bytes (limit {ROOM_MAX_BYTES}); keep it to what the keyed text gives')
    for path, key, value in _walk(room):
        if str(key).casefold() in FORBIDDEN_KEYS:
            problems.append(f'{path}: room files hold data only (no {key!r})')
        if isinstance(value, str) and re.match(r'\s*(def |import |lambda |<script|function\s*\()', value):
            problems.append(f'{path}: room files hold data only (that value reads as code)')
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
        warns.append('geometry unbound: exits follow the keyed text only (no ledger for this area)')
    actors = room.get('actors') if isinstance(room.get('actors'), dict) else {}
    triggers = room.get('triggers') if isinstance(room.get('triggers'), list) else []
    keyed = ' '.join(area['keyed_text'])
    if TRIGGER_WORDS.search(keyed) and not triggers:
        problems.append(f'the keyed text sets off creatures ("{TRIGGER_WORDS.search(keyed).group(0)}") but the room '
                        'declares no triggers: write the trigger, do not leave Kit to improvise the ambush')
    woken = {a for t in triggers if isinstance(t, dict) for a in (t.get('actors') or ())}
    for key in woken:
        actor = actors.get(key)
        if isinstance(actor, dict) and srd_creatures.stat_block(actor.get('stat_block')) is None:
            problems.append(f'actor {key} is woken by a trigger and needs a stat_block (inline or {{"srd": ...}})')
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
                                'the feature\'s own pull and leave the story to the trigger')
    tells = set()
    for key, actor in hidden.items():
        tells |= (_words(key.replace('_', ' ')) | _words(actor.get('name'))) - GENERIC
        sb = actor.get('stat_block') if isinstance(actor.get('stat_block'), dict) else {}
        tells |= _words(sb.get('srd', '')) - GENERIC
    # Words for a hidden creature that also name something visible (the corpse it hides in) are not tells.
    public = []
    for key, fact in (room.get('facts') or {}).items():
        if isinstance(fact, dict) and fact.get('visible'):
            public.append((f'fact {key}', fact.get('text')))
    for key, item in areas.items():
        if isinstance(item, dict):
            for field in ('name', 'called', 'arrival'):
                public.append((f'area {key} {field}', item.get(field)))
            tease = item.get('tease') if isinstance(item.get('tease'), dict) else {}
            public.append((f'area {key} tease', tease.get('text')))
            public += [(f'area {key} tease heard', h.get('sound')) for h in tease.get('heard') or () if isinstance(h, dict)]
    for key, edge in (room.get('exits') or {}).items():
        public += [(f'exit {key} label', text) for text in ((edge or {}).get('labels') or {}).values()]
    for where, text in public:
        leaked = sorted(tells & _words(text))
        if leaked:
            problems.append(f'{where} names a hidden actor ({", ".join(leaked)}): hidden actors stay dm_only '
                            'until their trigger fires')
    problems += held_and_part_problems(room)
    problems += layer_problems(room)
    book_dcs = {int(n) for n in DC_IN_TEXT.findall(keyed)}
    for path, key, value in _walk(room.get('claims') or {}):
        if key == 'dc' and type(value) is int and value not in book_dcs:
            warns.append(f'claims {path}: DC {value} is not a DC the keyed text gives '
                         f'({", ".join(map(str, sorted(book_dcs))) or "it gives none"}); omit dc to use the '
                         "engine's default, or use the book's")
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
    """The room loader's own mount checks, alarm warnings as errors (Kit would invent responders)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', kit_rooms.RoomWarning)
        try:
            kit_rooms.check_room(copy.deepcopy(room), room.get('id', 'authored room'))
        except kit_rooms.RoomMountError as exc:
            # The loader stops at the first stage that fails; a repair gets one try, so name
            # the later-stage problems too where they can be checked at all.
            later = []
            try:
                later = kit_rooms.unsupported(room) + kit_rooms.later_stage_problems(copy.deepcopy(room))
            except (AttributeError, TypeError, KeyError, ValueError, IndexError):
                pass
            return list(exc.problems) + [p for p in later if p not in exc.problems]
        except (AttributeError, TypeError, KeyError, ValueError, IndexError) as exc:
            return [f'malformed room data ({type(exc).__name__}: {exc})']
    return [str(w.message).split(': ', 1)[-1] for w in caught if issubclass(w.category, kit_rooms.RoomWarning)]


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
            started = start_session(Path(tmp) / 'probe.sqlite', room=str(path), manifests=False)
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


def validate(room, inputs):
    """{'ok', 'errors', 'warnings', 'first_packet_bytes'}."""
    problems, warns = authoring_problems(room, inputs) if isinstance(room, dict) else (['the room must be one JSON object'], [])
    if isinstance(room, dict):
        # Every error at once: the repair gets one try.
        found = loader_problems(room)
        found += [p for p in alarm_problems(room) if p not in found]
        problems = problems + [p for p in found if p not in problems]
    first = None
    if not problems:
        problems, first = mount_probe(room)
    return {'ok': not problems, 'errors': problems, 'warnings': warns, 'first_packet_bytes': first}


# ---------------------------------------------------------------- the session's jobs and cache

class Session:
    """Authored rooms for one play session, keyed by area id plus source hash."""

    def __init__(self, directory):
        self.dir = Path(directory)

    def _key(self, level, area, digest):
        return f'{kit_source.level_key(level)}-{area}-{digest[:16]}'

    def room_path(self, level, area, digest):
        return self.dir / f'{self._key(level, area, digest)}.json'

    def job_path(self, level, area, digest):
        return self.dir / f'{self._key(level, area, digest)}.job.json'

    def job(self, level, area, digest):
        path = self.job_path(level, area, digest)
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None

    def _save_job(self, level, area, digest, job):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.job_path(level, area, digest).write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding='utf-8')

    def latest(self, level, area):
        """The newest job for an area, whatever its hash (for link resolution)."""
        if not self.dir.is_dir():
            return None
        jobs = sorted(self.dir.glob(f'{kit_source.level_key(level)}-{area}-*.job.json'),
                      key=lambda p: p.stat().st_mtime)
        return json.loads(jobs[-1].read_text(encoding='utf-8')) if jobs else None

    def request(self, book, area, db=None):
        """A cached room (a hit, nothing regenerated) or the authoring packet."""
        built = packet(book, area, db)
        digest = source_hash(area_inputs(book, area))
        job = self.job(book.level, built['area']['key'], digest)
        if job and job['status'] == 'accepted' and Path(job['room_path']).is_file():
            return {'stage': 'cached', 'room_path': job['room_path'], 'room_id': built['room_id'],
                    'source_hash': digest[:16]}
        if job and job['status'] == 'fallback':
            return fallback_view(job)
        if not job:
            self._save_job(book.level, built['area']['key'], digest,
                           {'status': 'requested', 'level': book.level, 'area': built['area']['key'],
                            'source_hash': digest, 'attempts': [], 'keyed_text': built['area']['keyed_text']})
        return built

    def submit(self, book, area, room, db=None):
        inputs = area_inputs(book, area)
        digest = source_hash(inputs)
        key = inputs['area']['key']
        job = self.job(book.level, key, digest) or {'status': 'requested', 'level': book.level, 'area': key,
                                                    'source_hash': digest, 'attempts': [],
                                                    'keyed_text': inputs['area']['keyed_text']}
        if job['status'] == 'accepted':
            return {'stage': 'cached', 'room_path': job['room_path'], 'room_id': room_id(book.level, key),
                    'source_hash': digest[:16]}
        if job['status'] == 'fallback':
            return fallback_view(job)
        result = validate(room, inputs)
        job['attempts'].append({'ok': result['ok'], 'errors': result['errors'], 'warnings': result['warnings']})
        if result['ok']:
            path = self.room_path(book.level, key, digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(room, ensure_ascii=False, indent=1), encoding='utf-8')
            job.update(status='accepted', room_path=str(path))
            self._save_job(book.level, key, digest, job)
            return {'stage': 'accepted', 'room_path': str(path), 'room_id': room['id'], 'source_hash': digest[:16],
                    'attempt': len(job['attempts']), 'warnings': result['warnings'],
                    'first_packet_bytes': result['first_packet_bytes'],
                    'next_step': f'python3 -m runtime.kit_agent start --db {db or "<db>"} --room {path}'
                                 ' (or walk into its room_link: it mounts on arrival)'}
        if len(job['attempts']) >= MAX_ATTEMPTS:
            job['status'] = 'fallback'
            self._save_job(book.level, key, digest, job)
            return fallback_view(job)
        job['status'] = 'repair'
        self._save_job(book.level, key, digest, job)
        return {'stage': 'repair', 'attempt': len(job['attempts']), 'attempts_left': MAX_ATTEMPTS - len(job['attempts']),
                'errors': result['errors'], 'warnings': result['warnings'],
                'task': ('Your room did not validate. Fix every error below and submit the whole room again; '
                         'change nothing the errors do not name. This is the last try before the fallback.'),
                'packet': packet(book, key, db) | {'previous_room': room}}

    def resolve_link(self, link):
        """A room_link {"author": {level, area}} -> {room: path, area} for kit_rooms.arrive."""
        target = link['author']
        level, area = kit_source.level_key(target.get('level')), str(target.get('area'))
        job = self.latest(level, area)
        if job and job['status'] == 'accepted' and Path(job['room_path']).is_file():
            room = json.loads(Path(job['room_path']).read_text(encoding='utf-8'))
            return {'room': job['room_path'], 'area': link.get('area') or room.get('starting_area')}
        if job and job['status'] == 'fallback':
            raise RoomNotAuthored(f'level {level} area {area}', [f'authoring for area {area} failed twice'],
                                  fallback_view(job))
        raise RoomNotAuthored(f'level {level} area {area}', [f'area {area} is not authored yet in this session'],
                              {'request': _command('request', level, area, _db_of(self.dir)),
                               'level': level, 'area': area})


def _db_of(directory):
    name = str(directory)
    return name[:-len('.authored')] if name.endswith('.authored') else None


def fallback_view(job):
    return {'stage': 'fallback', 'flag': 'authoring_fallback', 'level': job['level'], 'area': job['area'],
            'improvise_from': 'keyed_text', 'keyed_text': job.get('keyed_text', []),
            'errors': (job['attempts'][-1]['errors'] if job.get('attempts') else []), 'note': FALLBACK_NOTE}


def author_ahead(source, state, db):
    """Rooms one step from here that are authored on demand: what the host can author now, while
    the player reads this area (the approach stage), so the room is ready by entry."""
    if db is None:
        return []
    areas, here = source.get('areas') or {}, state.get('area')
    session = Session(session_dir(db))
    found = []
    for key in [here] + [a for edge in (source.get('exits') or {}).values() if isinstance(edge, dict)
                         and here in (edge.get('areas') or ()) for a in edge['areas'] if a != here]:
        link = (areas.get(key) or {}).get('room_link')
        if isinstance(link, dict) and isinstance(link.get('author'), dict):
            level = kit_source.level_key(link['author'].get('level'))
            area = str(link['author'].get('area'))
            job = session.latest(level, area)
            status = job['status'] if job else 'not_requested'
            item = {'level': level, 'area': area, 'via': key, 'status': status}
            if status not in ('accepted', 'fallback'):
                item['request'] = _command('request', level, area, db)
            if item not in found:
                found.append(item)
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
    parser.add_argument('--ledger', help='a geometry ledger (default $KIT_LEVEL_GEOMETRY or '
                                         'docs/campaign/levels/geometry/LEVEL_NN.json)')
    parser.add_argument('--input-file', help='submit: the room JSON Kit wrote; - reads stdin')
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args(argv)
    if not (args.db or args.cache):
        parser.error('give --db (the session) or --cache')
    session = Session(args.cache or session_dir(args.db))
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

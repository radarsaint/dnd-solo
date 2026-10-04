"""The book's keyed text, read from a local path that is never in the repo (source-to-room).

docs/architecture/SOURCE_TO_ROOM.md is the design. This module only reads:

* ``source_text_path()``: where the adventure text lives on this machine. ``KIT_SOURCE_TEXT``
  (an env var) wins; else ``config/kit_source.json`` ({"text": "<path>"}), which is
  gitignored. Nothing here copies the text into the repo.
* ``level_binding(level)``: the level's row in docs/architecture/runtime/MAP_INDEX.md (its DM
  layer, canonical map, and indexed room headings).
* ``keyed_areas(text, headings)``: the book split into keyed areas by their headings
  ("17. Stone Temple Pileup", "17a. Foyer"), in the order the map index lists them. A
  sub-area ("17a.") belongs to its parent ("17."); the parent's own lines before its first
  sub-area are its intro.
* ``level_notes(level_doc, area)``: what the level DM layer says that bears on one area: its
  geometry rules, the lines that name the area, and the level NPCs its keyed text names.
* ``geometry(level, area)``: the area's exits from a machine-readable geometry ledger, when
  one exists (``KIT_LEVEL_GEOMETRY`` or docs/campaign/levels/geometry/LEVEL_NN.json). The DM
  map is a licensed image the runtime cannot read; without a ledger the geometry is unbound
  and says so.

Data only, no model calls.
"""
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'kit_source.json'
MAP_INDEX = ROOT / 'docs' / 'architecture' / 'runtime' / 'MAP_INDEX.md'
GEOMETRY_DIR = ROOT / 'docs' / 'campaign' / 'levels' / 'geometry'
ENV_TEXT = 'KIT_SOURCE_TEXT'
ENV_GEOMETRY = 'KIT_LEVEL_GEOMETRY'

HEADING = re.compile(r'^(\d{1,3})([a-z])?\.\s+(\S.{0,90})$')
AREA_REF = re.compile(r'\bareas?\s+(\d{1,3}[a-z]?)((?:\s*(?:,|and|or|–|-)\s*\d{1,3}[a-z]?)*)', re.I)
CHAPTER = re.compile(r'^(?:(?:Chapter|Appendix|Level \d+:)\s|Aftermath$)')
SLICE_MAX_LINES = 80  # the last area of a level has no next heading to stop it


class SourceUnavailable(LookupError):
    """No book text configured on this machine, or not the area asked for."""


def _norm(text):
    return re.sub(r'\s+', ' ', str(text).replace('\u2019', "'").replace('\u2018', "'")).strip().casefold()


def source_text_path(explicit=None):
    """The configured book text, or None when this machine has none."""
    if explicit:
        return Path(explicit)
    if os.environ.get(ENV_TEXT):
        return Path(os.environ[ENV_TEXT])
    if CONFIG.is_file():
        try:
            found = json.loads(CONFIG.read_text(encoding='utf-8')).get('text')
        except ValueError:
            found = None
        if found:
            return Path(found)
    return None


def read_source(explicit=None):
    path = source_text_path(explicit)
    if path is None or not path.is_file():
        raise SourceUnavailable(f'no book text: set {ENV_TEXT} or config/kit_source.json {{"text": <path>}} '
                                '(the text is never committed to the repo)')
    return path.read_text(encoding='utf-8')


def level_key(level):
    """'1', '01', 1 -> '01'."""
    return f'{int(str(level).strip()):02d}'


def level_binding(level, map_index=None):
    """The level's MAP_INDEX row: {level, name, layer, dm_map, player_map, headings}."""
    text = Path(map_index or MAP_INDEX).read_text(encoding='utf-8')
    want = int(level_key(level))
    for block in re.split(r'^### ', text, flags=re.M)[1:]:
        head = re.match(r'Level (\d+): (.+)', block)
        if not head or int(head.group(1)) != want:
            continue
        field = lambda name: (re.search(rf'- {name}: `?([^`\n]+)`?', block) or [None, None])[1]
        headings = [h.strip() for h in (field('Indexed room headings') or '').split(';') if h.strip()]
        return {'level': level_key(level), 'name': head.group(2).strip(), 'layer': field('Level layer'),
                'dm_map': field('Canonical DM map'), 'player_map': field('Player presentation map'),
                'headings': headings}
    raise SourceUnavailable(f'level {level} is not in {map_index or MAP_INDEX}')


def keyed_areas(text, headings):
    """{area key: {key, number, letter, title, line, lines, parent}} for one level, found by
    walking the book for the index's headings in order. ``lines`` is the area's own text
    (heading excluded); a parent's lines stop at its first sub-area."""
    lines = text.splitlines()
    wanted = []
    for heading in headings:
        m = re.match(r'(\d{1,3})\.\s+(.+)', heading)
        if m:
            wanted.append((int(m.group(1)), _norm(m.group(2))))
    if not wanted:
        return {}
    starts, at, i = [], 0, 0
    # The level begins at its first heading; every later heading must come in order.
    while i < len(lines) and at < len(wanted):
        m = HEADING.match(lines[i].strip())
        if m and not m.group(2) and int(m.group(1)) == wanted[at][0] and _norm(m.group(3)) == wanted[at][1]:
            starts.append((i, m.group(1), None, m.group(3).strip()))
            at += 1
            letter = 'a'
            j = i + 1
            nxt = wanted[at] if at < len(wanted) else None
            while j < len(lines):
                s = HEADING.match(lines[j].strip())
                if s and nxt and not s.group(2) and int(s.group(1)) == nxt[0] and _norm(s.group(3)) == nxt[1]:
                    break
                if s and s.group(2) == letter and s.group(1) == m.group(1):
                    starts.append((j, s.group(1), s.group(2), s.group(3).strip()))
                    letter = chr(ord(letter) + 1)
                if nxt is None and j - i > SLICE_MAX_LINES * 4:
                    break
                j += 1
            i = j
            continue
        i += 1
    if not starts:
        return {}
    areas = {}
    for n, (line, number, letter, title) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else min(len(lines), line + 1 + SLICE_MAX_LINES)
        body = [l.rstrip() for l in lines[line + 1:end]]
        if n + 1 == len(starts):
            # The level's last area: stop at a blank-heading boundary the book uses for chapters.
            for k, l in enumerate(body):
                if (HEADING.match(l.strip()) and HEADING.match(l.strip()).group(1) == '1') or CHAPTER.match(l.strip()):
                    body = body[:k]
                    break
        key = number + (letter or '')
        areas[key] = {'key': key, 'number': int(number), 'letter': letter, 'title': title, 'line': line + 1,
                      'lines': [l for l in body if l.strip()], 'parent': number if letter else None}
    for key, area in areas.items():
        area['subareas'] = [k for k, a in areas.items() if a['parent'] == key]
    return areas


def area_refs(text):
    """Area keys a passage names ("area 17b", "areas 6–8", "see area 18"), in order."""
    found = []
    for m in AREA_REF.finditer(text):
        for key in [m.group(1)] + re.findall(r'\d{1,3}[a-z]?', m.group(2) or ''):
            if key not in found:
                found.append(key)
    return found


def _covers(spec, number):
    """'Area 17', 'Areas 6–8', 'Areas 23, 28, and 39' cover area number?"""
    for a, b in re.findall(r'(\d+)\s*[–-]\s*(\d+)', spec):
        if int(a) <= number <= int(b):
            return True
    return number in {int(n) for n in re.findall(r'\d+', re.sub(r'(\d+)\s*[–-]\s*(\d+)', '', spec))}


def level_notes(level_doc_text, area, keyed_text):
    """The level DM layer's notes for one area: the geometry binding rules, every line that
    names the area (by number or range), the room-scoped NPC audit, and the level's preloaded
    NPCs whose names the area's keyed text mentions."""
    lines = level_doc_text.splitlines()
    notes = {'geometry_rules': [], 'mentions': [], 'npc_audit': [], 'npcs': []}
    section = None
    for line in lines:
        if line.startswith('## ') or line.startswith('### '):
            section = line.strip('# ').strip()
            continue
        text = line.strip()
        if not text:
            continue
        if section == 'Geometry Binding' and re.match(r'\d+\.', text):
            notes['geometry_rules'].append(text)
        elif section == 'Room-scoped NPC audit' and re.match(r'\d+\.', text):
            notes['npc_audit'].append(text)
        for m in re.finditer(r'\bAreas?\s+(\d+(?:\s*(?:,\s*and|,|and|or|–|-)\s*\d+)*)\b', text):
            if _covers(m.group(1), area['number']) and text not in notes['mentions']:
                notes['mentions'].append(text)
    # Preloaded NPCs (### headings with a Motive line) named in the keyed text.
    keyed = _norm(keyed_text)
    for m in re.finditer(r'^### (.+)\n+\*\*Motive:\*\*\s*(.+?)\s*$\n\*\*Plan if unopposed:\*\*\s*(.+?)\s*$',
                         level_doc_text, flags=re.M):
        name = m.group(1).strip()
        if any(part.casefold() in keyed for part in name.split() if len(part) > 3):
            notes['npcs'].append({'name': name, 'motive': m.group(2), 'plan': m.group(3)})
    return notes


def geometry(level, area_key, ledger=None):
    """The area's mapped geometry from a ledger, or an unbound record that says why."""
    path = Path(ledger) if ledger else Path(os.environ.get(ENV_GEOMETRY) or GEOMETRY_DIR / f'LEVEL_{level_key(level)}.json')
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        entry = (data.get('areas') or {}).get(area_key)
        if entry is not None:
            return {'bound': True, 'ledger': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                    **entry}
    return {'bound': False,
            'why': 'no geometry ledger lists this area (the canonical DM map is an image the runtime does not read)',
            'rule': ('Exits may join this area only to areas its keyed text names (named_neighbours) and to one '
                     'approach just outside its own way in. Invent no corridors, doors, distances, or secret '
                     'passages; leave geometry the text does not give out of the room.')}


def fingerprint(*parts):
    """A stable hash of the inputs a generated room was written from."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(json.dumps(part, sort_keys=True, ensure_ascii=False).encode())
        digest.update(b'\x00')
    return digest.hexdigest()

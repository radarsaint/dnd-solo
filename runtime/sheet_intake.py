"""Sheet intake, light (campaign-record design P5). Standard library only.

A D&D Beyond PDF export is a fillable form: every number and list on the sheet is a form
field (/T name, /V value) on a widget annotation. Reading those fields is exact and needs
no layout guessing (the printed text is three columns that interleave in pdftotext). This
module reads them with a small stdlib PDF object scanner (plain objects and FlateDecode
object streams; literal, hex and UTF-16 strings; indirect values), maps them to
character_sheet_v1, and validates the result with pc_sheet.check_sheet.

A PDF with no form fields (flattened, scanned, another exporter) falls back to Kit: the
text is extracted with pdftotext when the host has it, and Kit writes the JSON from the
template herself; `character --sheet` validates it. Nothing here needs a third-party module.
"""

import json
import re
import shutil
import subprocess
import zlib
from pathlib import Path

from . import pc_sheet

OBJ = re.compile(rb'(\d+)\s+(\d+)\s+obj\b(.*?)endobj', re.S)
STREAM = re.compile(rb'stream\r?\n(.*?)\r?\nendstream', re.S)
TEXT_MAX = 20000


class IntakeError(Exception):
    pass


# --- PDF strings and objects -------------------------------------------------------------

def _literal(data, i):
    """A PDF literal string starting at data[i] == '('. Returns (bytes, next index)."""
    depth, out, i = 1, bytearray(), i + 1
    escapes = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12,
               ord('('): 40, ord(')'): 41, ord('\\'): 92}
    while i < len(data):
        c = data[i]
        if c == 92:  # backslash
            n = data[i + 1] if i + 1 < len(data) else None
            if n in escapes:
                out.append(escapes[n])
                i += 2
            elif n is not None and 48 <= n <= 55:
                j = i + 1
                while j < len(data) and j < i + 4 and 48 <= data[j] <= 55:
                    j += 1
                out.append(int(data[i + 1:j], 8) & 0xFF)
                i = j
            elif n in (10, 13):  # line continuation
                i += 2 + (n == 13 and i + 2 < len(data) and data[i + 2] == 10)
            else:
                i += 1
            continue
        if c == 40:
            depth += 1
        elif c == 41:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
        out.append(c)
        i += 1
    return bytes(out), i


def _text(raw):
    if raw.startswith(b'\xfe\xff'):
        return raw[2:].decode('utf-16-be', errors='replace')
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw[3:].decode('utf-8', errors='replace')
    return raw.decode('latin-1')


def _value(body, key, objects, depth=0):
    """The text of /key in an object body: a literal, a hex string, a name, or a reference."""
    m = re.search(rb'/' + key + rb'(?![A-Za-z])\s*', body)
    if not m:
        return None
    i = m.end()
    if i >= len(body):
        return None
    c = body[i:i + 1]
    if c == b'(':
        return _text(_literal(body, i)[0])
    if c == b'<' and body[i:i + 2] != b'<<':
        j = body.find(b'>', i)
        hexed = re.sub(rb'\s', b'', body[i + 1:j])
        if len(hexed) % 2:
            hexed += b'0'
        return _text(bytes.fromhex(hexed.decode('ascii')))
    if c == b'/':
        return re.match(rb'/([^\s/<>\[\]()]*)', body[i:]).group(1).decode('latin-1')
    ref = re.match(rb'(\d+)\s+(\d+)\s+R', body[i:])
    if ref and depth < 3:
        target = objects.get(int(ref.group(1)))
        if target is not None:
            stripped = target.strip()
            if stripped.startswith((b'(', b'<')) and not stripped.startswith(b'<<'):
                return _value(b'/X ' + stripped, b'X', objects, depth + 1)
            stream = STREAM.search(target)
            if stream:
                try:
                    data = zlib.decompress(stream.group(1)) if b'FlateDecode' in target else stream.group(1)
                except zlib.error:
                    data = stream.group(1)
                return _text(data)
    return None


def _objects(data):
    objects = {}
    for m in OBJ.finditer(data):
        objects[int(m.group(1))] = m.group(3)
    for body in list(objects.values()):
        if b'/ObjStm' not in body:
            continue
        stream = STREAM.search(body)
        n = re.search(rb'/N\s+(\d+)', body)
        first = re.search(rb'/First\s+(\d+)', body)
        if not (stream and n and first):
            continue
        try:
            content = zlib.decompress(stream.group(1))
        except zlib.error:
            continue
        head = content[:int(first.group(1))].split()
        offsets = [(int(head[k]), int(head[k + 1])) for k in range(0, min(len(head), 2 * int(n.group(1))), 2)]
        for idx, (num, off) in enumerate(offsets):
            start = int(first.group(1)) + off
            end = int(first.group(1)) + offsets[idx + 1][1] if idx + 1 < len(offsets) else len(content)
            objects.setdefault(num, content[start:end])
    return objects


def pdf_fields(source):
    """{field name: value} of a PDF's form fields, in object order. Names keep DDB's spelling,
    trimmed. A field with no value is ''."""
    data = Path(source).read_bytes() if not isinstance(source, (bytes, bytearray)) else bytes(source)
    if not data.startswith(b'%PDF'):
        raise IntakeError('That file is not a PDF.')
    objects = _objects(data)
    fields = {}
    for num in sorted(objects):
        body = objects[num]
        if b'/T' not in body:
            continue
        name = _value(body, b'T', objects)
        if not name:
            continue
        value = _value(body, b'V', objects)
        fields.setdefault(name.strip(), (value or '').replace('\r\n', '\n').replace('\r', '\n'))
    return fields


# --- D&D Beyond fields to character_sheet_v1 ---------------------------------------------

ABILITY_FIELDS = {'str': 'STR', 'dex': 'DEX', 'con': 'CON', 'int': 'INT', 'wis': 'WIS', 'cha': 'CHA'}
SAVE_FIELDS = {'str': 'ST Strength', 'dex': 'ST Dexterity', 'con': 'ST Constitution',
               'int': 'ST Intelligence', 'wis': 'ST Wisdom', 'cha': 'ST Charisma'}
SKILL_FIELDS = {'acrobatics': 'Acrobatics', 'animal_handling': 'Animal', 'arcana': 'Arcana',
                'athletics': 'Athletics', 'deception': 'Deception', 'history': 'History',
                'insight': 'Insight', 'intimidation': 'Intimidation', 'investigation': 'Investigation',
                'medicine': 'Medicine', 'nature': 'Nature', 'perception': 'Perception',
                'performance': 'Performance', 'persuasion': 'Persuasion', 'religion': 'Religion',
                'sleight_of_hand': 'SleightofHand', 'stealth': 'Stealth', 'survival': 'Survival'}
PROF_FIELDS = {skill: (field if skill != 'animal_handling' else 'AnimalHandling') + 'Prof'
               for skill, field in SKILL_FIELDS.items()}
PASSIVE_FIELDS = {'perception': 'Passive1', 'insight': 'Passive2', 'investigation': 'Passive3'}
ORDINAL = re.compile(r'===\s*(CANTRIPS|(\d+)(?:st|nd|rd|th)\s+LEVEL)\s*===', re.I)


def _int(text):
    m = re.search(r'[-+]?\d+', text or '')
    return int(m.group(0)) if m else None


def _sections(text):
    """'=== ARMOR ===\\nShield\\n\\n=== LANGUAGES ===\\nCommon' -> {'armor': ['Shield'], ...}."""
    out, current = {}, None
    for line in (text or '').split('\n'):
        line = line.strip()
        head = re.fullmatch(r'===\s*(.*?)\s*===', line)
        if head:
            current = head.group(1).lower()
            out.setdefault(current, [])
        elif line and current is not None:
            out[current] += [p.strip() for p in line.split(',') if p.strip()]
    return out


USES_LINE = re.compile(r'^\s*\|\s*(\d+)\s*/\s*(Short|Long)\s+Rest', re.I)


def _feature_names(text):
    """Feature names from a DDB features block; a '| 2 / Long Rest' line under one becomes
    '(2/long rest)', the form kit_reactions reads uses from."""
    names = []
    for line in (text or '').split('\n'):
        m = re.match(r'\s*[*\u2022]\s*(.+?)(?:\s+[\u2022]|\s*$)', line)
        if m:
            name = m.group(1).strip()
            if name and name not in names:
                names.append(name)
            continue
        uses = USES_LINE.match(line)
        if uses and names and '/' not in names[-1]:
            names[-1] += f' ({uses.group(1)}/{uses.group(2).lower()} rest)'
    return names


def from_ddb_fields(fields):
    """(sheet, problems): character_sheet_v1 from D&D Beyond form fields. problems names every
    value that could not be read or did not check, so Kit can ask about just those."""
    get = lambda name: (fields.get(name) or '').strip()
    problems = []
    sheet = {'schema': pc_sheet.SCHEMA}
    sheet['name'] = get('CharacterName')
    class_level = get('CLASS  LEVEL') or get('CLASS LEVEL')
    parts = re.findall(r'([A-Za-z][A-Za-z \'-]*?)\s+(\d+)', class_level)
    if parts:
        sheet['class'] = ' / '.join(f'{c.strip()} {n}' if len(parts) > 1 else c.strip() for c, n in parts)
        sheet['level'] = sum(int(n) for _, n in parts)
    else:
        sheet['class'], problems = class_level, problems + ['class and level (CLASS LEVEL)']
    sheet['ancestry'] = get('RACE') or get('SPECIES')
    for key, field in (('background', 'BACKGROUND'), ('alignment', 'ALIGNMENT'), ('size', 'SIZE')):
        if get(field):
            sheet[key] = get(field)
    sheet['abilities'] = {k: _int(get(f)) for k, f in ABILITY_FIELDS.items()}
    sheet['proficiency_bonus'] = _int(get('ProfBonus'))
    sheet['saving_throws'] = {k: _int(get(f)) for k, f in SAVE_FIELDS.items() if _int(get(f)) is not None}
    sheet['skills'] = {k: _int(get(f)) for k, f in SKILL_FIELDS.items() if _int(get(f)) is not None}
    expertise = [k for k, f in PROF_FIELDS.items() if get(f).upper() == 'E']
    if expertise:
        sheet['expertise'] = expertise
    for key, field in (('initiative', 'Init'), ('ac', 'AC'), ('hp', 'MaxHP'), ('speed_ft', 'Speed'),
                       ('spell_save_dc', 'spellSaveDC0'), ('spell_attack', 'spellAtkBonus0')):
        if _int(get(field)) is not None:
            sheet[key] = _int(get(field))
    coins = {c: _int(get(c)) or 0 for c in ('CP', 'SP', 'EP', 'GP', 'PP')}
    if get('GP'):
        sheet['gold_gp'] = coins['GP'] + 10 * coins['PP']
        if coins['CP'] or coins['SP'] or coins['EP']:
            sheet['coins'] = {k.lower(): v for k, v in coins.items() if v}
    profs = _sections(get('ProficienciesLang'))
    if profs.get('languages'):
        sheet['languages'] = profs['languages']
    training = {k: v for k, v in profs.items() if k in ('armor', 'weapons', 'tools') and v}
    if training:
        sheet['proficiencies'] = training
        # The keys kit_chargen.proficiency_sources checks, so an unsourced entry is asked about.
        for key, flat in (('armor', 'armor_proficiencies'), ('weapons', 'weapon_proficiencies'),
                          ('tools', 'tool_proficiencies')):
            if training.get(key):
                sheet[flat] = list(training[key])
    if _int(get('EXPERIENCE POINTS')) is not None:
        sheet['xp'] = _int(get('EXPERIENCE POINTS'))
    attacks = []
    for k in range(1, 20):
        name = get('Wpn Name' if k == 1 else f'Wpn Name {k}')
        if not name:
            continue
        attack = {'name': name}
        bonus = _int(get(f'Wpn{k} AtkBonus'))
        if bonus is not None:
            attack['attack_bonus'] = bonus
        for key, field in (('damage', f'Wpn{k} Damage'), ('notes', f'Wpn Notes {k}')):
            if get(field):
                attack[key] = get(field)
        attacks.append(attack)
    if attacks:
        sheet['attacks'] = attacks
    equipment = []
    for k in range(0, 200):
        name = get(f'Eq Name{k}')
        if not name:
            if f'Eq Name{k}' not in fields:
                break
            continue
        equipment.append({'name': name, 'qty': _int(get(f'Eq Qty{k}')) or 1})
    if equipment:
        sheet['equipment'] = equipment
    features = []
    for k in range(1, 12):
        features += [f for f in _feature_names(get(f'FeaturesTraits{k}')) if f not in features]
    if features:
        sheet['features'] = features
    for k in range(1, 12):
        sub = re.search(r'\*[^\n]*Subclass[^\n]*\n\s*\|\s*([^\n|]+)', get(f'FeaturesTraits{k}'))
        if sub:
            sheet['subclass'] = sub.group(1).strip()
            break
    spells, slots, level = {}, {}, None
    for name, value in fields.items():
        value = value.strip()
        if name.startswith('spellHeader'):
            m = ORDINAL.search(value)
            level = (None if not m else 'cantrips' if m.group(1).lower() == 'cantrips' else m.group(2))
        elif name.startswith('spellSlotHeader'):
            idx = name[len('spellSlotHeader'):]
            n = re.match(r'\s*(\d+)\s+Slots?', value, re.I)
            header = ORDINAL.search(get(f'spellHeader{idx}'))
            if n and header and header.group(2):
                slots[header.group(2)] = int(n.group(1))
        elif re.fullmatch(r'spellName\d+', name) and value and level:
            spell = re.sub(r'\s*\[[A-Z]+\]\s*$', '', value).strip()
            if spell not in spells.setdefault(level, []):
                spells[level].append(spell)
    if spells:
        sheet['spells'] = spells
    if slots:
        sheet['slots'] = slots
    # Passives: kept only when they match 10 + the printed bonus (pc_sheet's rule).
    passives = {}
    for skill, field in PASSIVE_FIELDS.items():
        score = _int(get(field))
        if score is None or skill not in sheet['skills']:
            continue
        if score == 10 + sheet['skills'][skill]:
            passives[skill] = score
        else:
            problems.append(f'passive {skill} {score} is not 10 + {sheet["skills"][skill]} '
                            '(an item or feature adds to it; left out)')
    if passives:
        sheet['passives'] = passives
    for key in ('name', 'ancestry', 'class'):
        if not sheet.get(key):
            problems.append(f'{key} is blank on the sheet')
    for k, v in sheet['abilities'].items():
        if v is None:
            problems.append(f'ability {k} is blank')
    if sheet.get('proficiency_bonus') is None:
        problems.append('proficiency bonus is blank')
    return sheet, problems


def check(sheet):
    """pc_sheet's validation, as a message instead of an exception."""
    try:
        pc_sheet.check_sheet(sheet)
        return None
    except Exception as exc:  # InvalidChange; kept broad so a bad field never crashes intake
        return str(exc)


def pdf_text(path):
    """Text of a PDF for Kit-assisted intake: pdftotext -layout when the host has it, else None."""
    tool = shutil.which('pdftotext')
    if not tool:
        return None
    try:
        done = subprocess.run([tool, '-layout', str(path), '-'], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.decode('utf-8', errors='replace')[:TEXT_MAX] if done.returncode == 0 else None


TEMPLATE = 'tests/fixtures/characters/example_pc.json'


AMMO = re.compile(r'\b(arrows?|bolts?|bullets?|needles?|darts?|ammunition)\b', re.I)


def _ammo(sheet):
    return {e['name']: e.get('qty', 1) for e in (sheet or {}).get('equipment') or []
            if isinstance(e, dict) and AMMO.search(str(e.get('name', '')))}


def hand_edits(before, after):
    """[{what, was, now}]: gold, HP, XP and ammo that differ between the loaded sheet and the new
    one. The player manages their own sheet, so these are noted, never questioned."""
    if not before or not after:
        return []
    out = []
    for key, what in (('gold_gp', 'gold (gp)'), ('hp', 'HP'), ('xp', 'XP')):
        if before.get(key) != after.get(key) and (key in before or key in after):
            out.append({'what': what, 'was': before.get(key), 'now': after.get(key)})
    old, new = _ammo(before), _ammo(after)
    for name in sorted(set(old) | set(new)):
        if old.get(name) != new.get(name):
            out.append({'what': name, 'was': old.get(name), 'now': new.get(name)})
    return out


TRANSCRIBE = ('Copy only values printed on the sheet. Never fill a blank, work a number out, or pick '
              'anything for the player: that is character generation, and Kit never guesses at it. '
              'Leave anything you cannot read out of the JSON and list it in "unread". Show the player '
              'what you read (name, class and level, HP, AC, plus the unread list), ask them for each '
              'unread value, and load it with --sheet only after they confirm.')


def import_pdf(path, out=None):
    """Read a sheet PDF. Returns the host result: sheet_imported, or needs_kit with what was read."""
    path = Path(path)
    if not path.is_file():
        raise IntakeError(f'No file at {path}.')
    fields = pdf_fields(path)
    if not fields or not (fields.get('CharacterName') or fields.get('STR')):
        text = pdf_text(path)
        return {
            'stage': 'needs_kit', 'source': str(path), 'read': 'no_form_fields', 'text': text,
            'template': TEMPLATE,
            'next_step': ('This PDF has no fillable fields to read. '
                          + ('Its text is in "text" (columns may interleave). ' if text else
                             'Extract its text with any PDF tool your sandbox has (pypdf, PyMuPDF, pdftotext). ')
                          + f'Write a character_sheet_v1 JSON in the shape of {TEMPLATE} from it. '
                          + TRANSCRIBE),
            'player_confirms': True,
        }
    sheet, problems = from_ddb_fields(fields)
    failed = check(sheet)
    if failed:
        return {'stage': 'needs_kit', 'source': str(path), 'read': 'form_fields', 'sheet': sheet,
                'problems': problems + [failed], 'template': TEMPLATE,
                'player_confirms': True,
                'next_step': ('Most of the sheet was read. Ask the player for each value problems names; do not '
                              'work it out or fill it in yourself. ' + TRANSCRIBE)}
    target = Path(out) if out else path.with_suffix('.sheet.json')
    target.write_text(json.dumps(sheet, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'stage': 'sheet_imported', 'source': str(path), 'sheet_file': str(target),
            'character': pc_sheet.identity(sheet), 'problems': problems,
            'summary': {k: sheet.get(k) for k in ('name', 'class', 'level', 'hp', 'ac')},
            'next_step': ('Tell the player in one line what you read (name, class and level, HP, AC). '
                          'Load it with start --sheet <sheet_file>, or mid-game character --sheet <sheet_file>. '
                          + ('Mention once, lightly, what could not be read: problems. ' if problems else ''))}

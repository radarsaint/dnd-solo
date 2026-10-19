"""A synthetic D&D Beyond-style fillable PDF, written with the standard library.

Same field names as a D&D Beyond export, made-up character. It exercises what real exports
use: literal strings with escaped parens, UTF-16 hex strings with line breaks, an indirect
/V, and widgets inside a FlateDecode object stream. Never a real sheet.
"""
import zlib

FIELDS = {
    'CharacterName': 'Tamsin Reed', 'CLASS  LEVEL': 'Rogue 3', 'PLAYER NAME': 'tester', 'RACE': 'Halfling',
    'BACKGROUND': 'Criminal', 'EXPERIENCE POINTS': '(Milestone)', 'ALIGNMENT': 'Neutral Good', 'SIZE': 'Small',
    'STR': '8', 'STRmod': '-1', 'DEX': '17', 'DEXmod ': '+3', 'CON': '13', 'CONmod': '+1',
    'INT': '12', 'INTmod': '+1', 'WIS': '14', 'WISmod': '+2', 'CHA': '10', 'CHamod': '+0',
    'ST Strength': '-1', 'ST Dexterity': '+5', 'ST Constitution': '+1', 'ST Intelligence': '+3',
    'ST Wisdom': '+2', 'ST Charisma': '+0', 'ProfBonus': '+2',
    'Acrobatics': '+3', 'Animal': '+2', 'Arcana': '+1', 'Athletics': '-1', 'Deception': '+2',
    'History': '+1', 'Insight': '+4', 'Intimidation': '+0', 'Investigation': '+3', 'Medicine': '+2',
    'Nature': '+1', 'Perception': '+4', 'Performance': '+0', 'Persuasion': '+0', 'Religion': '+1',
    'SleightofHand': '+7', 'Stealth ': '+7', 'Survival': '+2',
    'StealthProf': 'E', 'SleightofHandProf': 'E', 'PerceptionProf': 'P',
    'Passive1': '14', 'Passive2': '14', 'Passive3': '15',
    'Init': '+3', 'AC': '14', 'MaxHP': '21', 'Speed': '25 ft. (Walking)',
    'CP': '3', 'SP': '0', 'EP': '0', 'GP': '42', 'PP': '1',
    'Wpn Name': 'Shortsword', 'Wpn1 AtkBonus': '+5', 'Wpn1 Damage': '1d6+3 Piercing', 'Wpn Notes 1': 'Finesse',
    'Eq Name0': 'Shortsword', 'Eq Qty0': '1', 'Eq Name1': "Thieves' Tools", 'Eq Qty1': '1',
    'Eq Name2': 'Rope', 'Eq Qty2': '2', 'Eq Name3': '',
    'spellHeader0': '=== CANTRIPS ===', 'spellName0': 'Minor Illusion',
    'spellHeader1': '=== 1st LEVEL ===', 'spellSlotHeader1': '2 Slots OO',
    'spellName1': 'Disguise Self [R]', 'spellName2': 'Charm Person',
}
HEX_FIELDS = {
    'FeaturesTraits1': '=== ROGUE FEATURES === \n\n* Sneak Attack \u2022 PHB 96 \nOnce per turn, extra damage.\n\n'
                       '* Cunning Action \u2022 PHB 96 \n   | 1 / Short Rest \u2022 Special \n\n* Rogue Subclass \u2022 PHB 97 \n   | Thief\n',
    'ProficienciesLang': '=== ARMOR === \nLight Armor \n\n=== WEAPONS === \nSimple Weapons, Shortswords \n\n'
                         "=== TOOLS === \nThieves' Tools \n\n=== LANGUAGES === \nCommon, Halfling",
}
INDIRECT = {'BACKGROUND2': 'Criminal'}
IN_STREAM = ('spellName2', 'GP', 'Survival')


def lit(text):
    return b'(' + text.encode('latin-1').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)') + b')'


def hexstr(text):
    raw = b'\xfe\xff' + text.encode('utf-16-be')
    h = raw.hex().upper()
    return b'<' + b'\n'.join(h[i:i + 64].encode() for i in range(0, len(h), 64)) + b'>'


def widget(name, value):
    return b'<<\n/FT/Tx\n/Subtype/Widget\n/T' + lit(name) + b'\n/Type/Annot\n/V' + value + b'\n>>'


def build(fields=None, hex_fields=None, with_fields=True):
    fields = dict(FIELDS if fields is None else fields)
    hex_fields = dict(HEX_FIELDS if hex_fields is None else hex_fields)
    objs, num = [], 10
    out = [b'%PDF-1.7\n']
    plain = [(n, v) for n, v in fields.items() if n not in IN_STREAM]
    body = [b'1 0 obj\n<< /Type/Catalog /Pages 2 0 R >>\nendobj\n',
            b'2 0 obj\n<< /Type/Pages /Count 1 /Kids[3 0 R] >>\nendobj\n',
            b'3 0 obj\n<< /Type/Page /Parent 2 0 R /MediaBox[0 0 612 792] >>\nendobj\n']
    if with_fields:
        for name, value in plain:
            body.append(b'%d 0 obj\n' % num + widget(name, lit(value)) + b'\nendobj\n'); num += 1
        for name, value in hex_fields.items():
            body.append(b'%d 0 obj\n' % num + widget(name, hexstr(value)) + b'\nendobj\n'); num += 1
        for name, value in INDIRECT.items():
            body.append(b'%d 0 obj\n' % num + b'<<\n/T' + lit(name) + b'\n/V %d 0 R\n>>' % (num + 1) + b'\nendobj\n')
            body.append(b'%d 0 obj\n' % (num + 1) + lit(value) + b'\nendobj\n'); num += 2
        inner = [(n, widget(n, lit(fields[n]))) for n in IN_STREAM if n in fields]
        head, data, nums = [], b'', []
        for name, obj in inner:
            head.append(b'%d %d' % (num, len(data))); data += obj + b'\n'; num += 1
        header = b' '.join(head) + b'\n'
        stream = zlib.compress(header + data)
        body.append(b'%d 0 obj\n<< /Type/ObjStm /N %d /First %d /Filter/FlateDecode /Length %d >>\nstream\n'
                    % (num, len(inner), len(header), len(stream)) + stream + b'\nendstream\nendobj\n')
    else:
        page = zlib.compress(b'BT /F1 12 Tf 72 720 Td (Tamsin Reed Rogue 3) Tj ET')
        body.append(b'%d 0 obj\n<< /Length %d /Filter/FlateDecode >>\nstream\n' % (num, len(page)) + page
                    + b'\nendstream\nendobj\n')
    out += body
    out.append(b'trailer\n<< /Root 1 0 R >>\n%%EOF\n')
    return b''.join(out)

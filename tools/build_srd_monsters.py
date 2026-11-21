"""Build runtime/data/srd_5_1_monsters.json from the 5e-bits/5e-database SRD 5.1 monster list.

Source: https://github.com/5e-bits/5e-database (MIT), file src/2014/en/5e-SRD-Monsters.json.
The numbers are the SRD 5.1 stat blocks (CC-BY-4.0, Wizards of the Coast). Only numbers and
names are kept (no description text), in the combat engine's shape (runtime/kit_combat.py):

    ac, hp, initiative (Dex mod), grapple (Str mod, or Athletics when listed), saves (all six,
    proficient value when listed), stealth (listed, else Dex mod), perception, abilities,
    attacks (one turn's swings: the best weapon attack, repeated for a Multiattack of N),
    with average damage from the damage dice; npc_role on the SRD's NPC templates.

Usage: python3 tools/build_srd_monsters.py <5e-SRD-Monsters.json> [out.json]
Rebuild only when the source changes; the runtime reads the JSON it writes (stdlib only).
"""
import json
import re
import sys
from pathlib import Path

ABIL = (('strength', 'str'), ('dexterity', 'dex'), ('constitution', 'con'),
        ('intelligence', 'int'), ('wisdom', 'wis'), ('charisma', 'cha'))
WORDS = {'two': 2, 'three': 3, 'four': 4, 'five': 5}
VERB = {'bite': 'bites', 'claw': 'rakes', 'claws': 'rakes', 'tail': 'lashes', 'gore': 'gores',
        'tentacle': 'lashes', 'tentacles': 'lashes', 'slam': 'slams', 'fist': 'punches', 'sting': 'stings',
        'hooves': 'kicks', 'talons': 'rakes', 'beak': 'pecks', 'horns': 'gores', 'ram': 'rams'}
BY_TYPE = {'slashing': 'cuts', 'piercing': 'stabs', 'bludgeoning': 'strikes'}
DICE = re.compile(r'^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$')


def mod(score):
    return (int(score) - 10) // 2


def avg(dice):
    m = DICE.match(str(dice or ''))
    if not m:
        return int(dice) if str(dice or '').strip().isdigit() else 0
    n, s = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(4) or 0) * (-1 if m.group(3) == '-' else 1)
    return max(1, n * (s + 1) // 2 + bonus)


def damage_of(action):
    total, kind = 0, None
    for part in action.get('damage') or ():
        if 'choose' in part:  # e.g. versatile one- or two-handed: take the first option
            part = ((part.get('from') or {}).get('options') or [{}])[0]
        dice = part.get('damage_dice')
        if not dice:
            continue
        total += avg(dice)
        kind = kind or ((part.get('damage_type') or {}).get('index'))
    return total, kind


def attack_of(action):
    if type(action.get('attack_bonus')) is not int:
        return None
    dmg, kind = damage_of(action)
    if dmg <= 0 or not kind:
        return None
    name = action['name'].split('(')[0].strip().casefold()
    verb = VERB.get(name) or BY_TYPE.get(kind, 'hits')
    return {'name': name, 'verb': verb, 'to_hit': action['attack_bonus'], 'damage': dmg, 'type': kind}


def swings(monster):
    attacks = [a for a in map(attack_of, monster.get('actions') or ()) if a]
    if not attacks:
        return []
    best = max(attacks, key=lambda a: (a['damage'], a['to_hit']))
    count = 1
    for action in monster.get('actions') or ():
        if action.get('name', '').casefold() == 'multiattack':
            m = re.search(r'\bmakes (two|three|four|five)\b', action.get('desc', ''))
            count = WORDS[m.group(1)] if m else 1
    return [dict(best) for _ in range(count)]


def convert(monster):
    abilities = {short: int(monster.get(long, 10)) for long, short in ABIL}
    prof = {}
    for p in monster.get('proficiencies') or ():
        idx = (p.get('proficiency') or {}).get('index', '')
        prof[idx] = p.get('value')
    saves = {short: prof.get(f'saving-throw-{short}', mod(abilities[short])) for _, short in ABIL}
    ac = monster.get('armor_class')
    ac = ac[0]['value'] if isinstance(ac, list) and ac else int(ac or 10)
    attacks = swings(monster)
    if not attacks or not monster.get('hit_points'):
        return None
    line = {'ac': ac, 'hp': int(monster['hit_points']), 'initiative': mod(abilities['dex']),
            'grapple': prof.get('skill-athletics', mod(abilities['str'])), 'saves': saves,
            'stealth': prof.get('skill-stealth', mod(abilities['dex'])),
            'perception': prof.get('skill-perception', mod(abilities['wis'])),
            'abilities': abilities, 'cr': monster.get('challenge_rating'), 'attacks': attacks}
    if monster.get('type') == 'humanoid' and 'any race' in str(monster.get('subtype') or ''):
        line['npc_role'] = True  # the SRD's NPC templates (Druid, Mage, Noble...): a role word for a person
    return line


def main(src, out):
    data = json.loads(Path(src).read_text(encoding='utf-8'))
    table = {}
    for monster in data:
        line = convert(monster)
        if line:
            table[monster['name'].casefold()] = line
    doc = {'_source': 'SRD 5.1 (CC-BY-4.0, Wizards of the Coast) via 5e-bits/5e-database (MIT), '
                      'numbers only; built by tools/build_srd_monsters.py',
           'creatures': dict(sorted(table.items()))}
    Path(out).write_text(json.dumps(doc, indent=0, sort_keys=False, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(table)} creatures -> {out}')


if __name__ == '__main__':
    here = Path(__file__).resolve().parent.parent
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else here / 'runtime' / 'data' / 'srd_5_1_monsters.json')

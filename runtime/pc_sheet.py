"""Player character sheets: one generic JSON shape for any class, ancestry, and level.

Nothing here knows about any particular character. The claims system
(runtime/kit_claims.py) reads the loaded sheet for passive scores and skill bonuses;
the adjudicator reads it for roll modifiers. Nik (tests/fixtures/characters/nik.json)
is one example sheet, not a special case.

Schema ``character_sheet_v1``:

    name, ancestry, class, level                 who the player is playing
    abilities: {str, dex, con, int, wis, cha}    scores (1-30)
    proficiency_bonus                            +2 to +6
    skills: {skill: total bonus}                 as printed on the sheet (all 18)
    advantage_on: [skill, ...]                   passive +5 (e.g. Sentinel Shield: perception)
    passives: {skill: score}                     optional; printed passives, checked against
                                                 10 + bonus (+5 with advantage)
    extra fields (hp, ac, spells, features, gear) are kept as written and never checked.
"""
from .state_context import require

SCHEMA = 'character_sheet_v1'
ABILITIES = ('str', 'dex', 'con', 'int', 'wis', 'cha')
SKILLS = {
    'acrobatics': 'dex', 'animal_handling': 'wis', 'arcana': 'int', 'athletics': 'str',
    'deception': 'cha', 'history': 'int', 'insight': 'wis', 'intimidation': 'cha',
    'investigation': 'int', 'medicine': 'wis', 'nature': 'int', 'perception': 'wis',
    'performance': 'cha', 'persuasion': 'cha', 'religion': 'int', 'sleight_of_hand': 'dex',
    'stealth': 'dex', 'survival': 'wis',
}


def modifier(score):
    return (score - 10) // 2


def check_sheet(sheet):
    require(isinstance(sheet, dict) and sheet.get('schema') == SCHEMA,
            f'A character sheet needs schema {SCHEMA!r}')
    for key in ('name', 'ancestry', 'class'):
        require(isinstance(sheet.get(key), str) and 0 < len(sheet[key].strip()) <= 60,
                f'Character sheet {key} must be 1-60 characters')
    require(type(sheet.get('level')) is int and 1 <= sheet['level'] <= 20, 'Character level must be 1-20')
    abilities = sheet.get('abilities')
    require(isinstance(abilities, dict) and set(abilities) == set(ABILITIES) and
            all(type(v) is int and 1 <= v <= 30 for v in abilities.values()),
            'Character abilities need str, dex, con, int, wis, cha scores (1-30)')
    require(type(sheet.get('proficiency_bonus')) is int and 2 <= sheet['proficiency_bonus'] <= 6,
            'Character proficiency_bonus must be 2-6')
    skills = sheet.get('skills')
    require(isinstance(skills, dict) and set(skills) <= set(SKILLS) and
            all(type(v) is int and -5 <= v <= 20 for v in skills.values()),
            'Character skills map known skill names to whole bonuses')
    require(set(sheet.get('advantage_on', [])) <= set(SKILLS), 'advantage_on names unknown skills')
    for skill, score in (sheet.get('passives') or {}).items():
        require(skill in SKILLS and type(score) is int, f'Unknown passive {skill!r}')
        require(score == derived_passive(sheet, skill),
                f'Printed passive {skill} {score} does not match 10 + bonus'
                f' ({derived_passive(sheet, skill)}); fix the sheet')
    return sheet


def skill_bonus(sheet, skill):
    """The sheet's printed bonus, else the bare ability modifier."""
    require(skill in SKILLS, f'Unknown skill {skill!r}')
    if skill in (sheet.get('skills') or {}):
        return sheet['skills'][skill]
    return modifier(sheet['abilities'][SKILLS[skill]])


def derived_passive(sheet, skill):
    return 10 + skill_bonus(sheet, skill) + (5 if skill in sheet.get('advantage_on', []) else 0)


def passive(sheet, skill):
    """Passive score (PHB: 10 + bonus, +5 with advantage). Works for any skill."""
    return derived_passive(sheet, skill)


def identity(sheet):
    """The public identity the scene-fit guard and your_character use."""
    return {'name': sheet['name'], 'ancestry': sheet['ancestry'], 'class': sheet['class'],
            'level': sheet['level']}


def private_summary(sheet):
    """What the decision stage sees of the sheet: the numbers the bands come from."""
    return {'name': sheet['name'], 'ancestry': sheet['ancestry'], 'class': sheet['class'],
            'level': sheet['level'], 'abilities': sheet['abilities'],
            'passives': {skill: passive(sheet, skill) for skill in ('perception', 'insight', 'investigation')},
            'skills': sheet.get('skills', {})}

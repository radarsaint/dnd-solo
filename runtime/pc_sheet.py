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
    advantage_on: [skill | {skill, source, while}] passive +5. A bare skill is always on (a
                                                 feature). A conditional entry is on only while
                                                 its condition is true now: while "held" or
                                                 "equipped" (source in that list) or "active"
                                                 (source in `active`: a spell or condition).
                                                 Ownership alone is not holding.
    held, equipped, active: [name, ...]          optional; what is true right now. Not a sheet
                                                 default: the situation sets it (situated(): seated
                                                 at cards, hands on the cards and a shield set
                                                 aside; a fight, weapon, shield, or focus in hand)
                                                 and the player's word overrides it (the decision's
                                                 pc_state, or the CLI, commits a pc_state event).
                                                 An unset list never blocks a roll.
    passives: {skill: score}                     optional; printed passives, checked against
                                                 10 + bonus (+5 with advantage, conditional
                                                 advantage counted either way)
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
    for entry in sheet.get('advantage_on', []):
        skill = entry.get('skill') if isinstance(entry, dict) else entry
        require(skill in SKILLS, 'advantage_on names unknown skills')
        if isinstance(entry, dict):
            require(isinstance(entry.get('source'), str) and entry.get('while') in CONDITIONS,
                    f'Conditional advantage needs a source and while: {"/".join(CONDITIONS)}')
    for key in CONDITIONS:
        require(all(isinstance(v, str) for v in sheet.get(key, [])), f'{key} lists names')
    for skill, score in (sheet.get('passives') or {}).items():
        require(skill in SKILLS and type(score) is int, f'Unknown passive {skill!r}')
        require(score in (derived_passive(sheet, skill), derived_passive(sheet, skill, assume_on=True)),
                f'Printed passive {skill} {score} does not match 10 + bonus'
                f' ({derived_passive(sheet, skill)}); fix the sheet')
    return sheet


def skill_bonus(sheet, skill):
    """The sheet's printed bonus, else the bare ability modifier."""
    require(skill in SKILLS, f'Unknown skill {skill!r}')
    if skill in (sheet.get('skills') or {}):
        return sheet['skills'][skill]
    return modifier(sheet['abilities'][SKILLS[skill]])


CONDITIONS = ('held', 'equipped', 'active')


def condition_true(sheet, name, condition=None):
    """Is this item/spell/condition in force now? Without a named condition, any list counts."""
    folded = (name or '').strip().casefold()
    keys = (condition,) if condition else CONDITIONS
    return bool(folded) and any(folded == v.strip().casefold() for k in keys for v in sheet.get(k, []))


# The situation sets the default PC state; anything the player says overrides it.
# seated: at a table (a card game running here): hands on the cards, held gear set aside,
#         and a shield set aside even if strapped on.
# at_ease: talking or exploring: hands free, worn gear still worn.
# ready: a fight or on guard: weapon, shield, or focus in hand, worn gear worn.
# Spells and conditions are never assumed: active is only what was said or cast.
SITUATIONS = ('seated', 'at_ease', 'ready')


def situation_of(state, fight=False):
    """The situation that sets the default: a fight, else a card game in play, else at ease."""
    if fight:
        return 'ready'
    return 'seated' if (state or {}).get('procedures') else 'at_ease'


def situation_default(sheet, situation):
    """held/equipped/active for this situation, from the sheet's conditional sources."""
    require(situation in SITUATIONS, f'Unknown situation {situation!r}')
    conditional = [e for e in sheet.get('advantage_on', []) if isinstance(e, dict)]

    def sources(condition):
        return [e['source'] for e in conditional if e.get('while') == condition]
    held = sources('held') if situation == 'ready' else []
    equipped = [name for name in sources('equipped')
                if not (situation == 'seated' and 'shield' in name.casefold())]
    return {'held': held, 'equipped': equipped, 'active': []}


def situated(sheet, situation):
    """The sheet as it stands now: lists the player (or the fiction) set, else the situation's
    default. Never None for a loaded sheet, so no roll waits on an unset list."""
    if not sheet:
        return sheet
    default = situation_default(sheet, situation)
    return {**sheet, **{key: list(default[key]) for key in CONDITIONS if key not in sheet}}


def sheet_now(state, fight=False):
    """The loaded sheet with its in-force lists settled by the player's word, else the situation."""
    return situated((state or {}).get('player_sheet'), situation_of(state, fight))


def settled_by(sheet, name):
    """'player' when a list the player (or fiction) set names it; 'situation' when it is one of
    the sheet's conditional sources the situation settles; else None."""
    if any(key in sheet and condition_true(sheet, name, key) for key in CONDITIONS):
        return 'player'
    folded = (name or '').strip().casefold()
    if folded and any(isinstance(e, dict) and e.get('source', '').strip().casefold() == folded
                      for e in sheet.get('advantage_on', [])):
        return 'situation'
    return None


def advantage_sources(sheet, skill):
    """What gives advantage on this skill right now: 'always', or the active sources."""
    found = []
    for entry in sheet.get('advantage_on', []):
        if entry == skill:
            found.append('always')
        elif isinstance(entry, dict) and entry.get('skill') == skill and \
                condition_true(sheet, entry['source'], entry['while']):
            found.append(entry['source'])
    return found


def derived_passive(sheet, skill, assume_on=False):
    on = advantage_sources(sheet, skill) or (assume_on and any(
        isinstance(e, dict) and e.get('skill') == skill for e in sheet.get('advantage_on', [])))
    return 10 + skill_bonus(sheet, skill) + (5 if on else 0)


def passive(sheet, skill):
    """Passive score (PHB: 10 + bonus, +5 with advantage in force now). Any skill."""
    return derived_passive(sheet, skill)


def identity(sheet):
    """The public identity the scene-fit guard and your_character use."""
    return {'name': sheet['name'], 'ancestry': sheet['ancestry'], 'class': sheet['class'],
            'level': sheet['level']}


def private_summary(sheet, situation='at_ease'):
    """What the decision stage sees of the sheet: the numbers the bands come from, with the
    in-force lists as they stand now (the player's word, else the situation's default)."""
    now = situated(sheet, situation)
    return {'name': sheet['name'], 'ancestry': sheet['ancestry'], 'class': sheet['class'],
            'level': sheet['level'], 'abilities': sheet['abilities'],
            'passives': {skill: passive(now, skill) for skill in ('perception', 'insight', 'investigation')},
            'skills': sheet.get('skills', {}),
            'situation': situation,
            'in_force': {key: now[key] for key in CONDITIONS},
            'from_situation': [key for key in CONDITIONS if key not in sheet],
            'conditional_advantage': [e for e in sheet.get('advantage_on', []) if isinstance(e, dict)],
            'advantage_now': {skill: src for skill in SKILLS if (src := advantage_sources(now, skill))}}

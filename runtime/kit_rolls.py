"""Rolls the player reports. Avrae is at every game: players roll there and post the
result, and Kit uses what they report. Kit never rolls for the player.

One rule for every stated number (checks, attacks, initiative, damage):

* Avrae's own line, ``1d20 (12) + 10 = 22`` (also ``2d20kh1 (12, 5) + 10 = 22``, bold or
  backticks): the total is what counts; the kept die is total minus the modifiers.
* ``12 + 10 = 22``: die, modifier, total. It has to add up.
* A bare stated number ("I rolled 17", "Deception 22", "18 to hit", "Initiative 14") is
  the **total** Avrae reported. Kit never adds the bonus to it a second time.
* Only an explicit natural ("natural 17", "nat 17", "the die shows 17") is the d20 alone,
  and then the sheet's bonus is added once.

Each roll is labelled by the words just before or after it: a skill, a save,
``initiative``, ``attack`` ("to hit"), or ``damage``. Deterministic; no dice here.
"""
import re
from dataclasses import dataclass

SKILLS = ('acrobatics', 'animal handling', 'arcana', 'athletics', 'deception', 'history', 'insight',
          'intimidation', 'investigation', 'medicine', 'nature', 'perception', 'performance',
          'persuasion', 'religion', 'sleight of hand', 'stealth', 'survival')
ABILITIES = {'strength': 'str', 'dexterity': 'dex', 'constitution': 'con', 'intelligence': 'int',
             'wisdom': 'wis', 'charisma': 'cha', 'str': 'str', 'dex': 'dex', 'con': 'con', 'int': 'int',
             'wis': 'wis', 'cha': 'cha'}
DAMAGE_TYPES = ('acid', 'bludgeoning', 'cold', 'fire', 'force', 'lightning', 'necrotic', 'piercing',
                'poison', 'psychic', 'radiant', 'slashing', 'thunder')
_SKILL = r'(?:' + '|'.join(s.replace(' ', r'\s+') for s in sorted(SKILLS, key=len, reverse=True)) + r')'
_DTYPE = r'(?:' + '|'.join(DAMAGE_TYPES) + r')'

_AVRAE = re.compile(r'\b\d*d20(?:[kp][hl]\d+)?\s*\(([^)]*)\)\s*((?:[+-]\s*\d+\s*)*)=\s*(-?\d{1,3})\b')
_SUM = re.compile(r'(?<![\d(])\b(\d{1,2})\s*((?:[+-]\s*\d{1,2}\s*)+)=\s*(-?\d{1,3})\b')
_NATURAL = re.compile(r'\b(?:natural|nat|the d20 (?:shows|showed|came up|says)|the die (?:shows|showed|came up)|'
                      r'd20 (?:shows|showed|came up)|d20:?)\s*(?:a\s+|an\s+)?(\d{1,2})\b')
_DAMAGE = re.compile(r'\b(\d{1,3})\s+(?:points?\s+of\s+)?(?:(' + _DTYPE + r')\s+)?(?:damage|dmg)\b'
                     r'|\b(\d{1,3})\s+(' + _DTYPE + r')\b(?!\s+(?:damage|dmg))'
                     r'|\b(?:damage|dmg):?\s+(?:of\s+)?(\d{1,3})\b')
_INIT = re.compile(r'\b(?:initiative|init)\b[^.!?\d\[\]]{0,30}?(?<![\d+-])(\d{1,2})\b(?!\s*(?:[+-]|to[- ]hit|damage|\w+ damage))')
_SKILL_AFTER = re.compile(r'^\s*(?:on|for|in|at)\s+(?:my\s+|the\s+|a\s+)?(' + _SKILL + r')\b')
_ATTACK_AFTER = re.compile(r'^\s*(?:to[- ]hit|to strike|on the attack|for the attack|attack)\b')
_TOTAL = re.compile(r'\b(?:rolled|rolling|roll(?:ed)?:|got|get|total(?:\s+of)?|scored?|came up)\s*'
                    r'(?:(?:a|an|my|the|for|with)\s+){0,2}(?:' + _SKILL + r'\s+(?:check\s+)?)?(?:of\s+)?(\d{1,2})\b'
                    r'|\b(\d{1,2})\s+(?:to[- ]hit|on the attack|for the attack)\b'
                    r'|\b(?:to[- ]hit|attack(?: roll)?|initiative|init)\s*(?:roll\s*)?(?:is|of|was|:|=)?\s*(\d{1,2})\b'
                    r'|\b(' + _SKILL + r'|(?:strength|dexterity|constitution|intelligence|wisdom|charisma)'
                    r'(?:\s+sav(?:e|ing throw))?)\s*(?:check|roll|save|saving throw)?\s*[:=]?\s*(\d{1,2})\b')


@dataclass(frozen=True)
class Roll:
    """One stated roll. ``die`` is None when only the total was given."""
    total: int
    die: int = None
    modifier: int = None
    label: str = None      # a skill (snake_case), '<ability>_save', 'initiative', 'attack'
    form: str = 'total'    # 'avrae' | 'sum' | 'natural' | 'total'
    start: int = 0

    def parts(self, modifier=None):
        """(die, modifier) for a check: the stated split, else the natural plus the sheet's
        bonus, else the total worked back with the sheet's bonus (never added twice)."""
        if self.die is not None and self.modifier is not None:
            return self.die, self.modifier
        if self.die is not None:
            return self.die, modifier
        mod = modifier if modifier is not None else 0
        return self.total - mod, mod


def _clean(text):
    return re.sub(r'[*`_~]+', '', (text or '').translate(str.maketrans({'\u2019': "'", '\u2212': '-'}))).casefold()


def _mods(text):
    return sum(int(part.replace(' ', '')) for part in re.findall(r'[+-]\s*\d+', text or ''))


def _label(text, start, end):
    """The skill, save, initiative, or attack a roll belongs to, from the words around it."""
    before = text[max(0, start - 40):start]
    after = text[end:end + 24]
    if _ATTACK_AFTER.search(after):
        return 'attack'
    named = _SKILL_AFTER.search(after)
    if named:
        return re.sub(r'\s+', '_', named.group(1))
    # the nearest label word before the roll, within its own clause
    clause = re.split(r'[.;!?\]\[]|,\s*(?=\w+\s+\d)', before)[-1]
    found = None
    for match in re.finditer(r'\b(' + _SKILL + r')\b|\b(initiative|init)\b|\b(to[- ]hit|attack)\b|'
                             r'\b(strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)'
                             r'\s+sav(?:e|ing throw)\b', clause):
        found = match
    if not found:
        return None
    if found.group(1):
        return re.sub(r'\s+', '_', found.group(1))
    if found.group(2):
        return 'initiative'
    if found.group(3):
        return 'attack'
    return f'{ABILITIES[found.group(4)]}_save'


def rolls(action):
    """Every d20 roll stated in the action, in order (damage is separate: ``damage``)."""
    text = _clean(action)
    found, taken = [], []

    def free(span):
        return all(span[1] <= a or span[0] >= b for a, b in taken)

    for match in _AVRAE.finditer(text):
        total = int(match.group(3))
        modifier = _mods(match.group(2))
        found.append(Roll(total, total - modifier, modifier, _label(text, match.start(), match.end()), 'avrae',
                          match.start()))
        taken.append(match.span())
    for match in _SUM.finditer(text):
        if not free(match.span()):
            continue
        die, modifier, total = int(match.group(1)), _mods(match.group(2)), int(match.group(3))
        if die + modifier != total or not 1 <= die <= 20:
            from .state_context import InvalidChange
            raise InvalidChange('Supplied roll does not add up')
        found.append(Roll(total, die, modifier, _label(text, match.start(), match.end()), 'sum', match.start()))
        taken.append(match.span())
    for match in _NATURAL.finditer(text):
        if not free(match.span()):
            continue
        die = int(match.group(1))
        if not 1 <= die <= 20:
            from .state_context import InvalidChange
            raise InvalidChange('A natural d20 roll must be 1-20')
        found.append(Roll(die, die, None, _label(text, match.start(), match.end()), 'natural', match.start()))
        taken.append(match.span())
    for match in _INIT.finditer(text):
        if free(match.span(1)):
            found.append(Roll(int(match.group(1)), None, None, 'initiative', 'total', match.start(1)))
            taken.append(match.span(1))
    for match in _TOTAL.finditer(text):
        if not free(match.span()):
            continue
        groups = match.groups()
        if groups[0] is not None:
            value, label = int(groups[0]), _label(text, match.start(), match.end())
            named = re.search(r'\b(' + _SKILL + r')\b', match.group(0))
            if named:
                label = re.sub(r'\s+', '_', named.group(1))
        elif groups[1] is not None:
            value, label = int(groups[1]), 'attack'
        elif groups[2] is not None:
            value = int(groups[2])
            label = 'initiative' if re.search(r'\binit', match.group(0)) else 'attack'
        else:
            name, value = groups[3], int(groups[4])
            word = re.sub(r'\s+', ' ', name.split(' sav')[0].strip())
            label = (f'{ABILITIES[word]}_save' if ' sav' in name else
                     ABILITIES[word] if word in ABILITIES else word.replace(' ', '_'))
        found.append(Roll(value, None, None, label, 'total', match.start()))
        taken.append(match.span())
    return sorted(found, key=lambda roll: roll.start)


def check_roll(action, skill=None):
    """The roll stated for a check: one labelled with ``skill`` if given, else the first
    roll that is not an attack or initiative. None when the player stated none."""
    candidates = [roll for roll in rolls(action) if roll.label not in ('attack', 'initiative')]
    if skill:
        for roll in candidates:
            if roll.label == skill:
                return roll
    return candidates[0] if candidates else None


def stated_skill(action):
    """The skill the player names with a stated roll ("[Deception: I rolled 12 + 4 = 16]",
    "Insight 18"), or None."""
    for roll in rolls(action):
        if roll.label and roll.label not in ('attack', 'initiative') and not roll.label.endswith('_save'):
            return roll.label
    return None


def initiative(action):
    for roll in rolls(action):
        if roll.label == 'initiative':
            return roll.total
    return None


def attack_total(action):
    for roll in rolls(action):
        if roll.label == 'attack':
            return roll.total
    # "I rolled 18" in a line that is plainly an attack and names damage
    if damage(action):
        plain = [roll for roll in rolls(action) if roll.label is None]
        if plain:
            return plain[0].total
    return None


def damage(action):
    """[(amount, damage type or None)] stated in the action."""
    text = _clean(action)
    out = []
    for match in _DAMAGE.finditer(text):
        if match.group(1):
            out.append((int(match.group(1)), match.group(2)))
        elif match.group(3):
            out.append((int(match.group(3)), match.group(4)))
        else:
            out.append((int(match.group(5)), None))
    return out

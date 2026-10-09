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
                    r'(?:\s+sav(?:e|ing throw))?|(?:str|dex|con|int|wis|cha)\s+sav(?:e|ing throw))'
                    r'\s*(?:check|roll|save|saving throw)?\s*[:=]?\s*(\d{1,2})\b')


def meets_or_beats(actor_total, target):
    """Brendon's tie rule (2026-10-04): when a creature acts on another creature, meeting the
    number wins, so the ACTOR wins ties. One rule for every such comparison: an attack against
    AC, a check against a passive score (a monster's Stealth against the PC's passive
    Perception, the PC's Stealth against a monster's), a contest against a flat number."""
    return int(actor_total) >= int(target)


def attacker_wins(dc, save_total):
    """Brendon's save rule (2026-10-04, a house rule over 5e): the attacker must meet or beat
    the defender, so a save that only ties the DC FAILS. Both ways: the PC's save against a
    monster's DC, and a monster's save against the PC's spell save DC. Death saves have no
    attacker and are not this rule (10 or more succeeds)."""
    return int(dc) >= int(save_total)


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


# Avrae's output (bold and backticks already stripped by ``_clean``). A roll's line field
# names what it is ("To Hit: 1d20 (11) + 7 = 18", "Damage: 1d12 (5) + 6 [slashing] = 11",
# "DEX Save: 1d20 (8) + 1 = 9; Failure!", "Initiative: 1d20 (12) + 2 = 14"); a title line
# names the check the next roll belongs to ("Sela makes a Persuasion check!").
_FIELD = re.compile(r'^\s*(?:[^:\n]{1,40}:\s*)?(to[- ]hit|damage(?:\s*\(crit!?\))?|'
                    r'(strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)\s+save|'
                    r'initiative|init)\s*:')
_HEADER = re.compile(r'\bmakes? an?\s+(' + _SKILL + r'|strength|dexterity|constitution|intelligence|wisdom|charisma)'
                     r'\s+(check|save|saving throw)\s*!?')


def _field(text, start):
    """'attack' | 'damage' | '<ability>_save' | 'initiative' | None: the Avrae field of the
    line a roll sits on."""
    line_start = text.rfind('\n', 0, start) + 1
    found = _FIELD.match(text[line_start:start])
    if not found:
        return None
    word = found.group(1)
    if word.startswith('to'):
        return 'attack'
    if word.startswith('damage'):
        return 'damage'
    if word.startswith('init'):
        return 'initiative'
    return f'{ABILITIES[found.group(2)]}_save'


def _header(text, start):
    """The check an Avrae title names for the roll right after it (no other roll between)."""
    before = text[max(0, start - 160):start]
    found = None
    for match in _HEADER.finditer(before):
        found = match
    if not found or re.search(r'=\s*-?\d', before[found.end():]):
        return None
    name, kind = found.group(1), found.group(2)
    name = re.sub(r'\s+', ' ', name)
    if kind == 'check':
        return ABILITIES[name] if name in ABILITIES else name.replace(' ', '_')
    return f'{ABILITIES.get(name, name)}_save'


def _label(text, start, end):
    """The skill, save, initiative, or attack a roll belongs to, from the words around it."""
    field = _field(text, start)
    if field:
        return field
    header = _header(text, start)
    if header:
        return header
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
    return sorted((roll for roll in found if roll.label != 'damage'), key=lambda roll: roll.start)


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
        plain = [roll for roll in rolls(action) if roll.label is None and roll.form != 'avrae']
        if plain:
            return plain[0].total
    return None


_AVRAE_DAMAGE = re.compile(r'^\s*damage(?:\s*\((crit)!?\))?\s*:\s*(.*)$', re.M)
_DC = re.compile(r'\bdc\s*:?\s*(\d{1,2})\b')


def _avrae_damage_line(content):
    """(total, type) from an Avrae damage field: "1d12 (5) + 6 [slashing] = 11", or a
    per-target "28 [fire]"."""
    kind = re.search(r'\[(' + _DTYPE + r')\]', content)
    total = re.search(r'=\s*(\d{1,3})\s*$', content.strip())
    if not total:
        total = re.match(r'\s*(\d{1,3})\b(?!\s*d\d)', content)
    return (int(total.group(1)), kind.group(1) if kind else None) if total else None


def avrae(action):
    """Avrae's attack and spell output, or None when there is none:
    {'damage': [(total, type, target or None)], 'dc': int or None,
     'targets': {name: {'save': (ability, total, success) or None, 'damage': (total, type) or None}}}.
    A line that is not a field or a title starts a target section (Avrae puts each target's
    save and damage under its name)."""
    text = _clean(action)
    if not _AVRAE_DAMAGE.search(text) and not re.search(r'^\s*(?:\w+\s+)?save\s*:', text, re.M):
        return None
    out = {'damage': [], 'dc': None, 'targets': {}}
    dc = _DC.search(text)
    out['dc'] = int(dc.group(1)) if dc else None
    target = None
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        damage_field = _AVRAE_DAMAGE.match(line)
        save = re.match(r'\s*(strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)'
                        r'\s+save\s*:\s*(.*)$', line)
        if damage_field:
            found = _avrae_damage_line(damage_field.group(2))
            if found:
                out['damage'].append((found[0], found[1], target))
                if target:
                    out['targets'].setdefault(target, {'save': None, 'damage': None})['damage'] = found
        elif save:
            total = re.search(r'=\s*(-?\d{1,3})', save.group(2))
            success = re.search(r'\b(success|failure|fail)\b', save.group(2))
            if target and total:
                out['targets'].setdefault(target, {'save': None, 'damage': None})['save'] = (
                    ABILITIES[save.group(1)], int(total.group(1)),
                    None if not success else success.group(1) == 'success')
        elif ':' in stripped or stripped.endswith('!') or re.match(r'^(meta|effect|dc\b)', stripped) or \
                re.search(r'\d', stripped) or len(stripped) > 40:
            continue
        else:
            target = stripped
    return out


def damage(action):
    """[(amount, damage type or None)] stated in the action. Avrae's damage fields win;
    numbers inside a roll expression or a to-hit line are never damage."""
    found = avrae(action)
    if found and found['damage']:
        return [(amount, kind) for amount, kind, _ in found['damage']]
    text = _clean(action)
    text = _AVRAE.sub(' ', text)
    text = '\n'.join(line for line in text.split('\n') if _field(line + ' ', len(line)) != 'attack')
    out = []
    for match in _DAMAGE.finditer(text):
        if match.group(1):
            out.append((int(match.group(1)), match.group(2)))
        elif match.group(3):
            out.append((int(match.group(3)), match.group(4)))
        else:
            out.append((int(match.group(5)), None))
    return out


# -- number words ("twenty" is 20, "twenty-five" is 25, "a hundred" is 100) ----------------
_UNITS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
          'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
          'seventeen': 17, 'eighteen': 18, 'nineteen': 19}
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80,
         'ninety': 90}
_NUMBER_WORD = re.compile(
    r"\b(?:(a|one|two|three|four|five|six|seven|eight|nine)\s+hundred(?:\s+(?:and\s+)?)?)?"
    r"(?:(" + '|'.join(_TENS) + r")(?:[- ](" + '|'.join(k for k in _UNITS if _UNITS[k] < 10) + r"))?|"
    r"(" + '|'.join(sorted(_UNITS, key=len, reverse=True)) + r"))?\b")


def number_words(text):
    """[(value, start, end)] for every number written in words or digits in ``text``.
    "twenty-one" is 21 (callers that mean the game check for it themselves)."""
    found = []
    for match in re.finditer(r'\b\d{1,4}\b', text):
        found.append((int(match.group(0)), match.start(), match.end()))
    for match in _NUMBER_WORD.finditer(text.casefold()):
        if not match.group(0).strip():
            continue
        hundreds, tens, unit_after, unit = match.groups()
        value = 0
        if hundreds:
            value += 100 * (1 if hundreds == 'a' else _UNITS[hundreds])
        if tens:
            value += _TENS[tens] + (_UNITS[unit_after] if unit_after else 0)
        elif unit:
            value += _UNITS[unit]
        if value:
            found.append((value, match.start(), match.end()))
    return sorted(found, key=lambda item: item[1])


_DICE_TERM = r'\d*d\d+(?:[a-z]{1,3}\d+)*(?:\s*\([^)]*\))?'
_DICE_EXPR = re.compile(r'\b' + _DICE_TERM + r'(?:\s*\[[^\]]*\])?'
                        r'(?:\s*[+-]\s*(?:' + _DICE_TERM + r'|\d+)(?:\s*\[[^\]]*\])?)*'
                        r'(?:\s*/\s*\d+)?(?:\s*=\s*-?\d{1,3}\b)?')


# Avrae's title lines: "Wren makes an Investigation check!", "Brakka attacks with a Greataxe!",
# "Nik casts Fireball!".
AVRAE_TITLE = re.compile(r"^[^\n!?.]{1,40}?\b(?:makes? an?\s+[a-z' ]{3,30}\s+(?:check|save|saving throw)|"
                         r"attacks? with an?\s+[^\n!]{1,40}|casts?\s+[^\n!]{1,40})!\s*$", re.M | re.I)


def without_rolls(text):
    """``text`` with every stated roll removed (Avrae output, dice notation, sums, naturals,
    totals, initiative, bracketed reports), so a die face, a modifier, or a total is never
    read as a bet, an offer, or an amount. Avrae's output goes as one pattern: its field
    lines (To Hit / Damage / <ABIL> Save / Initiative / DC) whole, and any dice expression
    ("1d20 (12) + 3 = 15", "2d20kh1 (13, 4) + 7 = 20", "8d6 (4, 3, ...) [fire] = 28", "1d20")."""
    text = _clean(text)
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    text = '\n'.join(' ' if _FIELD.match(line) or re.match(r'\s*dc\s*:', line) else line
                     for line in text.split('\n'))
    text = _DICE_EXPR.sub(' ', text)
    for pattern in (_AVRAE, _SUM, _NATURAL, _INIT, _TOTAL):
        # "I've got 20 gold" is money, not a roll: a number followed by a coin word stays.
        text = pattern.sub(lambda m: m.group(0) if re.match(r'\s*(?:gp|gold|coins?|sp|cp|pp)\b',
                                                             text[m.end():]) else ' ', text)
    return text


def damage_total(action):
    """(total, type) the blow or spell deals. Avrae: the untargeted (rolled) damage field,
    else the largest per-target one (the full roll on a failed save). Plain words: the sum."""
    found = avrae(action)
    if found and found['damage']:
        untargeted = [(a, k) for a, k, t in found['damage'] if t is None]
        amount, kind = untargeted[0] if untargeted else max(((a, k) for a, k, _ in found['damage']),
                                                            key=lambda item: item[0])
        return amount, kind
    items = damage(action)
    return (sum(a for a, _ in items), next((k for _, k in items if k), None)) if items else (0, None)

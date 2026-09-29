"""Brendon's deterministic magic item price formula (2026-09-29), implemented as written.

Source: Brendon's rules (research/kit-aliveness/05-brendon-price-formula.md), summarized:

1. Impact, the numerical points an item changes in play:
   damage/healing = average roll (2d4+2 = 7, 8d6 = 28); weapon bonus = bonus x 24 per
   level; charged = average effect x charges (wand of fireballs: 28 x 7 = 196);
   consumable = total effect of its single use (potion of healing 2d4+2 = 7); utility
   uses fixed values only (minor situational trick 4, reusable utility effect 6, broad
   multi-purpose utility 8). Area of effect: 4x impact regardless of size, applied
   before gold per impact.
2. Rarity band by entry level: Common 1-4, Uncommon 5-8, Rare 9-12, Very Rare 13-16.
   Once priced, an item always keeps that price (the canon ledger stores it).
3. Exactly one category: Consumable, Weapon/Armor Upgrade, Utility, Complex Multi-Ability.
4. Gold per impact (GPI) by band and category (table below).
5. Price = impact x GPI, rounded to the nearest clean shop value (360 -> 400).
   An official DMG price, when the item data carries one, overrides the formula.

Two choices the rules leave open, both explicit inputs with documented defaults, and
both flagged for Brendon's confirmation:

- ``levels`` for a weapon bonus ("24 successful attacks per level"): how many levels
  the item stays in circulation. Default ``DEFAULT_WEAPON_LEVELS = 4``, one rarity band.
- ``clean_price``: "nearest clean shop value". Default: under 100 gp, nearest 10; 100 to
  999 gp, nearest 100 (so 360 -> 400); 1,000 to 9,999 gp, nearest 500; 10,000 gp and up,
  nearest 1,000. Halves round up.

Magic items only. Mundane goods, food, drink, lodging, and services never use this
formula: they come from the source or the SRD 5.1 tables, or stay unpriced. The full
precedence lives in runtime/kit_prices.py.
"""
import re

from .state_context import require

BANDS = (('Common', 1, 4), ('Uncommon', 5, 8), ('Rare', 9, 12), ('Very Rare', 13, 16))
CATEGORIES = ('Consumable', 'Weapon/Armor Upgrade', 'Utility', 'Complex Multi-Ability')
GPI = {
    'Common': {category: 10 for category in CATEGORIES},
    'Uncommon': {'Consumable': 30, 'Weapon/Armor Upgrade': 50, 'Utility': 60, 'Complex Multi-Ability': 80},
    'Rare': {'Consumable': 80, 'Weapon/Armor Upgrade': 120, 'Utility': 150, 'Complex Multi-Ability': 200},
    'Very Rare': {'Consumable': 200, 'Weapon/Armor Upgrade': 300, 'Utility': 400,
                  'Complex Multi-Ability': 500},
}
UTILITY_VALUES = {'minor': 4, 'reusable': 6, 'broad': 8}
UTILITY_LABELS = {'minor': 'minor situational trick', 'reusable': 'reusable utility effect',
                  'broad': 'broad multi-purpose utility'}
IMPACT_KINDS = ('damage_healing', 'weapon_bonus', 'charged', 'consumable', 'utility')
ATTACKS_PER_LEVEL = 24
AOE_MULTIPLIER = 4
DEFAULT_WEAPON_LEVELS = 4  # one rarity band of levels; needs Brendon's confirmation
_DICE = re.compile(r'^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$', re.I)


def average_roll(dice):
    """Average of an 'NdM+K' expression, as Brendon counts it: 2d4+2 = 7, 8d6 = 28."""
    found = _DICE.match(dice or '')
    require(found is not None, f'Dice must read like 2d4+2, not {dice!r}')
    count, sides = int(found.group(1)), int(found.group(2))
    require(count >= 1 and sides >= 2, 'Dice need at least one die with two sides')
    bonus = int(found.group(4) or 0) * (-1 if found.group(3) == '-' else 1)
    average = count * (sides + 1) / 2 + bonus
    require(average == int(average), f'{dice} has a fractional average; state a whole-number impact')
    return int(average)


def rarity_band(entry_level):
    """Common 1-4, Uncommon 5-8, Rare 9-12, Very Rare 13-16."""
    require(type(entry_level) is int and 1 <= entry_level <= 16,
            'Entry level must be 1-16 (Common 1-4, Uncommon 5-8, Rare 9-12, Very Rare 13-16)')
    return next(band for band, low, high in BANDS if low <= entry_level <= high)


def clean_price(gp):
    """Nearest clean shop value (default rule; needs Brendon's confirmation)."""
    require(gp >= 0, 'A price cannot be negative')
    step = 10 if gp < 100 else 100 if gp < 1000 else 500 if gp < 10000 else 1000
    return max(step, ((gp + step // 2) // step) * step) if gp else 0


def impact(spec):
    """(impact points, human-readable calculation) for an item spec."""
    kind = spec.get('impact_kind')
    require(kind in IMPACT_KINDS, f'impact_kind must be one of {", ".join(IMPACT_KINDS)}')
    if kind in ('damage_healing', 'consumable'):
        value = average_roll(spec['dice'])
        label = 'single use' if kind == 'consumable' else 'average roll'
        text = f'{spec["dice"]} = {value} ({label})'
    elif kind == 'charged':
        per = average_roll(spec['dice'])
        charges = spec.get('charges')
        require(type(charges) is int and charges > 0, 'A charged item needs a positive charge count')
        value = per * charges
        text = f'{spec["dice"]} = {per} x {charges} charges = {value}'
    elif kind == 'weapon_bonus':
        bonus = spec.get('bonus')
        levels = spec.get('levels', DEFAULT_WEAPON_LEVELS)
        require(type(bonus) is int and bonus > 0, 'A weapon bonus must be a positive whole number')
        require(type(levels) is int and levels > 0, 'Levels in circulation must be a positive whole number')
        per_level = bonus * ATTACKS_PER_LEVEL
        value = per_level * levels
        text = f'+{bonus} x {ATTACKS_PER_LEVEL} = {per_level}/level x {levels} levels = {value}'
    else:
        utility = spec.get('utility')
        require(utility in UTILITY_VALUES, 'utility must be minor, reusable, or broad')
        value = UTILITY_VALUES[utility]
        text = f'{UTILITY_LABELS[utility]} {value}'
    if spec.get('aoe'):
        text = f'{text}; area of effect x{AOE_MULTIPLIER} = {value * AOE_MULTIPLIER}'
        value *= AOE_MULTIPLIER
    return value, text


def price(spec):
    """The formula's price for one magic item. Returns the trace fields in Brendon's
    output format plus 'amount' and 'unit'. An official DMG price overrides."""
    require(isinstance(spec, dict) and isinstance(spec.get('item'), str) and spec['item'].strip(),
            'Price spec needs the item name')
    band = rarity_band(spec.get('entry_level'))
    category = spec.get('category')
    require(category in CATEGORIES, f'category must be exactly one of {", ".join(CATEGORIES)}')
    value, calculation = impact(spec)
    gpi = GPI[band][category]
    raw = value * gpi
    official = spec.get('official_price_gp')
    if type(official) is int and official > 0:
        final, note = official, f'{official} gp (official DMG price overrides formula {raw} gp)'
    else:
        final = clean_price(raw)
        note = f'{value} x {gpi} = {raw} -> {final} gp'
    return {'item': spec['item'].strip(), 'impact_calculation': calculation, 'rarity_band': band,
            'item_category': category, 'gold_per_impact': gpi, 'final_price': note,
            'amount': final, 'unit': 'gp', 'basis': 'Brendon price formula v1'}


def trace_text(result):
    """Brendon's output format, one field per line, for the host's trace."""
    return '\n'.join((f'Item: {result["item"]}', f'Impact Calculation: {result["impact_calculation"]}',
                      f'Rarity Band: {result["rarity_band"]}', f'Item Category: {result["item_category"]}',
                      f'Gold Per Impact: {result["gold_per_impact"]}', f'Final Price: {result["final_price"]}'))

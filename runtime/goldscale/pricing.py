# Vendored verbatim from radarsaint/goldscale@a0a18c6 goldscale/pricing.py (Brendon's Goldscale bot).
# Only change: package imports made relative. Do not edit here; re-vendor from Goldscale.
import re
from dataclasses import dataclass
from typing import Optional

from .parser import FORMULA_CATEGORY_DISPLAY, ItemData, UTILITY_IMPACT


RARITY_GPI = {
    "common": {
        "consumable": 10,
        "weapon / armor": 10,
        "utility": 10,
        "complex": 10,
    },
    "uncommon": {
        "consumable": 30,
        "weapon / armor": 50,
        "utility": 60,
        "complex": 80,
    },
    "rare": {
        "consumable": 80,
        "weapon / armor": 120,
        "utility": 150,
        "complex": 200,
    },
    "very rare": {
        "consumable": 200,
        "weapon / armor": 300,
        "utility": 400,
        "complex": 500,
    },
}


@dataclass
class PricingResult:
    item_name: str
    impact: float
    impact_math: str
    rarity: str
    category: str
    gpi: int
    list_price: int
    final_price: int
    mode: str
    sell_rate: Optional[float]
    quantity: Optional[int]
    transaction_total: Optional[int]
    read_as: str
    warnings: list[str]


def average_dice(expr: str) -> float:
    expr = expr.lower().replace(" ", "")
    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", expr)

    if not match:
        raise ValueError("Invalid dice expression.")

    count = int(match.group(1))
    sides = int(match.group(2))
    modifier = int(match.group(3) or 0)

    return count * ((sides + 1) / 2) + modifier


def clean_shop_value(value: float) -> int:
    if value < 100:
        step = 5
    elif value < 1000:
        step = 25
    elif value < 10000:
        step = 100
    else:
        step = 500

    return int(round(value / step) * step)


def has_impact(data: ItemData) -> bool:
    if data.complex_partial_bonus:
        return False

    return any([
        data.bonus is not None,
        data.damage is not None,
        data.healing is not None,
        data.utility is not None,
    ])


def missing_fields(data: ItemData) -> list[str]:
    missing = []

    if data.rejection_error:
        missing.append(data.rejection_error)
        return missing

    if data.sell_rate_error:
        if data.sell_rate_error == "Sell rate must be between 1% and 100%.":
            missing.append("Sell rate: must be between 1% and 100%")
        else:
            missing.append("Sell rate: include the percent sign")

    if data.unsupported_rarity:
        missing.append(f"Rarity: {data.unsupported_rarity} is outside this formula. Use common, uncommon, rare, or very rare.")
        return missing

    if not data.rarity:
        missing.append("Rarity: common, uncommon, rare, or very rare")

    if not (data.formula_category or data.category):
        missing.append("Item type: wand, staff, potion, scroll, weapon, armor, shield, ring, cloak, wondrous item, or charged item")

    if not has_impact(data):
        if data.complex_partial_bonus:
            missing.append("What the magic item changes: found a +bonus on a charged item, but that is probably not the whole item. Choose dice like 8d6 or a utility strength: minor, reusable, or broad")
        elif data.randomized:
            missing.append("Utility strength: choose minor, reusable, or broad")
        else:
            missing.append("What the magic item changes: +1/+2/+3, dice like 8d6, healing like 2d4+2 healing, or utility strength: minor/reusable/broad")

    return missing


def calculate_price(data: ItemData) -> PricingResult:
    from .formatting import read_as_block

    missing = missing_fields(data)
    if missing:
        raise ValueError("missing fields")

    item_name = data.item_name or "Unnamed Item"
    quantity = data.quantity if data.quantity and data.quantity > 1 else None

    rarity = data.rarity
    category = data.formula_category or data.category

    if rarity not in RARITY_GPI:
        raise ValueError("Rarity must be Common, Uncommon, Rare, or Very Rare.")

    if category not in RARITY_GPI[rarity]:
        raise ValueError("Category must be Consumable, Weapon, Armor, Utility, or Complex.")

    if data.bonus is not None:
        impact = data.bonus * 24
        impact_math = f"{data.bonus} × 24 = {impact} impact per level"

    elif data.damage is not None or data.healing is not None:
        expr = data.damage or data.healing
        avg = average_dice(expr)

        if data.aoe and data.charges:
            impact = avg * 4 * data.charges
            impact_math = f"{expr} average = {avg:g}; AoE ×4; charges ×{data.charges}; {avg:g} × 4 × {data.charges} = {impact:g}"
        elif data.aoe:
            impact = avg * 4
            impact_math = f"{expr} average = {avg:g}; AoE ×4; {avg:g} × 4 = {impact:g}"
        elif data.charges:
            impact = avg * data.charges
            impact_math = f"{expr} average = {avg:g}; charges ×{data.charges}; {avg:g} × {data.charges} = {impact:g}"
        else:
            impact = avg
            impact_math = f"{expr} average = {avg:g} impact"

    elif data.utility is not None:
        utility_impact = UTILITY_IMPACT[data.utility]

        if data.charges:
            impact = utility_impact * data.charges
            impact_math = f"{data.utility.title()} utility = {utility_impact} impact; charges ×{data.charges}; {utility_impact} × {data.charges} = {impact} impact"
        else:
            impact = utility_impact
            impact_math = f"{data.utility.title()} utility = {impact} impact"

    else:
        raise ValueError("Description needs +1/+2/+3, damage, healing, or a utility tier.")

    gpi = RARITY_GPI[rarity][category]
    list_price = clean_shop_value(impact * gpi)

    final_price = list_price
    if data.mode == "sell":
        final_price = clean_shop_value(list_price * (data.sell_rate or 0.50))

    transaction_total = final_price * quantity if quantity else None

    return PricingResult(
        item_name=item_name,
        impact=impact,
        impact_math=impact_math,
        rarity=rarity.title(),
        category=FORMULA_CATEGORY_DISPLAY[category],
        gpi=gpi,
        list_price=list_price,
        final_price=final_price,
        mode=data.mode,
        sell_rate=data.sell_rate,
        quantity=quantity,
        transaction_total=transaction_total,
        read_as=read_as_block(data),
        warnings=data.warnings,
    )

# Vendored verbatim from radarsaint/goldscale@a0a18c6 goldscale/clarification.py (Brendon's Goldscale bot).
# Only change: package imports made relative. Do not edit here; re-vendor from Goldscale.
import re
from dataclasses import dataclass
from time import time
from typing import Optional

from .formatting import format_missing, format_result, should_request_description
from .parser import ItemData, find_aoe, find_damage_or_healing, parse_item_text, title_item_name
from .pricing import calculate_price, has_impact, missing_fields


PENDING_TTL_SECONDS = 300


PendingKey = tuple[Optional[int], int, int]


@dataclass
class PendingAppraisal:
    raw: str
    question_kind: str
    created_at: float


class PendingAppraisals:
    def __init__(self, ttl_seconds: int = PENDING_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._items: dict[PendingKey, PendingAppraisal] = {}

    def set(self, key: PendingKey, raw: str, question_kind: str, now: Optional[float] = None) -> None:
        self._items[key] = PendingAppraisal(raw=raw, question_kind=question_kind, created_at=time() if now is None else now)

    def get(self, key: PendingKey, now: Optional[float] = None) -> Optional[PendingAppraisal]:
        pending = self._items.get(key)
        if not pending:
            return None

        current = time() if now is None else now
        if current - pending.created_at > self.ttl_seconds:
            self._items.pop(key, None)
            return None

        return pending

    def clear(self, key: PendingKey) -> bool:
        return self._items.pop(key, None) is not None


def render_pricing_or_missing(data: ItemData) -> str:
    try:
        return format_result(calculate_price(data))
    except ValueError as error:
        if str(error) == "missing fields":
            return format_missing(data)
        raise


def classify_question(data: ItemData, raw: str) -> Optional[str]:
    if data.formula_category_conflict:
        return "category_conflict"

    if data.rejection_error:
        return None

    if should_request_description(data):
        return "description"

    lower = raw.lower()
    if data.spell_reference and not has_impact(data):
        return "spell_description"

    if data.has_description_text and "bead" in lower and "fireball" in lower and not (data.damage or data.healing):
        return "beads_damage"

    if data.spell_effect_without_dice and not has_impact(data):
        return "dice"

    if data.randomized and data.has_description_text and not has_impact(data):
        return "utility"

    missing = missing_fields(data)
    if any(item.startswith("Rarity:") for item in missing):
        return "rarity"

    if any(item.startswith("Item type:") for item in missing):
        return "item_type"

    if not has_impact(data) and (data.formula_category == "utility" or data.item_type_found in {"wondrous item", "ring", "cloak", "boots", "bag", "jug"}):
        return "utility"

    return None


def has_item_type_after_rarity(raw: str) -> bool:
    lower = raw.lower()
    return bool(
        re.search(
            r"\b(?:common|uncommon|rare|very\s+rare|veryrare|vr)\b[\s,]+(?:weapon|armor|shield|potion|scroll|wand|staff|ring|cloak|wondrous item|charged item)\b",
            lower,
        )
    )


def should_confirm_item_type_before_pricing(data: ItemData, raw: str) -> bool:
    return bool(
        data.bonus is not None
        and data.rarity
        and data.formula_category == "weapon / armor"
        and data.item_type_found in {"sword", "longsword", "shortsword", "greatsword", "dagger", "axe", "battleaxe", "greataxe", "mace", "spear", "bow", "longbow", "shortbow", "crossbow", "quarterstaff"}
        and not has_item_type_after_rarity(raw)
    )


def clarification_question(data: ItemData, question_kind: str) -> str:
    name = data.item_name or "that item"

    if question_kind == "description":
        return f"""
I found **{name}**, but I need the item description before I can price it.

Paste the item text from Avrae or D&D Beyond after:
```text
?gs buy
```
""".strip()

    if question_kind == "rarity":
        return """
What rarity is this item?
1. Common
2. Uncommon
3. Rare
4. Very Rare
Reply with 1-4.
""".strip()

    if question_kind == "item_type":
        return """
What kind of magic item is this?
1. Weapon or armor
2. Potion, scroll, or ammunition
3. Wand, staff, or charged item
4. Ring, cloak, boots, or wondrous item
Reply with 1-4.
""".strip()

    if question_kind == "utility":
        return """
How useful should this item count in your campaign?
1. Minor, small or situational
2. Reusable, useful repeatable effect
3. Broad, flexible or broadly useful
Reply with 1-3.
""".strip()

    if question_kind == "category_conflict":
        return """
I found mixed signals. How should Goldscale price it?
1. Utility item, use minor/reusable/broad
2. Multi-use charged item, use damage/healing dice and charges
Reply with 1 or 2.
""".strip()

    if question_kind == "beads_damage":
        return f"""
I found **{name}**, but I need two details before I can price it.

How many beads should I price, and what damage dice should I use?
""".strip()

    if question_kind == "spell_description":
        spell = title_item_name(data.spell_reference or "the spell")
        details = []
        if data.rarity:
            item_type = data.item_type_found or "item"
            details.append(f"{data.rarity.title()} {item_type}")
        if data.charges:
            details.append(f"{data.charges} charges")
        if data.spell_reference:
            details.append(f"Spell reference: {data.spell_reference}")

        found = "\n".join(details)
        if found:
            found = f"\n\nI found:\n{found}"

        return f"""
I found **{name}**.{found}

I need the spell description before I can price the spell effect.
Paste the {spell} spell text.
""".strip()

    if question_kind == "dice":
        return "I found a spell effect, but no damage or healing dice.\nAdd the dice manually, or paste a description that includes them."

    return format_missing(data)


def start_appraisal(raw: str, key: PendingKey, pending: PendingAppraisals, now: Optional[float] = None) -> str:
    data = parse_item_text(raw)

    if data.formula_category_conflict:
        pending.set(key, raw, "category_conflict", now=now)
        return clarification_question(data, "category_conflict")

    if should_confirm_item_type_before_pricing(data, raw):
        pending.set(key, raw, "item_type", now=now)
        return clarification_question(data, "item_type")

    try:
        return format_result(calculate_price(data))
    except ValueError as error:
        if str(error) != "missing fields":
            raise

    question_kind = classify_question(data, raw)
    if not question_kind:
        return format_missing(data)

    pending.set(key, raw, question_kind, now=now)
    return clarification_question(data, question_kind)


def parse_rarity_answer(answer: str, allow_numbers: bool = False) -> Optional[str]:
    lower = answer.lower()
    if allow_numbers:
        numbered = {
            "1": "common",
            "2": "uncommon",
            "3": "rare",
            "4": "very rare",
        }
        if normalize_choice(answer) in numbered:
            return numbered[normalize_choice(answer)]

    if re.search(r"\bvery\s+rare\b|\bveryrare\b|\bvr\b", lower):
        return "very rare"
    for rarity in ("uncommon", "common", "rare"):
        if re.search(rf"\b{rarity}\b", lower):
            return rarity
    return None


def parse_item_type_answer(answer: str, allow_numbers: bool = False) -> tuple[Optional[str], Optional[str]]:
    lower = answer.lower()
    if allow_numbers:
        numbered = {
            "1": ("weapon", "weapon / armor"),
            "2": ("potion", "consumable"),
            "3": ("charged item", "complex"),
            "4": ("wondrous item", "utility"),
        }
        choice = normalize_choice(answer)
        if choice in numbered:
            return numbered[choice]

    mapping = {
        "charged item": "complex",
        "multi-use item": "complex",
        "weapon": "weapon / armor",
        "armor": "weapon / armor",
        "shield": "weapon / armor",
        "potion": "consumable",
        "scroll": "consumable",
        "ammunition": "consumable",
        "wand": "complex",
        "staff": "complex",
        "ring": "utility",
        "cloak": "utility",
        "boots": "utility",
        "wondrous item": "utility",
    }

    for item_type, category in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(item_type)}\b", lower):
            return item_type, category
    return None, None


def parse_utility_answer(answer: str, allow_numbers: bool = False) -> Optional[str]:
    lower = answer.lower()
    if allow_numbers:
        numbered = {
            "1": "minor",
            "2": "reusable",
            "3": "broad",
        }
        if normalize_choice(answer) in numbered:
            return numbered[normalize_choice(answer)]

    for tier in ("minor", "reusable", "broad"):
        if re.search(rf"\b{tier}\b", lower):
            return tier
    return None


def normalize_choice(answer: str) -> str:
    return answer.strip().strip(".").lower()


def valid_closed_choice(pending: PendingAppraisal, answer: str) -> bool:
    if pending.question_kind == "rarity":
        return parse_rarity_answer(answer, allow_numbers=True) is not None
    if pending.question_kind == "item_type":
        return parse_item_type_answer(answer, allow_numbers=True) != (None, None)
    if pending.question_kind == "utility":
        return parse_utility_answer(answer, allow_numbers=True) is not None
    if pending.question_kind == "category_conflict":
        return normalize_choice(answer) in {"1", "2", "utility", "utility item", "charged item", "multi-use charged item", "multi-use item"}
    return True


def invalid_choice_message(question_kind: str) -> str:
    if question_kind in {"rarity", "item_type"}:
        return "I need one of the listed choices. Reply with 1-4."
    if question_kind == "utility":
        return "I need one of the listed choices. Reply with 1-3."
    if question_kind == "category_conflict":
        return "I need one of the listed choices. Reply with 1 or 2."
    return "I need one of the listed choices."


def clarified_utility_raw(data: ItemData) -> str:
    mode = data.mode or "buy"
    name = data.item_name or "item"
    rarity = data.rarity or ""
    item_type = data.item_type_found or "wondrous item"
    return " ".join(part for part in (mode, name, rarity, item_type) if part)


def parse_dice_answer(answer: str) -> tuple[Optional[str], Optional[str]]:
    match = re.search(r"\b\d+d\d+(?:\s*[+-]\s*\d+)?\b", answer.lower())
    if not match:
        return None, None

    expr = match.group(0).replace(" ", "")
    window = answer.lower()[max(0, match.start() - 40): match.end() + 40]
    if any(term in window for term in ("heal", "healing", "hit points")):
        return None, expr
    return expr, None


def parse_count_answer(answer: str, allow_bare: bool = False) -> Optional[int]:
    match = re.search(r"\b(\d+)\s+(?:charges?|uses?|beads?)\b", answer.lower())
    if match:
        return int(match.group(1))
    if allow_bare:
        without_dice = re.sub(r"\b\d+d\d+(?:\s*[+-]\s*\d+)?\b", " ", answer.lower())
        match = re.search(r"\b(\d+)\b", without_dice)
        if match:
            return int(match.group(1))
    return None


ONGOING_SPELL_MARKERS = [
    "starts its turn",
    "enters the area",
    "for the first time on a turn",
    "duration",
    "concentration",
    "each round",
    "repeats",
    "at the start of",
    "at the end of",
]


def has_ongoing_spell_effect(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in ONGOING_SPELL_MARKERS)


def apply_spell_description(data: ItemData, answer: str) -> ItemData:
    damage, healing = find_damage_or_healing(answer)
    if damage:
        data.damage = damage
    if healing:
        data.healing = healing

    data.aoe = find_aoe(answer)

    if (damage or healing) and has_ongoing_spell_effect(answer):
        warning = (
            "Ongoing spell effect detected. Goldscale used one damage instance because "
            "duration/repeated damage is outside the current formula."
        )
        if warning not in data.warnings:
            data.warnings.append(warning)

    return data


def apply_answer(data: ItemData, pending: PendingAppraisal, answer: str) -> ItemData:
    if pending.question_kind == "spell_description":
        data = apply_spell_description(data, answer)

    if pending.question_kind == "category_conflict":
        choice = normalize_choice(answer)
        data.rejection_error = None
        data.formula_category_conflict = None
        if choice in {"2", "charged item", "multi-use charged item", "multi-use item"}:
            data.item_type_found = "charged item"
            data.item_type_source = 'from clarification "charged item"'
            data.formula_category = "complex"
            data.formula_category_source = 'from clarification "charged item"'
            data.formula_category_confidence = "clarified"
            data.category = data.formula_category
            data.category_source = data.formula_category_source
            return data

        data.formula_category = "utility"
        data.formula_category_source = 'from clarification "utility item"'
        data.formula_category_confidence = "clarified"
        data.damage = None
        data.healing = None
        data.charges = None
        data.aoe = False
        data.category = data.formula_category
        data.category_source = data.formula_category_source

    rarity = parse_rarity_answer(answer, allow_numbers=pending.question_kind == "rarity")
    if rarity:
        data.rarity = rarity

    item_type, formula_category = parse_item_type_answer(answer, allow_numbers=pending.question_kind == "item_type")
    if item_type:
        data.item_type_found = item_type
        data.item_type_source = f'from clarification "{item_type}"'
        data.formula_category = formula_category
        data.formula_category_source = f'from clarification "{item_type}"'
        data.formula_category_confidence = "clarified"

    utility = parse_utility_answer(answer, allow_numbers=pending.question_kind == "utility")
    if utility:
        data.utility = utility

    damage, healing = parse_dice_answer(answer)
    if damage:
        data.damage = damage
    if healing:
        data.healing = healing

    count = parse_count_answer(answer, allow_bare=pending.question_kind == "beads_damage" and damage is not None)
    if count:
        data.charges = count

    if pending.question_kind == "beads_damage":
        data.item_type_found = "charged item"
        data.item_type_source = 'from clarification "charged item"'
        data.formula_category = "complex"
        data.formula_category_source = 'from clarification "charged item"'
        data.formula_category_confidence = "clarified"
        if damage and "fireball" in pending.raw.lower():
            data.aoe = True

    data.category = data.formula_category
    data.category_source = data.formula_category_source

    return data


def continue_appraisal(
    answer: str,
    key: PendingKey,
    pending_store: PendingAppraisals,
    now: Optional[float] = None,
) -> Optional[str]:
    pending = pending_store.get(key, now=now)
    if not pending:
        return None

    if pending.question_kind == "description":
        pending_store.clear(key)
        return start_appraisal(answer, key, pending_store, now=now)

    if not valid_closed_choice(pending, answer):
        return invalid_choice_message(pending.question_kind)

    data = apply_answer(parse_item_text(pending.raw), pending, answer)

    try:
        result = format_result(calculate_price(data))
        pending_store.clear(key)
        return result
    except ValueError as error:
        if str(error) != "missing fields":
            raise

    if pending.question_kind == "spell_description" and not has_impact(data):
        pending_store.set(key, pending.raw, "utility", now=now)
        return (
            "I found spell text, but no damage or healing dice.\n"
            f"{clarification_question(data, 'utility')}"
        )

    next_kind = classify_question(data, pending.raw)
    if next_kind:
        raw = clarified_utility_raw(data) if pending.question_kind == "category_conflict" and next_kind == "utility" else pending.raw
        pending_store.set(key, raw, next_kind, now=now)
        return clarification_question(data, next_kind)

    return format_missing(data)


def cancel_appraisal(key: PendingKey, pending_store: PendingAppraisals) -> str:
    if pending_store.clear(key):
        return "Canceled the pending appraisal."
    return "There is no pending appraisal to cancel."

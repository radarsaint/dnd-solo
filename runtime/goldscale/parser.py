# Vendored verbatim from radarsaint/goldscale@a0a18c6 goldscale/parser.py (Brendon's Goldscale bot).
# Only change: package imports made relative. Do not edit here; re-vendor from Goldscale.
import re
from dataclasses import dataclass, field
from typing import Optional


# These are pricing controls, not item-description guesses.
# Do not add flavor synonyms here.
UTILITY_IMPACT = {
    "minor": 4,
    "reusable": 6,
    "broad": 8,
}


TYPE_TO_CATEGORY = {
    "potion": "consumable",
    "scroll": "consumable",
    "ammunition": "consumable",

    "weapon": "weapon / armor",
    "armor": "weapon / armor",
    "armour": "weapon / armor",
    "shield": "weapon / armor",
    "sword": "weapon / armor",
    "axe": "weapon / armor",
    "bow": "weapon / armor",
    "mace": "weapon / armor",
    "dagger": "weapon / armor",
    "spear": "weapon / armor",
    "crossbow": "weapon / armor",
    "battleaxe": "weapon / armor",
    "greataxe": "weapon / armor",
    "longbow": "weapon / armor",
    "shortbow": "weapon / armor",
    "quarterstaff": "weapon / armor",
    "longsword": "weapon / armor",
    "shortsword": "weapon / armor",
    "greatsword": "weapon / armor",

    "wand": "complex",
    "staff": "complex",
    "charged item": "complex",
    "multi-use item": "complex",
    "multi-ability item": "complex",

    "cloak": "utility",
    "ring": "utility",
    "boots": "utility",
    "gloves": "utility",
    "gauntlets": "utility",
    "amulet": "utility",
    "helm": "utility",
    "hat": "utility",
    "belt": "utility",
    "bracers": "utility",
    "brooch": "utility",
    "goggles": "utility",
    "bag": "utility",
    "jug": "utility",
    "robe": "utility",
    "wondrous item": "utility",
}


SOFT_UTILITY_ITEM_TYPES = {
    "ring",
    "cloak",
    "boots",
    "amulet",
    "belt",
    "bracers",
    "gloves",
    "gauntlets",
    "helm",
    "hat",
    "goggles",
    "robe",
    "bag",
    "jug",
    "wondrous item",
}


CONTEXT_ITEM_WORDS = {
    "rod",
    "deck",
    "tome",
    "manual",
    "book",
    "orb",
    "crystal",
    "gem",
    "stone",
    "instrument",
    "horn",
    "pipes",
    "chime",
    "decanter",
    "bottle",
    "figurine",
    "cube",
    "mirror",
    "lens",
    "lantern",
    "carpet",
    "broom",
    "rope",
}


MUNDANE_ONLY_WORDS = {
    "longsword",
    "shortsword",
    "greatsword",
    "sword",
    "axe",
    "bow",
    "crossbow",
    "dagger",
    "mace",
    "spear",
    "weapon",
    "armor",
    "armour",
    "shield",
    "rope",
    "backpack",
    "torch",
    "torches",
}


SUPPLIED_PRICE_OVERRIDE_MESSAGE = (
    "Goldscale supplies prices from the magic item formula. It does not use supplied price overrides."
)


MUNDANE_ONLY_MESSAGE = (
    "Goldscale prices magic items, not mundane gear.\n"
    "Add rarity and what the magic item changes."
)


CATEGORY_ALIASES = {
    "consumable": "consumable",
    "wep": "weapon / armor",
    "weapon / armor": "weapon / armor",
    "weapon armor": "weapon / armor",
    "utility": "utility",
    "util": "utility",
    "complex": "complex",
}


FORMULA_CATEGORY_DISPLAY = {
    "consumable": "Consumable",
    "weapon / armor": "Weapon / Armor Upgrade",
    "utility": "Utility Item",
    "complex": "Complex Multi-Ability Magic Item",
}


AVRAE_LABELS = {
    "attunement",
    "requires attunement",
    "description",
    "regaining charges",
    "item",
    "dmg",
    "dmg-2024",
}


@dataclass
class ItemData:
    item_name: Optional[str] = None
    rarity: Optional[str] = None
    unsupported_rarity: Optional[str] = None
    category: Optional[str] = None
    category_source: Optional[str] = None
    item_type_found: Optional[str] = None
    item_type_source: Optional[str] = None
    formula_category: Optional[str] = None
    formula_category_source: Optional[str] = None
    formula_category_confidence: Optional[str] = None
    formula_category_conflict: Optional[str] = None
    bonus: Optional[int] = None
    damage: Optional[str] = None
    healing: Optional[str] = None
    utility: Optional[str] = None
    aoe: bool = False
    charges: Optional[int] = None
    quantity: Optional[int] = None
    rejection_error: Optional[str] = None
    sell_rate: Optional[float] = None
    sell_rate_error: Optional[str] = None
    sell_rate_retry: Optional[str] = None
    sell_rate_retry_command: Optional[str] = None
    mode: str = "buy"
    randomized: bool = False
    has_description_text: bool = False
    spell_effect_without_dice: bool = False
    spell_reference: Optional[str] = None
    complex_partial_bonus: bool = False
    warnings: list[str] = field(default_factory=list)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def text_before_description(text: str) -> str:
    return re.split(
        r"\b(description|attunement|requires attunement|regaining charges|while holding it|this item|this wand|this staff|this weapon)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]


def title_item_name(name: str) -> str:
    name = re.sub(r"^[,;:\s]+|[,;:\s]+$", "", name)
    name = normalize_spaces(name)

    if not name:
        return "Unnamed Item"

    small_words = {"of", "the", "and", "a", "an", "in", "on", "with"}
    result = []

    for index, word in enumerate(name.split()):
        if re.fullmatch(r"\+[123]", word):
            result.append(word)
            continue

        lower = word.lower()
        if index > 0 and lower in small_words:
            result.append(lower)
        else:
            result.append(word[:1].upper() + word[1:])

    return " ".join(result)


def remove_old_prefix_accidents(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^\s*!price\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\?gs\s+", "", text, flags=re.IGNORECASE)
    return text.strip()


def split_mode(text: str) -> tuple[str, str]:
    stripped = text.strip()

    if re.match(r"^sell\b", stripped, flags=re.IGNORECASE):
        return "sell", re.sub(r"^sell\b", "", stripped, flags=re.IGNORECASE).strip()

    if re.match(r"^(buy|price)\b", stripped, flags=re.IGNORECASE):
        return "buy", re.sub(r"^(buy|price)\b", "", stripped, flags=re.IGNORECASE).strip()

    return "buy", stripped


def strip_known_speaker_prefix(text: str) -> str:
    return normalize_spaces(text)


def find_rarity(text: str) -> tuple[Optional[str], Optional[str]]:
    lower = text.lower()

    if re.search(r"\blegendary\b", lower):
        return None, "legendary"

    if re.search(r"\bartifact\b", lower):
        return None, "artifact"

    if re.search(r"\bvery\s+rare\b", lower) or re.search(r"\bveryrare\b", lower) or re.search(r"\bvr\b", lower):
        return "very rare", None

    for rarity in ("uncommon", "common", "rare"):
        if re.search(rf"\b{rarity}\b", lower):
            return rarity, None

    return None, None


def find_explicit_category(text: str) -> tuple[Optional[str], Optional[str]]:
    lower = text.lower()

    explicit_patterns = [
        ("weapon / armor", 'explicit formula category "weapon / armor"'),
        ("weapon armor", 'explicit formula category "weapon armor"'),
        ("consumable", 'explicit formula category "consumable"'),
        ("utility", 'explicit formula category "utility"'),
        ("complex", 'explicit formula category "complex"'),
        ("wep", 'explicit formula category "wep"'),
    ]

    for word, source in explicit_patterns:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            return CATEGORY_ALIASES[word], source

    return None, None


def find_category_from_type(text: str, item_name: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    matches = find_type_aliases(text, item_name)

    if matches:
        type_word, category = matches[0]
        return type_word, category, f'from item type "{type_word}"', "strong"

    return None, None, None, None


def find_type_aliases(text: str, item_name: Optional[str]) -> list[tuple[str, str]]:
    search_space = text.lower()
    matches = []

    for type_word, category in sorted(TYPE_TO_CATEGORY.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(type_word)}\b", search_space):
            matches.append((type_word, category))

    return matches


def find_context_item_type(text: str) -> Optional[str]:
    lower = text.lower()

    for type_word in sorted(CONTEXT_ITEM_WORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(type_word)}\b", lower):
            return type_word

    return None


def find_alias_category_conflict(text: str, item_name: Optional[str], explicit_category: Optional[str]) -> Optional[str]:
    matches = find_type_aliases(text, item_name)
    categories = {category for _, category in matches}

    if explicit_category:
        categories.add(explicit_category)

    if len(categories) <= 1:
        return None

    found = ", ".join(f"{word} -> {category}" for word, category in matches)
    if explicit_category:
        found = f"{found}, explicit -> {explicit_category}" if found else f"explicit -> {explicit_category}"

    return (
        "Goldscale found conflicting item type signals. "
        "Use one item type, such as wand, potion, weapon, armor, cloak, or charged item."
        f" Found: {found}."
    )


def find_soft_utility_charged_damage_conflict(data: ItemData) -> Optional[str]:
    if data.item_type_found not in SOFT_UTILITY_ITEM_TYPES:
        return None

    if not data.charges or not (data.damage or data.healing):
        return None

    return (
        "I found mixed item-type signals.\n"
        f"This looks like a {data.item_type_found}, but charged damage suggests a multi-use magic item.\n"
        "Use \"charged item\" if you want this priced as Complex Multi-Ability Magic Item."
    )


def find_charges(text: str) -> Optional[int]:
    lower = text.lower()

    patterns = [
        r"\bhas\s+(\d+)\s+charges?\b",
        r"\b(\d+)\s+charges?\b",
        r"\bcharges?\s*[:=]?\s*(\d+)\b",
        r"\b(\d+)\s+uses?\b",
        r"\b(\d+)\s+beads?\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, lower):
            if "bead" in match.group(0) and re.search(r"\d+d\d+\s*[+-]\s*$", lower[max(0, match.start() - 12):match.start()]):
                continue
            return int(match.group(1))

    return None


def find_quantity(text: str) -> Optional[int]:
    lower = text.lower()
    match = re.search(r"\b(?:quantity|qty|count)\s*[:=]?\s*(\d+)\b", lower)

    if match:
        return int(match.group(1))

    return None


def has_supplied_price_override(text: str) -> bool:
    lower = text.lower()

    return bool(
        re.search(
            r"\b(?:official(?:\s+price)?|listed price|list price|manual price|dm override|override)\b",
            lower,
        )
    )


def is_mundane_only_request(body: str, data: ItemData) -> bool:
    if data.rarity or data.unsupported_rarity or data.bonus is not None or data.damage or data.healing or data.utility:
        return False

    if data.charges:
        return False

    lower = body.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", lower) for word in MUNDANE_ONLY_WORDS)


def find_sell_rate(text: str) -> tuple[Optional[float], Optional[str]]:
    lower = text.lower()

    percent_match = re.search(r"\b(?:at|for|custom)?\s*(\d{1,3})\s*%", lower)
    if percent_match:
        rate = int(percent_match.group(1))

        if rate <= 0 or rate > 100:
            return None, "Sell rate must be between 1% and 100%."

        return rate / 100, None

    bare_match = re.search(r"\b(?:at|for|custom)\s+(\d{1,3})\b", lower)
    if bare_match:
        number = bare_match.group(1)
        return None, f'I found "{number}" but not "{number}%." For sell rates, include the percent sign.'

    return None, None


def sell_rate_error_message(warning: str) -> str:
    if warning == "Sell rate must be between 1% and 100%.":
        return warning

    return "I need the sell rate with a percent sign."


def build_sell_rate_retry_command(body: str, number: str) -> str:
    retry_body = re.sub(
        rf"\b(at|for|custom)\s+{re.escape(number)}\b",
        rf"\1 {number}%",
        body,
        count=1,
        flags=re.IGNORECASE,
    )
    return f"?gs sell {normalize_spaces(retry_body)}"


def item_name_before_pricing_signals(text: str) -> Optional[str]:
    cleaned = normalize_spaces(text)
    if not cleaned:
        return None

    signal_pattern = re.compile(
        r"\b("
        r"common|uncommon|rare|very\s+rare|veryrare|vr|legendary|artifact|"
        r"consumable|utility|complex|weapon\s*/\s*armor|weapon armor|weapon|armor|armour|shield|"
        r"\d+d\d+(?:\s*[+-]\s*\d+)?|aoe|area of effect|minor|reusable|broad|"
        r"\d+\s+charges?|charges?\s*[:=]?\s*\d+|"
        r"(?:quantity|qty|count)\s*[:=]?\s*\d+|"
        r"official price|official|listed price|list price|manual price|dm override|override|at\s+\d{1,3}%?"
        r")\b",
        flags=re.IGNORECASE,
    )
    match = signal_pattern.search(cleaned)

    if not match:
        return None

    candidate = cleaned[:match.start()].strip(" ,;:")
    signal = match.group(0).lower()
    if re.fullmatch(r"\+[123]", candidate) and signal in TYPE_TO_CATEGORY:
        return f"{candidate} {signal}"

    return candidate or None


def strip_leading_quantity_signal(text: str) -> str:
    return re.sub(r"^\s*(?:quantity|qty|count)\s*[:=]?\s*\d+\s+", "", text, flags=re.IGNORECASE)


def trim_flattened_speaker_text(candidate: str, type_word: str) -> str:
    words = candidate.split()
    lowered_type = type_word.lower()

    for index in range(len(words) - 1, -1, -1):
        if words[index].lower() == lowered_type:
            return " ".join(words[index:])

    return candidate


def remove_dice_expressions(text: str) -> str:
    return re.sub(r"\b\d+d\d+(?:\s*[+-]\s*\d+)?\b", " ", text, flags=re.IGNORECASE)


BONUS_WORDS = {
    "1": 1,
    "one": 1,
    "2": 2,
    "two": 2,
    "3": 3,
    "three": 3,
}


def bonus_match_is_charge_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 60): min(len(text), end + 80)]
    return bool(re.search(r"\b(charges?|recharge|regains?|expended|uses?)\b", window, flags=re.IGNORECASE))


def find_bonus(text: str) -> Optional[int]:
    # Remove dice expressions first so "1d6 + 1" does not become a +1 item.
    no_dice = remove_dice_expressions(text.lower())

    explicit = re.search(r"\bbonus\s*[:=]?\s*(?:\+\s*)?([123])\b", no_dice)
    if explicit:
        return int(explicit.group(1))

    explicit_after = re.search(r"(?<![0-9d])\+\s*([123])\s+bonus\b", no_dice)
    if explicit_after:
        return int(explicit_after.group(1))

    for match in re.finditer(r"(?<![0-9d])\+\s*([123])\b", no_dice):
        if not bonus_match_is_charge_context(no_dice, match.start(), match.end()):
            return int(match.group(1))

    for match in re.finditer(r"\bplus[-\s]+(1|2|3|one|two|three)\b", no_dice):
        if not bonus_match_is_charge_context(no_dice, match.start(), match.end()):
            return BONUS_WORDS[match.group(1)]

    return None


def find_dice_expressions(text: str) -> list[tuple[str, int, int]]:
    results = []

    for match in re.finditer(r"\b\d+d\d+(?:\s*[+-]\s*\d+)?\b", text.lower()):
        expr = match.group(0).replace(" ", "")
        results.append((expr, match.start(), match.end()))

    return results


def dice_is_recharge_or_table_roll(lower: str, start: int, end: int, allow_charge_count_clause: bool = False) -> bool:
    window = lower[max(0, start - 80): min(len(lower), end + 120)]
    after_dice = lower[end: min(len(lower), end + 80)]

    reject_terms = [
        "recharge",
        "charges daily",
        "daily at dawn",
        "expended charges",
        "roll 1d20",
        "roll a d20",
        "on a 1",
        "crumbles",
        "destroyed",
        "maximum",
    ]

    if any(term in window for term in reject_terms):
        return True

    if re.match(r"^[\s,]*(beads?|stars?|charges?|uses?|patches?)\b", after_dice):
        return True

    if re.match(r"^[\s,]*(?:for|per)\s+(?:each|every|additional)?\s*(?:bead|charge|use|patch)\b", after_dice):
        return True

    # Strongly reject dice whose nearby noun is charges, unless it is clearly damage/healing.
    if "charge" in window and not any(term in window for term in ("damage", "healing", "hit points")):
        if allow_charge_count_clause and re.match(r"^[\s,]*(?:aoe|area of effect)?[\s,]*\d+\s+charges?\b", after_dice):
            return False
        return True

    return False


def find_damage_or_healing(text: str) -> tuple[Optional[str], Optional[str]]:
    lower = text.lower()
    dice_matches = find_dice_expressions(lower)

    for expr, start, end in dice_matches:
        if dice_is_recharge_or_table_roll(lower, start, end):
            continue

        window = lower[max(0, start - 90): min(len(lower), end + 120)]

        if any(term in window for term in ("heal", "healing", "hit points")) and "charge" not in window:
            return None, expr

        if any(term in window for term in ("damage", "dam.", "takes", "deal", "deals")):
            return expr, None

    # Loose command syntax still needs to work:
    # ?gs buy wand of fireballs, rare complex, 8d6 aoe, 7 charges
    # If this is not an Avrae/rules-text paste, accept the first non-recharge dice as damage.
    looks_like_paste = bool(re.search(r"\b(description|attunement|requires attunement|regaining charges)\b", lower))

    if not looks_like_paste:
        for expr, start, end in dice_matches:
            if not dice_is_recharge_or_table_roll(lower, start, end, allow_charge_count_clause=True):
                if re.search(rf"{re.escape(expr)}\s*(healing|heal)", lower):
                    return None, expr
                return expr, None

    return None, None


def find_aoe(text: str) -> bool:
    lower = text.lower()

    safe_patterns = [
        r"\baoe\b",
        r"\barea of effect\b",
        r"\b\d+\s*-?\s*foot\s+radius\b",
        r"\bradius\b",
        r"\bsphere\b",
        r"\bcone\b",
        r"\bcube\b",
        r"\bcylinder\b",
        r"\b\d+\s*-?\s*foot\s+line\b",
        r"\beach creature in\b",
        r"\beach creature within\b",
        r"\bcreatures within\b",
        r"\ball creatures within\b",
    ]

    if re.search(r"\b(?:bright|dim)\s+light\b", lower):
        lightless = re.sub(
            r"\b(?:bright|dim)\s+light\b.{0,80}?\b(?:radius|sphere|cone|cube|cylinder|line)\b",
            " ",
            lower,
        )
        lower = lightless

    return any(re.search(pattern, lower) for pattern in safe_patterns)


def find_utility(text: str) -> Optional[str]:
    lower = text.lower()

    # Explicit adjacent forms work anywhere, including after a pasted description.
    adjacent_patterns = [
        r"\b(minor|reusable|broad)\s+utility\b",
        r"\butility\s*[:=,]?\s*(minor|reusable|broad)\b",
    ]

    for pattern in adjacent_patterns:
        match = re.search(pattern, lower)
        if match:
            if match.group(1) in UTILITY_IMPACT:
                return match.group(1)
            if match.group(2) in UTILITY_IMPACT:
                return match.group(2)

    # Loose shorthand works only before Avrae description text.
    # This lets "?gs buy cloak, uncommon utility, reusable" work, but avoids reading item prose as a tier.
    pre_description = re.split(r"\bdescription\b", lower, maxsplit=1)[0]

    for tier in UTILITY_IMPACT:
        if re.search(rf"\b{tier}\b", pre_description):
            return tier

    return None


def find_randomized_item_markers(text: str) -> bool:
    lower = text.lower()

    markers = [
        "determined by rolling",
        "roll on",
        "effects table",
        "effect determined",
        "determines randomly",
        "determined randomly",
        "randomly which",
        "random effect",
    ]

    return any(marker in lower for marker in markers)


def has_pasted_description(text: str) -> bool:
    return bool(
        re.search(
            r"\b(description|attunement|requires attunement|regaining charges|while holding it|this item|this wand|this staff|this weapon)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def find_spell_effect_without_dice(text: str, damage: Optional[str], healing: Optional[str]) -> bool:
    if damage or healing:
        return False

    lower = text.lower()
    if not has_pasted_description(lower):
        return False

    return bool(re.search(r"\b(cast|casts|spell|spellcasting|fireball|cure wounds|magic missile)\b", lower))


def find_spell_reference(text: str, damage: Optional[str], healing: Optional[str]) -> Optional[str]:
    if damage or healing:
        return None

    lower = text.lower()
    patterns = [
        r"\bcast\s+([a-z][a-z\s'-]{1,40}?)(?:\.|,|;|\n|$)",
        r"\bcasts\s+([a-z][a-z\s'-]{1,40}?)(?:\.|,|;|\n|$)",
        r"\bto\s+cast\s+([a-z][a-z\s'-]{1,40}?)(?:\.|,|;|\n|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            spell = normalize_spaces(match.group(1))
            spell = re.sub(r"^(the|a|an)\s+", "", spell)
            spell = re.sub(r"\s+spell$", "", spell)
            if spell in {"iron", "shadow"}:
                continue
            return spell or None

    return None


def clean_lines_after_mode(text: str) -> list[str]:
    cleaned = remove_old_prefix_accidents(text)
    _, cleaned = split_mode(cleaned)

    lines = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.lower() in AVRAE_LABELS:
            continue

        lines.append(line)

    return lines


def extract_item_name(text: str) -> Optional[str]:
    cleaned = remove_old_prefix_accidents(text)
    _, cleaned = split_mode(cleaned)

    lines = clean_lines_after_mode(text)

    # Avrae multiline pattern:
    # Wand of Wonder
    # Wand, rare
    for index, line in enumerate(lines[:-1]):
        next_line = lines[index + 1]
        if re.match(r"^(wand|weapon|armor|armour|potion|scroll|staff|rod|ring|cloak|shield|boots|amulet|belt|bracers|gloves|gauntlets|helm|hat|goggles|bag|jug|robe|wondrous item|charged item|multi-use item|multi-ability item)[,\s]+(?:common|uncommon|rare|very\s+rare)\b", next_line, flags=re.IGNORECASE):
            return title_item_name(strip_known_speaker_prefix(line))

    # If first cleaned line looks title-like, use it.
    if lines:
        first = strip_leading_quantity_signal(strip_known_speaker_prefix(lines[0]))
        if not re.search(r"\b(description|attunement|requires attunement|this item|this wand|this weapon)\b", first, flags=re.IGNORECASE):
            signal_candidate = item_name_before_pricing_signals(first)
            if signal_candidate:
                return title_item_name(signal_candidate)
            if "," in first:
                candidate = first.split(",", 1)[0]
                if candidate.strip():
                    return title_item_name(candidate)
            if len(first) <= 90:
                return title_item_name(first)

    # Flattened Avrae pattern:
    # DM radar Wand of Wonder Wand, rare Attunement...
    flat = normalize_spaces(cleaned)
    type_words = "|".join(re.escape(word) for word in sorted(TYPE_TO_CATEGORY, key=len, reverse=True))
    match = re.search(
        rf"^(.+?)\s+({type_words})\s*,\s*(common|uncommon|rare|very\s+rare)\b",
        flat,
        flags=re.IGNORECASE,
    )

    if match:
        candidate = trim_flattened_speaker_text(strip_known_speaker_prefix(match.group(1)), match.group(2))
        return title_item_name(candidate)

    return None


def remove_known_signals_for_name(text: str) -> str:
    cleaned = remove_old_prefix_accidents(text)
    _, cleaned = split_mode(cleaned)

    # Remove everything after common Avrae rule prose starts.
    cleaned = re.split(
        r"\b(description|attunement|requires attunement|regaining charges|this wand|this item|this weapon|while holding it)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    # Remove labels and pricing signals.
    cleaned = re.sub(r"\b(item|rarity|category|damage|healing|utility|charges|charge|official price|official|listed price|list price|manual price|dm override|override)\s*[:=]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bvery\s+rare\b|\bveryrare\b|\bvr\b|\buncommon\b|\bcommon\b|\brare\b|\blegendary\b|\bartifact\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(consumable|utility|complex|weapon\s*/\s*armor|weapon armor|weapon|armor|armour)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+d\d+(?:\s*[+-]\s*\d+)?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<![0-9d])\+[123]\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+\s*(?:charges?|uses?)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:has\s+)?\d+\s+charges?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:quantity|qty|count)\s*[:=]?\s*\d+\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(aoe|area of effect|minor|reusable|broad)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:at|for|custom)?\s*\d{1,3}\s*%", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[,;:|]+", " ", cleaned)
    cleaned = normalize_spaces(cleaned)

    return cleaned


def trim_repeated_category_from_bonus_name(name: str) -> str:
    if not re.match(r"^\+[123]\b", name, flags=re.IGNORECASE):
        return name

    return re.sub(r"\s+(weapon|armor|armour)$", "", name, flags=re.IGNORECASE)


def clean_bonus_phrase_from_name(name: str, bonus: Optional[int]) -> str:
    if bonus is None:
        return name

    cleaned = normalize_spaces(name)
    cleaned = re.sub(rf"^\+\s*{bonus}\b", f"+{bonus}", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\bplus[-\s]+(?:{bonus}|{['', 'one', 'two', 'three'][bonus]})\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s+\+\s*{bonus}\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_spaces(cleaned)
    return cleaned or name


def parse_item_text(raw: str) -> ItemData:
    text = remove_old_prefix_accidents(raw)
    mode, body = split_mode(text)

    data = ItemData(mode=mode)
    if has_supplied_price_override(body):
        data.rejection_error = SUPPLIED_PRICE_OVERRIDE_MESSAGE

    data.item_name = extract_item_name(text)
    data.rarity, data.unsupported_rarity = find_rarity(body)

    pre_description = text_before_description(body)
    explicit_category, explicit_source = find_explicit_category(pre_description)
    data.formula_category = explicit_category
    data.formula_category_source = explicit_source
    data.formula_category_confidence = "explicit" if explicit_category else None

    data.charges = find_charges(body)
    data.quantity = find_quantity(body)
    data.bonus = find_bonus(body)
    data.damage, data.healing = find_damage_or_healing(body)
    data.aoe = find_aoe(body)
    data.utility = find_utility(body)
    data.randomized = find_randomized_item_markers(body)
    data.has_description_text = has_pasted_description(body)
    data.spell_effect_without_dice = find_spell_effect_without_dice(body, data.damage, data.healing)
    data.spell_reference = find_spell_reference(body, data.damage, data.healing)

    if data.mode == "sell":
        data.sell_rate, warning = find_sell_rate(body)
        if warning:
            data.sell_rate_error = sell_rate_error_message(warning)
            data.warnings.append(warning)
            match = re.search(r'"(\d{1,3})"', warning)
            if match:
                data.sell_rate_retry = match.group(1)
                data.sell_rate_retry_command = build_sell_rate_retry_command(body, data.sell_rate_retry)
        if data.sell_rate is None and not data.sell_rate_error:
            data.sell_rate = 0.50

    if not data.item_name:
        candidate = remove_known_signals_for_name(body)
        data.item_name = title_item_name(candidate) if candidate else None

    if data.formula_category:
        item_type, inferred_category, source, confidence = None, None, None, None
        context_item_type = None
    else:
        item_type, inferred_category, source, confidence = find_category_from_type(pre_description, data.item_name)
        context_item_type = find_context_item_type(pre_description)

    data.item_type_found = item_type or context_item_type
    data.item_type_source = f'from item type "{data.item_type_found}"' if data.item_type_found else None

    if data.formula_category is None:
        if inferred_category:
            data.formula_category = inferred_category
            data.formula_category_source = source
            data.formula_category_confidence = confidence
        elif context_item_type and data.utility:
            data.formula_category = "utility"
            data.formula_category_source = f'from context item type "{context_item_type}" with utility strength'
            data.formula_category_confidence = "context"

    if not data.rejection_error:
        conflict = find_alias_category_conflict(pre_description, data.item_name, data.formula_category)
        if conflict:
            data.rejection_error = conflict
            data.formula_category_conflict = conflict

    if not data.rejection_error:
        conflict = find_soft_utility_charged_damage_conflict(data)
        if conflict:
            data.rejection_error = conflict
            data.formula_category_conflict = conflict

    if not data.rejection_error and is_mundane_only_request(body, data):
        data.rejection_error = MUNDANE_ONLY_MESSAGE

    data.category = data.formula_category
    data.category_source = data.formula_category_source

    if data.item_name and data.category_source and data.category_source.startswith("explicit formula category"):
        data.item_name = title_item_name(trim_repeated_category_from_bonus_name(data.item_name))

    if data.item_name:
        data.item_name = title_item_name(clean_bonus_phrase_from_name(data.item_name, data.bonus))

    if (
        data.formula_category == "complex"
        and data.charges
        and data.bonus is not None
        and data.damage is None
        and data.healing is None
        and data.utility is None
    ):
        data.complex_partial_bonus = True

    return data

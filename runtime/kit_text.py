"""Spoken quantities shared by the shop tool and the card table.

Cards name a rank from one to thirteen. A shop line can also start with a
count: a digit, one through twenty, or a dozen, a pair, a couple, a brace.
The word list lives here so those two readers do not keep their own copies.
Rolls are not read here. Those stay in kit_rolls.
"""
from __future__ import annotations

import re

_SPOKEN = (
    'zero one two three four five six seven eight nine ten eleven twelve thirteen '
    'fourteen fifteen sixteen seventeen eighteen nineteen twenty'
).split()
WORD_NUMBERS: dict[str, int] = {word: index for index, word in enumerate(_SPOKEN)}
CARD_WORDS: dict[str, int] = {word: WORD_NUMBERS[word] for word in _SPOKEN if 1 <= WORD_NUMBERS[word] <= 13}

_SHOP_WORDS = {
    **WORD_NUMBERS,
    'a': 1,
    'an': 1,
    'dozen': 12,
    'pair': 2,
    'couple': 2,
    'brace': 2,
}
_COUNT = re.compile(
    r"^(?:(\d+)|(?:a\s+|an\s+)?(dozen|pair|couple|brace)(?:\s+of)?|([a-z]+))\s+(?=[a-z+])",
    re.IGNORECASE,
)


def card_number(token: str) -> int:
    """A card rank token: digits, or one through thirteen."""
    if token.isdigit():
        return int(token)
    return CARD_WORDS[token]


def leading_count(text: str | None) -> tuple[int, str] | None:
    """(count, rest) for a leading quantity.

    Digits, one..twenty, a dozen, a pair/couple/brace (of), and a/an as 1.
    None when the text does not start with a count. Zero is not a count.
    """
    raw = text or ''
    found = _COUNT.match(raw)
    if not found:
        return None
    if found.group(1):
        count = int(found.group(1))
    else:
        word = (found.group(2) or found.group(3)).lower()
        if word not in _SHOP_WORDS or word == 'zero':
            return None
        count = _SHOP_WORDS[word]
    if count < 1:
        return None
    return count, raw[found.end():]

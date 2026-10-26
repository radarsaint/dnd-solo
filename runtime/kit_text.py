"""Spoken quantities shared by the shop tool and the card table.

Cards name a rank from one to thirteen. A shop line and a Goldscale line share
one quantity grammar: a leading count, a "qty N" signal, or a trailing "x N".
"3 torches", "three torches", "qty 3 torch", "a dozen arrows", "pair of
daggers", and "torches x3" are the same count. Rolls are not read here.
Those stay in kit_rolls.
"""
from __future__ import annotations

import re

from .kit_lazyre import compile as lazy_compile

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
_COUNT = lazy_compile(
    r"^(?:(\d+)|(?:a\s+|an\s+)?(dozen|pair|couple|brace)(?:\s+of)?|([a-z]+))\s+(?=[a-z+])",
    re.IGNORECASE,
)
# A number of charges, uses, or coins is not a stack of items.
_NOT_A_COUNT = lazy_compile(
    r"^(?:charges?|uses?|beads?|gp|sp|cp|pp|percent)\b",
    re.IGNORECASE,
)
_EXPLICIT = lazy_compile(
    r"\b(?:quantity|qty|count)\s*[:=]?\s*(\d+)\b",
    re.IGNORECASE,
)
_TRAILING_X = lazy_compile(
    r"^(?P<item>.+?)\s+x\s*(?P<n>\d+)\s*$",
    re.IGNORECASE,
)


def card_number(token: str) -> int:
    """A card rank token: digits, or one through thirteen."""
    if token.isdigit():
        return int(token)
    return CARD_WORDS[token]


def _tidy(text: str) -> str:
    return " ".join(text.split()).strip(" ,;")


def leading_count(text: str | None) -> tuple[int, str] | None:
    """(count, rest) for a leading quantity.

    Digits, one..twenty, a dozen, a pair/couple/brace (of), and a/an as 1.
    None when the text does not start with a count. Zero is not a count.
    "7 charges" is a charge count, not a stack of items.
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
    rest = raw[found.end():]
    if _NOT_A_COUNT.match(rest):
        return None
    return count, rest


def parse_quantity(text: str | None) -> tuple[int, str] | None:
    """(count, item text) for the one shop and Goldscale quantity grammar.

    Explicit "qty / quantity / count N" anywhere, a trailing "x N", then a
    leading count. "+1" is a bonus, not a count. "7 charges" is not a count.
    An explicit zero is returned as zero so an old "qty 0" line stays a zero.
    """
    raw = _tidy(text or '')
    if not raw:
        return None
    explicit = _EXPLICIT.search(raw)
    if explicit:
        count = int(explicit.group(1))
        if count < 0:
            return None
        rest = _tidy(_EXPLICIT.sub(' ', raw, count=1))
        return count, rest
    trailing = _TRAILING_X.match(raw)
    if trailing and re.search(r'[A-Za-z]', trailing.group('item')):
        count = int(trailing.group('n'))
        if count >= 1:
            return count, _tidy(trailing.group('item'))
    return leading_count(raw)

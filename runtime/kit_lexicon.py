"""Spelling repair for a player's line before Kit reads what he means.

Proven tools, not more regex: pyspellchecker (MIT) knows which words are real English words,
and rapidfuzz (MIT) measures typo distance toward the words Kit's move and skill readers use.
Both are optional (requirements.txt). Without them Kit falls back to the standard library
(difflib) and only repairs a long word one letter away from a Kit word. A real word is never
touched, so a clean line never changes.

``normalize(text)`` returns the repaired line ("i atack the guy" -> "i attack the guy").
"""
import difflib
import re
from functools import lru_cache

try:  # optional, MIT
    from rapidfuzz import process as _rf_process
    from rapidfuzz.distance import OSA as _rf_osa
except ImportError:  # pragma: no cover - exercised on hosts without it
    _rf_process = _rf_osa = None
try:  # optional, MIT
    from spellchecker import SpellChecker as _SpellChecker
except ImportError:  # pragma: no cover
    _SpellChecker = None

_WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")
# Function words a typo must never be "repaired" into or out of.
_COMMON = frozenset("""a an the i me my we us our you your he him his she her it its they them their this that
these those there here what who whom whose which where when why how is am are was were be been being do does
did done have has had can could would should will shall may might must not no yes and or but if then so to of
in on at by for with from into onto over under up down out off about as than too very just also only all any
some each every both either one two three four five six seven eight nine ten let lets let's go gonna wanna
im i'm i'd i'll it's that's what's he's she's we're they're don't doesn't can't won't isn't wasn't get got
see say said tell told make made take took give gave come came way thing things guy kid man woman old new
back now still again more most much many like know think want try need""".split())
_KEEP_SHORT = 4  # shorter unknown words are left alone unless one swap of two letters fixes them


def _vocabulary():
    """Every word the move and skill readers match on, from their own patterns."""
    from . import kit_moves, kit_skills
    words = set()
    sources = [p for _s, _u, p in kit_skills.SKILL_USES]
    for name in dir(kit_moves):
        value = getattr(kit_moves, name)
        if isinstance(value, str):
            sources.append(value)
        pattern = getattr(value, 'pattern', None)
        if isinstance(pattern, str):
            sources.append(pattern)
    for source in sources:
        cleaned = re.sub(r'\\[a-zA-Z]', ' ', source)
        for word in re.findall(r'[a-z]{3,}', cleaned.lower()):
            words.add(word)
    words |= {s.replace('_', ' ') for s in kit_moves.SKILLS} | set(kit_moves.MOVES)
    words |= {'attack', 'search', 'ask', 'look', 'around', 'body', 'bodies', 'sneaking', 'sneak', 'climb',
              'jump', 'swim', 'run', 'hit', 'check', 'roll', 'rest', 'hidden'}
    return frozenset(w for part in words for w in part.split())


@lru_cache(maxsize=1)
def _known():
    return _vocabulary()


@lru_cache(maxsize=1)
def _english():
    return _SpellChecker() if _SpellChecker is not None else None


def _repair(word):
    lower = word.lower()
    vocab = _known()
    english = _english()
    if lower in vocab or lower in _COMMON or not lower.isalpha() or word[:1].isupper():
        return word  # a capitalized word is a name or the line's first word: left alone
    if english is not None and not english.unknown([lower]):
        return word  # a real word ("parents", "closest"): never "repaired"
    if english is None and len(lower) < 5:  # no word list: only long words, one letter off
        return word
    if len(lower) < _KEEP_SHORT:
        swaps = [w for w in vocab if len(w) == len(lower) and _transposed(w, lower)]
        if len(swaps) == 1:
            return _same_case(word, swaps[0])
        return word  # a short unknown word ("orc") is more likely a name than a typo
    if any(w.startswith(lower) or lower.startswith(w) for w in vocab if len(w) >= _KEEP_SHORT and
           abs(len(w) - len(lower)) <= 3 and w[:4] == lower[:4]):
        if english is None:
            return word  # "thicket" beside "thickets": a word form, not a typo
    candidates = [w for w in vocab if w[0] == lower[0] and abs(len(w) - len(lower)) <= 2]
    limit = 1 if (len(lower) < 6 or english is None) else 2
    if candidates and _rf_process is not None:
        hit = _rf_process.extractOne(lower, candidates, scorer=_rf_osa.distance, score_cutoff=limit)
        if hit:
            return _same_case(word, hit[0])
    elif candidates:
        close = difflib.get_close_matches(lower, candidates, n=1, cutoff=0.86)
        if close:
            return _same_case(word, close[0])
    if english is not None and len(lower) >= _KEEP_SHORT:
        fixed = english.correction(lower)
        if fixed and fixed != lower:
            return _same_case(word, fixed)
    return word


def _transposed(a, b):
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


def _same_case(original, word):
    return word.capitalize() if original[:1].isupper() else word


def normalize(text):
    """The line with unknown words repaired toward Kit's vocabulary; a clean line is unchanged."""
    text = str(text or '')
    if not text:
        return text
    return _WORD.sub(lambda m: _repair(m.group(0)), text)


def backend():
    return {'distance': 'rapidfuzz' if _rf_process is not None else 'difflib',
            'words': 'pyspellchecker' if _SpellChecker is not None else 'none'}

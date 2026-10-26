"""Kit never guesses at character generation (Brendon, 2026-10-25).

She carries the SRD 5.1 core options and nothing later. For any class feature, subclass,
species, background, feat, or spell list beyond the SRD, she says she doesn't have that
text and asks the player to paste the exact rules or hand her the finished sheet. She reads
and checks sheets; she never invents options, features, or numbers.

    python -m runtime.kit_chargen "help me build a Twilight cleric"
"""
import argparse
import json
import re
import sys

# SRD 5.1 (CC-BY-4.0) player options, names only.
SRD_OPTIONS = {
    'class': ('barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk', 'paladin', 'ranger', 'rogue',
              'sorcerer', 'warlock', 'wizard'),
    'subclass': ('path of the berserker', 'berserker', 'college of lore', 'lore', 'life domain', 'life',
                 'circle of the land', 'land', 'champion', 'way of the open hand', 'open hand',
                 'oath of devotion', 'devotion', 'hunter', 'thief', 'draconic bloodline', 'draconic',
                 'the fiend', 'fiend', 'school of evocation', 'evocation'),
    'species': ('dwarf', 'hill dwarf', 'elf', 'high elf', 'halfling', 'lightfoot halfling', 'lightfoot',
                'human', 'dragonborn', 'gnome', 'rock gnome', 'half-elf', 'half-orc', 'tiefling'),
    'background': ('acolyte',),
    'feat': ('grappler',),
}
_SRD_WORDS = {name for names in SRD_OPTIONS.values() for name in names}

_BUILD = re.compile(
    r"\b(build|make|create|roll up|level(?:ing)? up|multiclass|respec|new character|"
    r"character creation|chargen|which (?:feat|subclass|species|race|background)|"
    r"pick (?:a |my )?(?:feat|subclass|species|race|background|spells?))\b", re.I)
_CHAR_NOUN = re.compile(r"\b(character|pc|sheet|build|feat|subclass|species|race|background|class|level|"
                        + '|'.join(re.escape(w) for w in SRD_OPTIONS['class']) + r")s?\b", re.I)
# Names that mark a non-SRD option: a later book, D&D Beyond, or an option word with a name
# that isn't an SRD option.
_BEYOND = re.compile(r"\b(tasha'?s?|xanathar'?s?|volo'?s?|mordenkainen'?s?|fizban'?s?|monsters of the multiverse|"
                     r"2024|phb 2024|one d&d|d&d beyond|dndbeyond|ua|unearthed arcana|homebrew)\b", re.I)
_NAMED = re.compile(r"\b([a-z][a-z'\-]*(?: [a-z][a-z'\-]*){0,2}) (domain|oath|circle|college|school|"
                    r"patron|path|way|archetype|conclave|bloodline|origin|subclass|feat|species|race|"
                    r"background)\b", re.I)
_NAMED_AFTER = re.compile(r"\b(domain|oath|circle|college|school|path|way) of (?:the )?([a-z][a-z'\-]*)", re.I)
_CLASS_WITH_ADJ = re.compile(r"\b((?:[a-z][a-z'\-]+ )?[a-z][a-z'\-]+) (" + '|'.join(SRD_OPTIONS['class']) + r")\b", re.I)
_FILLER = {'a', 'an', 'the', 'my', 'new', 'level', 'srd', 'first', 'second', 'third', 'fourth', 'fifth',
           'this', 'that', 'good', 'basic', 'simple', 'human', 'build', 'make', 'create', 'pick', 'which',
           'what', 'help', 'me', 'to', 'up', 'for', 'some', 'level-1', 'multiclass', 'with', 'and', 'or',
           'core', 'beginner', 'starting', 'test', 'quick', 'strong', 'support', 'melee', 'ranged'}
_FILLER |= {f'{n}th' for n in range(1, 21)} | {'1st', '2nd', '3rd'}

NEED_RULES_NAMED = ("I don't carry {name} in my books, and I won't guess at it. Paste me the exact rules, "
                    "or hand me your finished sheet and I'll check it line by line.")
NEED_RULES = ("That's past the core rules I carry, and I won't guess at it. Paste me the exact rules, "
              "or hand me your finished sheet and I'll check it line by line.")
SRD_LINE = ("That's core rules, so I can walk you through it. Anything from a later book, "
            "paste me the text first.")


def is_srd(name):
    return (name or '').strip().casefold() in _SRD_WORDS


def is_chargen_request(text):
    text = text or ''
    return bool(_BUILD.search(text) and _CHAR_NOUN.search(text))


def _strip_srd(text):
    """Remove SRD subclass/species/background/feat names (longest first); class names stay."""
    out = ' ' + text.lower() + ' '
    names = sorted({n for k, v in SRD_OPTIONS.items() if k != 'class' for n in v if ' ' in n}, key=len, reverse=True)
    for name in names:
        out = re.sub(r'\b' + re.escape(name) + r'\b', ' ', out)
    return out


def _unknown_names(text):
    text = _strip_srd(text)
    found = []
    for match in _NAMED.finditer(text):
        words = [w for w in match.group(1).lower().split() if w not in _FILLER and not is_srd(w)]
        if words:
            name = ' '.join(words)
            if not is_srd(name):
                found.append(f'{name} {match.group(2).lower()}'.strip())
    for match in _NAMED_AFTER.finditer(text):
        full = f'{match.group(1)} of {match.group(2)}'.lower()
        if not (is_srd(full) or is_srd(match.group(2)) or is_srd(f'{match.group(1)} of the {match.group(2)}')):
            found.append(full)
    for match in _CLASS_WITH_ADJ.finditer(text):
        words = [w for w in match.group(1).lower().split()
                 if w not in _FILLER and not is_srd(w) and not w.endswith(('ing', 'ed', 'ly'))]
        word = ' '.join(words)
        if word and not is_srd(word) and not any(word in f for f in found):
            found.append(f'{word} {match.group(2).lower()}')
    return list(dict.fromkeys(found))


def chargen(text, sheet_given=False):
    """Kit's answer to a character-building request, or None if the text isn't one."""
    if not is_chargen_request(text):
        return None
    unknown = _unknown_names(text)
    beyond = _BEYOND.search(text)
    base = {'stage': 'chargen', 'never_guess': True, 'sheet_given': bool(sheet_given),
            'next_step': ('Do not invent class features, subclass features, species traits, feats, spells, '
                          'or numbers beyond the SRD 5.1. Use only text the player pasted or their sheet. '
                          'With a sheet, read it and check each entry against its source.')}
    if unknown or beyond:
        name = unknown[0] if unknown else None
        line = NEED_RULES_NAMED.format(name=name.title()) if name else NEED_RULES
        return {**base, 'srd_only': False, 'unknown_options': unknown or [beyond.group(0)],
                'needs': ['exact_rules_text', 'or_finished_sheet'], 'table_line': line}
    return {**base, 'srd_only': True, 'unknown_options': [], 'needs': [], 'table_line': SRD_LINE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('text')
    parser.add_argument('--sheet', action='store_true', help='the player already gave a finished sheet')
    args = parser.parse_args(argv)
    out = chargen(args.text, args.sheet) or {'stage': 'not_chargen'}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

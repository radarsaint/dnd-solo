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

# Well-known player options that are NOT in SRD 5.1 (names only, no rules text). A hit here
# always means "paste the rules or hand me the sheet". Not exhaustive: the pattern checks
# below catch named options that aren't listed.
NON_SRD_NAMES = {
    'feat': ('sharpshooter', 'great weapon master', 'polearm master', 'war caster', 'lucky', 'alert',
             'sentinel', 'crossbow expert', 'resilient', 'fey touched', 'fey-touched', 'shadow touched',
             'shadow-touched', 'elven accuracy', 'eldritch adept', 'tough', 'mobile', 'skilled',
             'magic initiate', 'telekinetic', 'telepathic', 'observant', 'mage slayer', 'savage attacker',
             'ritual caster', 'inspiring leader', 'heavy armor master', 'dual wielder', 'crusher', 'piercer',
             'slasher', 'skill expert', 'mounted combatant', 'healer', 'durable', 'athlete', 'keen mind',
             'linguist', 'medium armor master', 'martial adept', 'spell sniper', 'tavern brawler',
             'weapon master', 'defensive duelist', 'charger', 'shield master', 'metamagic adept',
             'fighting initiate', 'gift of the metallic dragon', 'actor', 'chef', 'poisoner'),
    'subclass': ('gloom stalker', 'beast master', 'horizon walker', 'monster slayer', 'fey wanderer',
                 'swarmkeeper', 'drakewarden', 'battle master', 'eldritch knight', 'echo knight',
                 'rune knight', 'samurai', 'cavalier', 'psi warrior', 'arcane archer', 'purple dragon knight',
                 'assassin', 'arcane trickster', 'swashbuckler', 'soulknife', 'scout', 'inquisitive',
                 'mastermind', 'phantom', 'hexblade', 'genie', 'fathomless', 'celestial', 'archfey',
                 'great old one', 'undying', 'undead', 'twilight', 'peace', 'order', 'forge', 'grave',
                 'tempest', 'trickery', 'war domain', 'light domain', 'knowledge', 'nature domain', 'arcana',
                 'death domain', 'vengeance', 'ancients', 'conquest', 'redemption', 'glory', 'watchers',
                 'oathbreaker', 'crown', 'zealot', 'totem warrior', 'ancestral guardian', 'storm herald',
                 'wild magic', 'beast', 'giant', 'battlerager', 'swords', 'valor', 'glamour', 'whispers',
                 'eloquence', 'creation', 'spirits', 'moon', 'shepherd', 'dreams', 'spores', 'stars',
                 'wildfire', 'kensei', 'drunken master', 'shadow', 'four elements', 'sun soul', 'mercy',
                 'astral self', 'long death', 'divine soul', 'shadow magic', 'storm sorcery', 'aberrant mind',
                 'clockwork soul', 'bladesinging', 'war magic', 'chronurgy', 'graviturgy', 'scribes',
                 'divination', 'abjuration', 'conjuration', 'enchantment', 'illusion', 'necromancy',
                 'transmutation', 'artificer', 'blood hunter', 'alchemist', 'armorer', 'artillerist',
                 'battle smith'),
    'species': ('aasimar', 'goliath', 'tabaxi', 'kenku', 'firbolg', 'genasi', 'tortle', 'aarakocra',
                'triton', 'yuan-ti', 'lizardfolk', 'bugbear', 'goblin', 'hobgoblin', 'kobold', 'orc',
                'warforged', 'changeling', 'shifter', 'kalashtar', 'harengon', 'fairy', 'owlin', 'satyr',
                'centaur', 'minotaur', 'githyanki', 'githzerai', 'eladrin', 'sea elf', 'shadar-kai',
                'duergar', 'drow', 'wood elf', 'astral elf', 'autognome', 'giff', 'hadozee', 'plasmoid',
                'thri-kreen', 'loxodon', 'simic hybrid', 'vedalken', 'leonin', 'dhampir', 'hexblood',
                'reborn', 'stout halfling', 'forest gnome', 'mountain dwarf', 'deep gnome', 'verdan',
                'grung', 'locathah', 'gnoll'),
    'spell': ('toll the dead', 'booming blade', 'green-flame blade', 'silvery barbs', 'mind sliver',
              'healing spirit', 'absorb elements', 'shadow blade', 'synaptic static', 'catapult', 'ice knife',
              'chaos bolt', 'find greater steed', 'spirit shroud', 'steel wind strike', "dragon's breath",
              'zephyr strike', 'hex', 'armor of agathys', 'arms of hadar', 'hunger of hadar', 'witch bolt',
              'ensnaring strike', 'hail of thorns', 'thunderous smite', 'searing smite', 'branding smite',
              'wrathful smite', 'blinding smite', 'staggering smite', 'banishing smite', 'destructive wave',
              'cordon of arrows', 'lightning arrow', 'conjure barrage', 'swift quiver', 'compelled duel',
              'crusader\'s mantle', 'aura of vitality', 'aura of life', 'aura of purity', 'elemental weapon',
              'beast sense', 'dissonant whispers', 'chromatic orb', 'tasha\'s mind whip', 'mind whip',
              'shadow of moil', 'summon beast', 'summon fey', 'summon undead', 'summon fiend',
              'summon celestial', 'summon aberration', 'summon construct', 'summon elemental',
              'summon draconic spirit', 'tidal wave', 'erupting earth', 'thunder step', 'vortex warp',
              'magnify gravity', 'sapping sting', 'frostbite', 'infestation', 'primal savagery',
              'sword burst', 'lightning lure', 'create bonfire', 'word of radiance', 'thunderclap',
              'gust', 'mold earth', 'shape water', 'control flames', 'magic stone', 'earth tremor',
              'tasha\'s caustic brew', 'caustic brew', 'web of fire', 'raulothim\'s psychic lance',
              'psychic lance', 'spray of cards', 'blade of disaster', 'mighty fortress', 'wall of light',
              'dawn', 'holy weapon', 'far step', 'enervation', 'negative energy flood', 'danse macabre',
              'shadow of moil', 'life transference', 'intellect fortress', 'sickening radiance'),
}
_NON_SRD_WORDS = {n: k for k, v in NON_SRD_NAMES.items() for n in v}
_NON_SRD_RE = re.compile(r"(?<![a-z'])(" + '|'.join(re.escape(n) for n in sorted(_NON_SRD_WORDS, key=len, reverse=True))
                         + r")(?![a-z'])", re.I)

_BUILD = re.compile(
    r"\b(build|make|create|roll up|level(?:ing)? up|multiclass|respec|new character|"
    r"character creation|chargen|which (?:feat|subclass|species|race|background)|"
    r"pick (?:a |my )?(?:feat|subclass|species|race|background|spells?))\b", re.I)
# Asking to take, play, learn or swap a player option counts even without a build verb.
_OPTION_ASK = re.compile(
    r"\b(can (?:i|my \w+|we)|could (?:i|my \w+)|should (?:i|my \w+)|may i|i(?:'d| would)? (?:want|like|wanna|plan) to|"
    r"i'?m (?:going|gonna|planning) to|let me|how about|what about|is|are)\b.{0,40}?"
    r"\b(take|takes|taking|play|playing|be|pick|choose|get|have|use|learn|know|prepare|swap|switch|go|grab|add|allowed)\b"
    r"|\b(play(?:ing)? (?:a|an|as)|take (?:the )?\w[\w' \-]{0,30} (?:feat|subclass|archetype|spell|cantrip)|"
    r"learn (?:the )?\w[\w' \-]{0,30} (?:spell|cantrip)|multiclass(?:ing)? into|subclass|archetype)\b", re.I)
_CHAR_NOUN = re.compile(r"\b(character|pc|sheet|build|feat|subclass|species|race|background|class|level|spell|"
                        r"cantrip|archetype|domain|oath|patron|circle|college|tradition|"
                        + '|'.join(re.escape(w) for w in SRD_OPTIONS['class']) + r")s?\b", re.I)
# Names that mark a non-SRD option: a later book, D&D Beyond, or an option word with a name
# that isn't an SRD option.
_BEYOND = re.compile(r"\b(tasha'?s?|xanathar'?s?|volo'?s?|mordenkainen'?s?|fizban'?s?|monsters of the multiverse|"
                     r"2024|phb 2024|one d&d|d&d beyond|dndbeyond|ua|unearthed arcana|homebrew)\b", re.I)
_NAMED = re.compile(r"\b([a-z][a-z'\-]*(?: [a-z][a-z'\-]*){0,2}) (domain|oath|circle|college|school|"
                    r"patron|path|way|archetype|conclave|bloodline|origin|subclass|feat|species|race|"
                    r"background|spell|cantrip)\b", re.I)
_NAMED_AFTER = re.compile(r"\b(domain|oath|circle|college|school|path|way) of (?:the )?([a-z][a-z'\-]*)", re.I)
_CLASS_WITH_ADJ = re.compile(r"\b((?:[a-z][a-z'\-]+ )?[a-z][a-z'\-]+) (" + '|'.join(SRD_OPTIONS['class']) + r")\b", re.I)
_FILLER = {'a', 'an', 'the', 'my', 'new', 'level', 'srd', 'first', 'second', 'third', 'fourth', 'fifth',
           'this', 'that', 'good', 'basic', 'simple', 'human', 'build', 'make', 'create', 'pick', 'which',
           'what', 'help', 'me', 'to', 'up', 'for', 'some', 'level-1', 'multiclass', 'with', 'and', 'or',
           'core', 'beginner', 'starting', 'test', 'quick', 'strong', 'support', 'melee', 'ranged',
           'i', 'can', 'could', 'should', 'would', 'want', 'like', 'take', 'taking', 'play', 'playing', 'be',
           'get', 'have', 'use', 'learn', 'choose', 'as', 'of', 'from', 'is', 'it', 'try', 'go', 'into',
           'instead', 'maybe', 'also', 'one', 'cool', 'fun', 'your', 'his', 'her', 'their', 'our'}
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
    if not (_BUILD.search(text) or _OPTION_ASK.search(text) or _BEYOND.search(text)):
        return False
    return bool(_CHAR_NOUN.search(text) or _NON_SRD_RE.search(text) or _BEYOND.search(text)
                or any(re.search(r'\b' + re.escape(w) + r'\b', text, re.I) for w in _SRD_WORDS))


def _known_non_srd(text):
    out = []
    for m in _NON_SRD_RE.finditer(text or ''):
        name = m.group(1).lower()
        out.append(f'{name} {_NON_SRD_WORDS[name]}' if _NON_SRD_WORDS[name] in ('feat', 'spell') else name)
    return out


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
    found = list(dict.fromkeys(_known_non_srd(text) + _unknown_names(text)))
    # Keep the fullest name: 'gloom stalker ranger' over 'gloom stalker'.
    unknown = sorted((n for n in found if not any(n != o and n in o for o in found)), key=len, reverse=True)
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

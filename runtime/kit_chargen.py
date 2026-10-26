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


# Proficiency sources (fix: PR 145 playtest #5). Names only, from SRD 5.1 and SRD 5.2 class tables.
_SIMPLE = ('club', 'dagger', 'greatclub', 'handaxe', 'javelin', 'light hammer', 'mace', 'quarterstaff',
           'sickle', 'spear', 'light crossbow', 'dart', 'shortbow', 'sling')
_ALL_ARMOR = ('light armor', 'medium armor', 'heavy armor')
CLASS_PROFICIENCIES = {
    'barbarian': (('light armor', 'medium armor', 'shields'), ('simple weapons', 'martial weapons'), ()),
    'bard': (('light armor',), ('simple weapons', 'hand crossbow', 'longsword', 'rapier', 'shortsword'),
             ('musical instrument',)),
    'cleric': (('light armor', 'medium armor', 'shields'), ('simple weapons',), ()),
    'druid': (('light armor', 'medium armor', 'shields'),
              ('simple weapons', 'club', 'dagger', 'dart', 'javelin', 'mace', 'quarterstaff', 'scimitar',
               'sickle', 'sling', 'spear'), ('herbalism kit',)),
    'fighter': (_ALL_ARMOR + ('shields',), ('simple weapons', 'martial weapons'), ()),
    'monk': ((), ('simple weapons', 'shortsword', 'martial weapons with the light property'),
             ("artisan's tools", 'musical instrument')),
    'paladin': (_ALL_ARMOR + ('shields',), ('simple weapons', 'martial weapons'), ()),
    'ranger': (('light armor', 'medium armor', 'shields'), ('simple weapons', 'martial weapons'), ()),
    'rogue': (('light armor',), ('simple weapons', 'hand crossbow', 'longsword', 'rapier', 'shortsword',
                                 'martial weapons with the finesse or light property'), ("thieves' tools",)),
    'sorcerer': ((), ('simple weapons', 'dagger', 'dart', 'sling', 'quarterstaff', 'light crossbow'), ()),
    'warlock': (('light armor',), ('simple weapons',), ()),
    'wizard': ((), ('simple weapons', 'dagger', 'dart', 'sling', 'quarterstaff', 'light crossbow'), ()),
}
SRD_FEAT_PROFICIENCIES = {
    'lightly armored': ('light armor',),
    'moderately armored': ('medium armor', 'shields'),
    'heavily armored': ('heavy armor',),
}
PROF_KEYS = (('armor_proficiencies', 0), ('weapon_proficiencies', 1), ('tool_proficiencies', 2))
UNSOURCED_LINE = ("One thing before we start, and I'm asking, not ruling: where did {name} learn to use "
                  "{prof}? I can't find it in the class, the people, the background, or the feats. "
                  "If there's a story, pitch it and we'll settle it together.")


_CATEGORY = re.compile(r'\b(?:armor|weapons|tools|supplies|kit|instruments?)\b', re.I)


def natural_proficiency(prof):
    """Table wording for one proficiency: 'Shield' -> 'a shield', "Calligrapher's Supplies" stays plural."""
    p = re.sub(r'\s+', ' ', str(prof or '').strip()).lower()
    if p in ('shield', 'shields'):
        return 'a shield'
    if _CATEGORY.search(p) and not p.endswith('kit'):
        return p
    if p.endswith('kit'):
        return ('an ' if p[:1] in 'aeiou' else 'a ') + p
    if p.endswith('s') and not p.endswith('ss'):
        return p
    return ('an ' if p[:1] in 'aeiou' else 'a ') + p


def natural_list(items):
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1]) + f', and {items[-1]}'


def _fold(text):
    s = (text or '').strip().casefold().replace('\u2019', "'")
    s = re.sub(r'\s+', ' ', s)
    return s[:-1] if s.endswith('s') and not s.endswith("ss") else s


def _granted_by(prof, grants):
    f = _fold(prof)
    for g in grants:
        gf = _fold(g)
        if f == gf or f == gf.replace(' armor', '') or (gf == 'simple weapon' and f in _SIMPLE):
            return True
        if gf in ('shield',) and f in ('shield', 'shields'):
            return True
    return False


def _classes(sheet):
    found = [c for c in CLASS_PROFICIENCIES if re.search(rf'\b{c}\b', str(sheet.get('class', '')).casefold())]
    return found


def proficiency_sources(sheet):
    """Check each armor, weapon, and tool proficiency against where it comes from.

    Sources: the class table (SRD), SRD armor feats, the sheet's own text for its species,
    background, features and feats, and any settled entry in `proficiency_sources`
    ({name: "where it came from"}). Anything with no source is flagged for Kit to ask about
    once, in the fiction. This never rules: it only reports. Skills are not checked here.
    """
    classes = _classes(sheet)
    settled = {_fold(k): v for k, v in (sheet.get('proficiency_sources') or {}).items()}
    feats = [str(f) for f in (sheet.get('feats') or [])]
    texts = [str(t) for t in (sheet.get('features') or [])] + feats + [
        str(sheet.get('background') or ''), str(sheet.get('ancestry') or '')]
    checked, unsourced = [], []
    for key, idx in PROF_KEYS:
        for prof in sheet.get(key) or []:
            source = None
            if _fold(prof) in settled:
                source = f'settled: {settled[_fold(prof)]}'
            for c in classes:
                if source is None and _granted_by(prof, CLASS_PROFICIENCIES[c][idx]):
                    source = f'class: {c}'
            for feat in feats:
                grants = SRD_FEAT_PROFICIENCIES.get(_fold(feat), ())
                if source is None and _granted_by(prof, grants):
                    source = f'feat: {feat}'
            for text in texts:
                if source is None and _fold(prof) and _fold(prof) in _fold(text):
                    source = f'sheet text: {text}'
            entry = {'proficiency': prof, 'kind': key, 'source': source}
            checked.append(entry)
            if source is None:
                unsourced.append(entry)
    name = character_name(sheet)
    out = {'stage': 'proficiency_check', 'checked': checked, 'unsourced': unsourced,
           'classes_recognized': classes, 'auto_ruled': False, 'raise_once': True,
           'next_step': ('Nothing is ruled here. For each unsourced entry, ask the player once, in the '
                         'fiction, where it came from. Until it is settled, play it by the rules as written. '
                         'Record a settled answer in the sheet under proficiency_sources; do not ask again.')}
    if unsourced:
        out['table_line'] = UNSOURCED_LINE.format(
            name=name, prof=natural_list(natural_proficiency(u['proficiency']) for u in unsourced))
    if not classes:
        out['note'] = 'Class not recognized from the SRD; class proficiencies could not be checked.'
    return out


_COPY = re.compile(r'^\s*(?:copy of\s+)+', re.I)
_DUP = re.compile(r'\s*(?:\(\d+\)|-\s*copy|\bcopy\b)\s*$', re.I)


def character_name(sheet):
    """The character's real name, not a file title like 'Copy of Nik' or 'Nik (2)'."""
    raw = str(sheet.get('character_name') or sheet.get('name') or '').strip()
    name = _DUP.sub('', _COPY.sub('', raw)).strip()
    return name or raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('text', nargs='?', default='')
    parser.add_argument('--sheet', action='store_true', help='the player already gave a finished sheet')
    parser.add_argument('--check-sheet', metavar='FILE',
                        help='check a sheet file: each proficiency against its source (text is ignored)')
    args = parser.parse_args(argv)
    if args.check_sheet:
        with open(args.check_sheet, encoding='utf-8') as fh:
            out = proficiency_sources(json.load(fh))
    else:
        out = chargen(args.text, args.sheet) or {'stage': 'not_chargen'}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

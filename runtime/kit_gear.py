"""Equipment audit (Brendon's ruling, 2026-10-19): the sheet against the gear in use.

Kit failed an intentional test: a wizard with no shield proficiency held a shield, took its
bonuses and cast freely, and nothing flagged it. The engine now checks the loaded sheet at
session start (the sheet is loaded) and after every rest, for any class or build:

* armor and shield proficiency against the armor worn and the shield held (class table,
  multiclass gains, armor feats and a sheet's own ``armor_proficiencies``);
* the attunement limit (3 items, SRD) and an item's "requires attunement by a ..." class.

Each mismatch becomes a pending clarification (``state['gear']['clarify']``). Kit raises it
once, in voice, at a natural moment (a substantive turn, never a window or table talk), as an
in-fiction question that states the rule as written. The player's answer is game state
(``gear_state``: "stows the shield", "keeps it on his arm").

While non-proficient armor or a non-proficient shield is in use the engine enforces the SRD:
disadvantage on any ability check, saving throw or attack roll that uses Strength or
Dexterity, and no spellcasting. Donning or doffing a shield costs the action in a fight, and
every swap costs its own action (no free drop-and-ready around each cast). An item's own
advantage (a shield that grants initiative or Perception advantage) applies only while it is
in use, and advantage and disadvantage on the same roll cancel (SRD).

Nothing here knows any particular character or item beyond the SRD tables below; a sheet can
describe any item itself as a dict: {name, type: shield|light|medium|heavy, equipped,
requires_attunement, attuned, attunement_by, advantage: [initiative|<skill>], ac_bonus}.
"""
import copy
import re

from .state_context import require

ATTUNEMENT_LIMIT = 3
CATEGORIES = ('light', 'medium', 'heavy', 'shield')
# SRD armor: (category, strength needed or None). Longest names first when matching.
ARMOR = {'padded armor': ('light', None), 'padded': ('light', None), 'leather armor': ('light', None),
         'studded leather': ('light', None), 'hide armor': ('medium', None), 'chain shirt': ('medium', None),
         'scale mail': ('medium', None), 'breastplate': ('medium', None), 'half plate': ('medium', None),
         'ring mail': ('heavy', None), 'chain mail': ('heavy', 13), 'splint armor': ('heavy', 15),
         'splint mail': ('heavy', 15), 'plate armor': ('heavy', 15), 'full plate': ('heavy', 15),
         'plate mail': ('heavy', 15)}
_ARMOR = re.compile(r'\b(' + '|'.join(re.escape(n) for n in sorted(ARMOR, key=len, reverse=True)) + r')\b')
_SHIELD = re.compile(r'\bshield\b')
# SRD class armor training: a first class, and what multiclassing into it adds.
CLASS_ARMOR = {'barbarian': {'light', 'medium', 'shield'}, 'bard': {'light'},
               'cleric': {'light', 'medium', 'shield'}, 'druid': {'light', 'medium', 'shield'},
               'fighter': {'light', 'medium', 'heavy', 'shield'}, 'monk': set(),
               'paladin': {'light', 'medium', 'heavy', 'shield'}, 'ranger': {'light', 'medium', 'shield'},
               'rogue': {'light'}, 'sorcerer': set(), 'warlock': {'light'}, 'wizard': set(),
               'artificer': {'light', 'medium', 'shield'}}
MULTICLASS_ARMOR = {'barbarian': {'shield'}, 'bard': {'light'}, 'cleric': {'light', 'medium', 'shield'},
                    'druid': {'light', 'medium', 'shield'}, 'fighter': {'light', 'medium', 'shield'},
                    'monk': set(), 'paladin': {'light', 'medium', 'shield'}, 'ranger': {'light', 'medium', 'shield'},
                    'rogue': {'light'}, 'sorcerer': set(), 'warlock': {'light'}, 'wizard': set(),
                    'artificer': {'light', 'medium', 'shield'}}
FEAT_ARMOR = {'lightly armored': {'light'}, 'moderately armored': {'medium', 'shield'},
              'heavily armored': {'heavy'}}
ANCESTRY_ARMOR = {'mountain dwarf': {'light', 'medium'}}
# Items the SRD or the published rules name, by what matters here. Anything else describes itself.
KNOWN_ITEMS = {
    'sentinel shield': {'type': 'shield', 'advantage': ['initiative', 'perception']},
    'animated shield': {'type': 'shield', 'requires_attunement': True},
    'arrow-catching shield': {'type': 'shield', 'requires_attunement': True},
    'spellguard shield': {'type': 'shield', 'requires_attunement': True},
    'shield of missile attraction': {'type': 'shield', 'requires_attunement': True},
    'amulet of health': {'requires_attunement': True}, 'bracers of defense': {'requires_attunement': True},
    'cloak of protection': {'requires_attunement': True}, 'ring of protection': {'requires_attunement': True},
    'cloak of displacement': {'requires_attunement': True}, 'cloak of elvenkind': {'requires_attunement': True},
    'boots of speed': {'requires_attunement': True}, 'boots of elvenkind': {'requires_attunement': False},
    'gauntlets of ogre power': {'requires_attunement': True}, 'headband of intellect': {'requires_attunement': True},
    'belt of giant strength': {'requires_attunement': True}, 'pearl of power': {'requires_attunement': True},
    'ring of evasion': {'requires_attunement': True}, 'ring of free action': {'requires_attunement': True},
    'ring of spell storing': {'requires_attunement': True}, 'periapt of wound closure': {'requires_attunement': True},
    'staff of power': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'staff of the magi': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'robe of the archmagi': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'holy avenger': {'requires_attunement': True, 'attunement_by': ['paladin']},
    'wand of the war mage': {'requires_attunement': True, 'attunement_by': ['spellcaster']},
    'elven chain': {'type': 'medium', 'proficient_anyway': True},
}
GEAR_KEYS = ('armor', 'equipment', 'gear', 'magic_items', 'inventory', 'items')
SPELLCASTERS = ('bard', 'cleric', 'druid', 'paladin', 'ranger', 'sorcerer', 'warlock', 'wizard', 'artificer')
CATEGORY_WORDS = {'light': 'light armor', 'medium': 'medium armor', 'heavy': 'heavy armor', 'shield': 'shields'}

RULE_ARMOR = ('SRD: wearing armor you are not proficient with gives disadvantage on any ability check, saving '
              'throw or attack roll that uses Strength or Dexterity, and you cannot cast spells.')
RULE_SHIELD = ('SRD: holding a shield you are not proficient with gives disadvantage on any ability check, '
               'saving throw or attack roll that uses Strength or Dexterity, and you cannot cast spells. '
               'Readying or stowing a shield takes your action.')
RULE_ATTUNE = 'SRD: a creature can be attuned to no more than three magic items at a time.'
RULE_ATTUNE_BY = 'SRD: an item that requires attunement by a {who} can only be attuned by one.'
# -- proficiency sources (Brendon, 2026-10-19): a claimed proficiency needs a source ----------
# A sheet's own armor/weapon/tool lists are claims. Each is checked against what its class,
# species, background and feats grant (SRD 5.1 and the 2024 rules: a grant in either counts).
# A claim nothing grants is UNVERIFIED and not trusted until Kit, asking in the fiction, rules
# on the player's answer (state['homebrew_rulings']). Choice grants ("one artisan's tools") are
# kept as a category: a claim in that category is sourced. An unknown build verifies nothing
# and asks nothing (never guessed).
SIMPLE_WEAPONS = ('club', 'dagger', 'greatclub', 'handaxe', 'javelin', 'light hammer', 'mace', 'quarterstaff',
                  'sickle', 'spear', 'light crossbow', 'dart', 'shortbow', 'sling')
MARTIAL_WEAPONS = ('battleaxe', 'flail', 'glaive', 'greataxe', 'greatsword', 'halberd', 'lance', 'longsword',
                   'maul', 'morningstar', 'pike', 'rapier', 'scimitar', 'shortsword', 'trident', 'war pick',
                   'warhammer', 'whip', 'blowgun', 'hand crossbow', 'heavy crossbow', 'longbow', 'net')
ARTISAN_TOOLS = ("alchemist's supplies", "brewer's supplies", "calligrapher's supplies", "carpenter's tools",
                 "cartographer's tools", "cobbler's tools", "cook's utensils", "glassblower's tools",
                 "jeweler's tools", "leatherworker's tools", "mason's tools", "painter's supplies",
                 "potter's tools", "smith's tools", "tinker's tools", "weaver's tools", "woodcarver's tools")
INSTRUMENTS = ('bagpipes', 'drum', 'dulcimer', 'flute', 'horn', 'lute', 'lyre', 'pan flute', 'shawm', 'viol')
GAMING_SETS = ('dice set', 'dice', 'dragonchess set', 'playing card set', 'playing cards', 'three-dragon ante set')
# Grant = {'armor': categories, 'weapons': 'simple'|'martial'|weapon names, 'tools': tool names or
# 'artisan'|'instrument'|'gaming'|'any' for a choice}.
CLASS_GRANTS = {
    'barbarian': {'weapons': {'simple', 'martial'}},
    'bard': {'weapons': {'simple', 'hand crossbow', 'longsword', 'rapier', 'shortsword'}, 'tools': {'instrument'}},
    'cleric': {'weapons': {'simple'}},
    'druid': {'weapons': {'simple', 'club', 'dagger', 'dart', 'javelin', 'mace', 'quarterstaff', 'scimitar', 'sickle',
                          'sling', 'spear'}, 'tools': {"herbalism kit"}},
    'fighter': {'weapons': {'simple', 'martial'}},
    'monk': {'weapons': {'simple', 'shortsword', 'martial-light'}, 'tools': {'artisan', 'instrument'}},
    'paladin': {'weapons': {'simple', 'martial'}},
    'ranger': {'weapons': {'simple', 'martial'}},
    'rogue': {'weapons': {'simple', 'hand crossbow', 'longsword', 'rapier', 'shortsword', 'scimitar', 'whip'},
              'tools': {"thieves' tools"}},
    'sorcerer': {'weapons': {'simple', 'dagger', 'dart', 'sling', 'quarterstaff', 'light crossbow'}},
    'warlock': {'weapons': {'simple'}},
    'wizard': {'weapons': {'simple', 'dagger', 'dart', 'sling', 'quarterstaff', 'light crossbow'}},
    'artificer': {'weapons': {'simple'}, 'tools': {"thieves' tools", "tinker's tools", 'artisan'}},
}
MULTICLASS_GRANTS = {
    'barbarian': {'weapons': {'simple', 'martial'}}, 'bard': {'tools': {'instrument'}},
    'fighter': {'weapons': {'simple', 'martial'}}, 'monk': {'weapons': {'simple', 'shortsword'}},
    'paladin': {'weapons': {'simple', 'martial'}}, 'ranger': {'weapons': {'simple', 'martial'}},
    'rogue': {'tools': {"thieves' tools"}}, 'warlock': {'weapons': {'simple'}},
    'artificer': {'tools': {"thieves' tools", "tinker's tools"}},
}
SPECIES_GRANTS = {
    'dwarf': {'weapons': {'battleaxe', 'handaxe', 'light hammer', 'warhammer'},
              'tools': {"smith's tools", "brewer's supplies", "mason's tools"}},
    'mountain dwarf': {'armor': {'light', 'medium'}},
    'elf': {'weapons': {'longsword', 'shortsword', 'shortbow', 'longbow'}},
    'drow': {'weapons': {'rapier', 'shortsword', 'hand crossbow'}},
    'githyanki': {'armor': {'light', 'medium'}, 'weapons': {'shortsword', 'longsword', 'greatsword'}},
    'hobgoblin': {'armor': {'light'}, 'weapons': {'martial'}},
    'tortle': {'tools': {"herbalism kit"}},
}
BACKGROUND_GRANTS = {
    'acolyte': {'tools': {"calligrapher's supplies"}}, 'artisan': {'tools': {'artisan'}},
    'charlatan': {'tools': {'disguise kit', 'forgery kit'}}, 'criminal': {'tools': {"thieves' tools", 'gaming'}},
    'entertainer': {'tools': {'disguise kit', 'instrument'}}, 'farmer': {'tools': {"carpenter's tools"}},
    'folk hero': {'tools': {'artisan', 'vehicles (land)'}}, 'guard': {'tools': {'gaming'}},
    'guide': {'tools': {"cartographer's tools"}}, 'guild artisan': {'tools': {'artisan'}},
    'hermit': {'tools': {'herbalism kit'}}, 'merchant': {'tools': {"navigator's tools"}},
    'noble': {'tools': {'gaming'}}, 'outlander': {'tools': {'instrument'}},
    'sage': {'tools': {"calligrapher's supplies"}}, 'sailor': {'tools': {"navigator's tools", 'vehicles (water)'}},
    'scribe': {'tools': {"calligrapher's supplies"}}, 'soldier': {'tools': {'gaming', 'vehicles (land)'}},
    'urchin': {'tools': {'disguise kit', "thieves' tools"}}, 'wayfarer': {'tools': {"thieves' tools"}},
}
# Feats that grant training. War Caster, Magic Initiate and an Ability Score Improvement grant
# none: War Caster lets you perform somatic components with weapons or a shield in hand, it is
# not shield training.
FEAT_GRANTS = {
    'lightly armored': {'armor': {'light'}}, 'moderately armored': {'armor': {'medium', 'shield'}},
    'heavily armored': {'armor': {'heavy'}}, 'shield master': {}, 'weapon master': {'weapons': {'any'}},
    'martial weapon training': {'weapons': {'simple', 'martial'}}, 'martial adept': {'tools': {'artisan'}},
    'skilled': {'tools': {'any'}}, 'crafter': {'tools': {'artisan'}}, 'musician': {'tools': {'instrument'}},
    'tavern brawler': {'weapons': {'improvised'}},
}
# Subclass grants (Nagatha's 59ce12a review, F7): (class, a word of the subclass) -> grant. SRD 5.1
# (Life Domain) and the published 2014/2024 subclasses; a grant in any of them counts.
ONE_HANDED_MELEE = ('battleaxe', 'flail', 'longsword', 'morningstar', 'rapier', 'scimitar', 'shortsword',
                    'trident', 'war pick', 'warhammer', 'whip')
SUBCLASS_GRANTS = {
    ('cleric', 'life'): {'armor': {'heavy'}},
    ('cleric', 'nature'): {'armor': {'heavy'}},
    ('cleric', 'tempest'): {'armor': {'heavy'}, 'weapons': {'martial'}},
    ('cleric', 'war'): {'armor': {'heavy'}, 'weapons': {'martial'}},
    ('cleric', 'forge'): {'armor': {'heavy'}},
    ('cleric', 'order'): {'armor': {'heavy'}},
    ('cleric', 'twilight'): {'armor': {'heavy'}, 'weapons': {'martial'}},
    ('cleric', 'death'): {'weapons': {'martial'}},
    ('bard', 'valor'): {'armor': {'medium', 'shield'}, 'weapons': {'martial'}},
    ('bard', 'swords'): {'armor': {'medium'}, 'weapons': {'scimitar'}},
    ('warlock', 'hexblade'): {'armor': {'medium', 'shield'}, 'weapons': {'martial'}},
    ('wizard', 'bladesinging'): {'armor': {'light'}, 'weapons': {'onehanded'}},
    ('wizard', 'bladesinger'): {'armor': {'light'}, 'weapons': {'onehanded'}},
    ('artificer', 'armorer'): {'armor': {'heavy'}},
    ('artificer', 'battle smith'): {'weapons': {'martial'}},
    ('rogue', 'assassin'): {'tools': {'disguise kit', "poisoner's kit"}},
    ('rogue', 'mastermind'): {'tools': {'disguise kit', 'forgery kit', 'gaming'}},
}
# 2024 class options a sheet lists as a feature: Divine Order (Protector), Primal Order (Warden).
OPTION_GRANTS = {('cleric', 'protector'): {'armor': {'heavy'}, 'weapons': {'martial'}},
                 ('druid', 'warden'): {'armor': {'medium'}, 'weapons': {'martial'}}}
KINDS = ('armor', 'weapons', 'tools')
CLAIM_KEYS = {'armor': ('armor_proficiencies',), 'weapons': ('weapon_proficiencies',), 'tools': ('tool_proficiencies',)}
CLAIM_WORDS = {'armor': {'light': 'light armor training', 'medium': 'medium armor training',
                         'heavy': 'heavy armor training', 'shield': 'shield training'}}
RULE_SOURCE = ('Rules as written: a proficiency comes from your class, species, background or a feat. Nothing on '
               'this sheet grants {claim}, so without a source you have no proficiency: {without}')
WITHOUT = {'armor': RULE_ARMOR[len('SRD: '):], 'shield': RULE_SHIELD[len('SRD: '):],
           'weapons': 'you do not add your proficiency bonus to attack rolls with it.',
           'tools': 'you do not add your proficiency bonus to ability checks made with it.'}
WAR_CASTER_NOTE = ' War Caster covers somatic components with a shield in hand; it grants no proficiency.'
RULINGS = ('granted', 'granted_with_cost', 'declined')

CLARIFY_RULE = (
    'Equipment clarification (gear_clarify): the engine found gear on the sheet that does not fit the rules. '
    'Raise it once, now, in your own voice, as an in-fiction clarifying question at a natural point in this '
    'turn: name the item, state the rule as written (gear_clarify.rule), and ask what the character does '
    '(gear_clarify.ask). Never decide it for the player; the engine records the answer.')


def ident(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name or '').casefold()).strip('_')


def _norm(name):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\' -]+', ' ', str(name or '').casefold())).strip()


def classes(sheet):
    """The sheet's classes in order: 'Fighter 3 / Wizard 2', 'Cleric (Life)', 'Wizard'."""
    text = str((sheet or {}).get('class') or '').casefold()
    found = []
    for match in re.finditer(r'[a-z]+', re.sub(r'\([^)]*\)', ' ', text)):
        word = match.group(0)
        if word in CLASS_ARMOR and word not in found:
            found.append(word)
    return found


def subclasses(sheet):
    """[(class, subclass text)] from 'Cleric (Life)', 'Fighter 1 / Cleric (Life Domain) 3', or a
    sheet's own ``subclass`` (the first class)."""
    text = str((sheet or {}).get('class') or '').casefold()
    out = [(m.group(1), m.group(2).strip()) for m in re.finditer(r'([a-z]+)\s*(?:\d+\s*)?\(([^)]*)\)', text)
           if m.group(1) in CLASS_ARMOR]
    extra = (sheet or {}).get('subclass')
    found = classes(sheet)
    if extra and found:
        out.append((found[0], str(extra).casefold()))
    return out


def proficiencies(sheet, rulings=None):
    """The armor categories (light, medium, heavy, shield) the sheet is trained in: what its class,
    species, background and feats grant, plus a claim a homebrew ruling granted. A claim the sheet
    lists with no source is not trusted. None when the build is unknown: never guessed."""
    granted = sources(sheet)
    if granted is None:
        return None
    out = {cat for cat in granted['armor'] if cat in CATEGORIES}
    for c in verify(sheet, rulings) or ():
        if c['kind'] == 'armor' and c['ruling'] and c['ruling']['verdict'] in RULINGS[:2]:
            out.add(c['claim'])
    return out


def items(sheet):
    """Every armor, shield or attunement item on the sheet:
    [{id, name, type (light|medium|heavy|shield|None), equipped, requires_attunement, attuned,
      attunement_by, advantage, ac_bonus, str_needed, proficient_anyway}]"""
    out, seen = [], set()
    for key in GEAR_KEYS:
        value = (sheet or {}).get(key)
        if isinstance(value, (str, dict)):
            value = [value]
        for entry in value or ():
            detail = dict(entry) if isinstance(entry, dict) else {'name': entry}
            name = str(detail.get('name') or '').strip()
            if not name or ident(name) in seen:
                continue
            folded = _norm(name)
            known = next((v for k, v in KNOWN_ITEMS.items() if k in folded), {})
            kind = detail.get('type') or detail.get('kind') or known.get('type')
            armor = _ARMOR.search(folded)
            if kind not in CATEGORIES:
                kind = 'shield' if _SHIELD.search(folded) else ARMOR[armor.group(1)][0] if armor else None
            needs = detail.get('requires_attunement', detail.get('attunement', known.get('requires_attunement', False)))
            if not kind and not needs:
                continue
            seen.add(ident(name))
            by = detail.get('attunement_by', known.get('attunement_by'))
            out.append({'id': ident(name), 'name': name, 'type': kind,
                        'equipped': detail.get('equipped', True) is not False,
                        'requires_attunement': bool(needs),
                        'attuned': bool(needs) and detail.get('attuned', True) is not False,
                        'attunement_by': [str(b).casefold() for b in (by if isinstance(by, list) else [by] if by else [])],
                        'advantage': [str(a).casefold() for a in detail.get('advantage', known.get('advantage', ()))],
                        'ac_bonus': int(detail.get('ac_bonus', 2 if kind == 'shield' else 0)),
                        'str_needed': ARMOR[armor.group(1)][1] if armor and kind == ARMOR[armor.group(1)][0] else None,
                        'proficient_anyway': bool(detail.get('proficient_anyway', known.get('proficient_anyway')))})
    return out


def _texts(sheet, *keys):
    out = []
    for key in keys:
        value = (sheet or {}).get(key)
        for entry in value if isinstance(value, list) else [value] if value else ():
            out.append(_norm(entry.get('name') if isinstance(entry, dict) else entry))
    return out


def _armor_words(word):
    word = _norm(word)
    if 'all armor' in word:
        return {'light', 'medium', 'heavy'}
    return {cat for cat in CATEGORIES if re.search(r'\b' + cat + r's?\b', word)}


def _weapon_word(word):
    word = re.sub(r'\bweapons?\b', '', _norm(word)).strip()
    return re.sub(r'(?<=[a-rt-z])s$', '', word)


def _tool_category(tool):
    if tool in ARTISAN_TOOLS or re.search(r"(supplies|tools|utensils)$", tool) and tool not in (
            "thieves' tools", "navigator's tools"):
        return 'artisan'
    if any(tool.startswith(i) or tool == i + 's' for i in INSTRUMENTS):
        return 'instrument'
    if any(g in tool for g in ('dice', 'card', 'dragonchess', 'three-dragon')):
        return 'gaming'
    return None


def sources(sheet):
    """{kind: {granted: [source label]}} from class, species, background and feats; None when the
    build is unknown (no known class)."""
    found = classes(sheet)
    if not found:
        return None
    out = {kind: {} for kind in KINDS}

    def grant(label, table):
        for kind in KINDS:
            for what in table.get(kind, ()):
                out[kind].setdefault(what, []).append(label)

    grant(f'{found[0].title()} class', dict(CLASS_GRANTS.get(found[0], {}), armor=CLASS_ARMOR[found[0]]))
    for extra in found[1:]:
        grant(f'{extra.title()} multiclass', dict(MULTICLASS_GRANTS.get(extra, {}), armor=MULTICLASS_ARMOR[extra]))
    ancestry = _norm((sheet or {}).get('ancestry') or (sheet or {}).get('species') or (sheet or {}).get('race'))
    for name, table in SPECIES_GRANTS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', ancestry) and not (name == 'elf' and 'half-elf' in ancestry):
            grant(f'{name.title()} species', table)
    for klass, sub in subclasses(sheet):
        for (owner, word), table in SUBCLASS_GRANTS.items():
            if owner == klass and re.search(r'\b' + re.escape(word) + r'\b', sub):
                grant(f'{klass.title()} ({sub.title()}) subclass', table)
    for text in _texts(sheet, 'features', 'feats'):
        for (owner, word), table in OPTION_GRANTS.items():
            if owner in found and re.search(r'\b' + word + r'\b', text) and (
                    text.startswith(word) or 'order' in text):
                grant(f'{owner.title()} {word.title()} option', table)
    background = _norm((sheet or {}).get('background'))
    for name, table in BACKGROUND_GRANTS.items():
        if re.fullmatch(re.escape(name) + r'( background)?', background):
            grant(f'{name.title()} background', table)
    for text in _texts(sheet, 'features', 'feats'):
        for name, table in FEAT_GRANTS.items():
            if text.startswith(name):
                grant(f'{name.title()} feat', table)
    return out


def claims(sheet):
    """{kind: [claim]} the sheet lists itself: armor categories, weapons ('simple', 'martial' or a
    weapon), tools."""
    sheet = sheet or {}
    nested = sheet.get('proficiencies') if isinstance(sheet.get('proficiencies'), dict) else {}
    out = {}
    for kind in KINDS:
        raw = []
        for key in CLAIM_KEYS[kind]:
            value = sheet.get(key)
            raw += value if isinstance(value, list) else [value] if value else []
        value = nested.get(kind) or nested.get(kind.rstrip('s'))
        raw += value if isinstance(value, list) else [value] if value else []
        words = []
        for word in raw:
            if kind == 'armor':
                words += sorted(_armor_words(word))
            elif kind == 'weapons':
                words.append(_weapon_word(word))
            else:
                words.append(_norm(word))
        out[kind] = list(dict.fromkeys(w for w in words if w))
    return out


def _sourced(kind, claim, granted):
    if claim in granted:
        return granted[claim]
    if kind == 'weapons':
        if 'any' in granted:
            return granted['any']
        if claim in SIMPLE_WEAPONS and 'simple' in granted:
            return granted['simple']
        if claim in MARTIAL_WEAPONS and 'martial' in granted:
            return granted['martial']
        if claim in ONE_HANDED_MELEE and 'onehanded' in granted:
            return granted['onehanded']
    if kind == 'tools':
        category = _tool_category(claim)
        if category and category in granted:
            return granted[category]
        if 'any' in granted:
            return granted['any']
    return None


def ruling_for(rulings, claim_id):
    """The latest homebrew ruling on this claim, or None."""
    return next((r for r in reversed(list(rulings or ())) if r.get('claim_id') == claim_id), None)


def claim_id(kind, claim):
    return f'proficiency:{kind}:{ident(claim)}'


def verify(sheet, rulings=None):
    """[{kind, claim, id, sources, ruling}] for every claim on the sheet; sources [] = unverified.
    None when the build is unknown."""
    granted = sources(sheet)
    if granted is None:
        return None
    out = []
    for kind, listed in claims(sheet).items():
        for claim in listed:
            cid = claim_id(kind, claim)
            out.append({'kind': kind, 'claim': claim, 'id': cid, 'sources': _sourced(kind, claim, granted[kind]) or [],
                        'ruling': ruling_for(rulings, cid)})
    return out


def unverified(sheet, rulings=None):
    """Claims with no source and no ruling granting them."""
    return [c for c in verify(sheet, rulings) or () if not c['sources']
            and not (c['ruling'] and c['ruling']['verdict'] in RULINGS[:2])]


def claim_label(kind, claim):
    return CLAIM_WORDS.get(kind, {}).get(claim) or (
        f'{claim} weapon training' if claim in ('simple', 'martial') else f'training with {claim}' if kind == 'weapons'
        else f'proficiency with {claim}')


def _claim_issue(sheet, c):
    label = claim_label(c['kind'], c['claim'])
    without = WITHOUT['shield'] if c['claim'] == 'shield' else WITHOUT[c['kind']]
    war_caster = c['claim'] == 'shield' and any(t.startswith('war caster') for t in _texts(sheet, 'features', 'feats'))
    return {'id': c['id'], 'item': None, 'name': label, 'issue': 'unverified_proficiency', 'kind': c['kind'],
            'claim': c['claim'],
            'rule': RULE_SOURCE.format(claim=label, without=without) + (WAR_CASTER_NOTE if war_caster else ''),
            'ask': f"Your sheet says {label}. Where's that from?"}


def _proficient(item, trained):
    return trained is None or item['proficient_anyway'] or item['type'] in trained


def audit(sheet, rulings=None):
    """The sheet's mismatches, for any build: [{id, item, issue, rule, ask}] (empty: nothing to ask).
    A claimed proficiency with no source is asked about first (where is that from?); the gear
    question for that category waits on it, and a ruling (any verdict) is never asked again."""
    trained = proficiencies(sheet, rulings)
    found = [_claim_issue(sheet, c) for c in verify(sheet, rulings) or ()
             if not c['sources'] and not c['ruling']]
    claimed = {c['claim'] for c in verify(sheet, rulings) or () if c['kind'] == 'armor' and not c['sources']
               and not c['ruling']}
    for item in items(sheet):
        if item['type'] and item['equipped'] and not _proficient(item, trained) and item['type'] not in claimed:
            shield = item['type'] == 'shield'
            found.append({'id': f"{'shield' if shield else 'armor'}_proficiency:{item['id']}", 'item': item['id'],
                          'name': item['name'], 'issue': 'shield_proficiency' if shield else 'armor_proficiency',
                          'rule': RULE_SHIELD if shield else RULE_ARMOR,
                          'ask': (f"Is the {item['name']} on your arm, or stowed? You are not trained with "
                                  f"{CATEGORY_WORDS[item['type']]}." if shield else
                                  f"Are you wearing the {item['name']}, or have you taken it off? You are not "
                                  f"trained with {CATEGORY_WORDS[item['type']]}.")})
    attuned = [item for item in items(sheet) if item['attuned']]
    who = classes(sheet)
    for item in attuned:
        if item['attunement_by'] and not any(b in who or (b == 'spellcaster' and any(c in SPELLCASTERS for c in who))
                                             for b in item['attunement_by']):
            label = ' or '.join(item['attunement_by'])
            found.append({'id': f"attunement_class:{item['id']}", 'item': item['id'], 'name': item['name'],
                          'issue': 'attunement_class', 'rule': RULE_ATTUNE_BY.format(who=label),
                          'ask': f"The {item['name']} only answers to a {label}. What is it doing for you now?"})
    if len(attuned) > ATTUNEMENT_LIMIT:
        names = ', '.join(item['name'] for item in attuned)
        found.append({'id': 'attunement_limit', 'item': None, 'name': names, 'issue': 'attunement_limit',
                      'rule': RULE_ATTUNE,
                      'ask': f'You are attuned to {len(attuned)} items ({names}); which three keep the bond?'})
    return found


# -- state: state['gear'] = {'in_use': {item id: bool}, 'clarify': [...], 'audits': n} ------------
def gear(state):
    return copy.deepcopy((state or {}).get('gear') or {'in_use': {}, 'clarify': [], 'audits': 0})


def run_audit(state, why):
    """Re-audit the loaded sheet into ``state`` (in place): a new mismatch is a pending
    clarification; one already raised or answered is never raised twice."""
    sheet = (state or {}).get('player_sheet')
    if not sheet:
        return state
    body = gear(state)
    known = {entry['id'] for entry in body['clarify']}
    for issue in audit(_with_use(sheet, body), state.get('homebrew_rulings')):
        if issue['id'] not in known:
            body['clarify'].append({**issue, 'status': 'pending', 'found': why})
    # Never drop an entry the sheet still raises (an answered one would come back as new and be
    # asked again: Nagatha's 59ce12a review, F10); only old ones for gear no longer there go.
    current = {issue['id'] for issue in audit(_with_use(sheet, body), state.get('homebrew_rulings'))}
    keep = [e for e in body['clarify'] if e['id'] in current or e['status'] in OPEN]
    gone = [e for e in body['clarify'] if not (e['id'] in current or e['status'] in OPEN)][-12:]
    body['clarify'] = [e for e in body['clarify'] if any(e is k for k in keep + gone)]
    body['audits'] = int(body.get('audits') or 0) + 1
    state['gear'] = body
    return state


def _with_use(sheet, body):
    """The sheet with each item's recorded in-use state as its ``equipped`` flag."""
    sheet = copy.deepcopy(sheet)
    recorded = body.get('in_use') or {}
    for key in GEAR_KEYS:
        value = sheet.get(key)
        if isinstance(value, (str, dict)):
            value = [value]
            sheet[key] = value
        for index, entry in enumerate(value or ()):
            name = entry.get('name') if isinstance(entry, dict) else entry
            if ident(name) in recorded:
                detail = dict(entry) if isinstance(entry, dict) else {'name': entry}
                detail['equipped'] = bool(recorded[ident(name)])
                value[index] = detail
    return sheet


def in_use(state, item, fight=None):
    """Is this armor worn / shield held now? The player's recorded word, else the sheet (an item
    listed is in use unless it says equipped false), except a shield at a card table (seated)."""
    recorded = ((state or {}).get('gear') or {}).get('in_use') or {}
    if item['id'] in recorded:
        return bool(recorded[item['id']])
    if not item['equipped']:
        return False
    if item['type'] == 'shield' and not fight and (state or {}).get('procedures'):
        return False  # seated at cards: a shield is set aside (pc_sheet situation 'seated')
    return True


def stowed_names(state):
    """Names of sheet items the player has recorded as not in use (pc_sheet drops them from held)."""
    sheet = (state or {}).get('player_sheet') or {}
    recorded = ((state or {}).get('gear') or {}).get('in_use') or {}
    return [item['name'] for item in items(sheet) if recorded.get(item['id']) is False]


OPEN = ('pending', 'raised')


def open_question(state, item):
    """The clarification still open (pending or raised) on this item: its own gear question, or
    the source question on a training claim that covers it. None when nothing is open."""
    for entry in gear(state)['clarify']:
        if entry.get('status') not in OPEN:
            continue
        if entry.get('item') == item['id'] or (entry.get('issue') == 'unverified_proficiency' and
                                               entry.get('kind') == 'armor' and entry.get('claim') == item['type']):
            return entry
    return None


def asked_and_answered(state, item):
    """Brendon's ruling (2026-10-19): ask first, then the rules as written. A penalty applies only
    once the player has said the item is in use (his answer to Kit's question, or readying it in so
    many words) and no question on it is still open. Never from the sheet alone."""
    recorded = ((state or {}).get('gear') or {}).get('in_use') or {}
    return recorded.get(item['id']) is True and open_question(state, item) is None


def penalties(state, fight=None):
    """{'gear': [names], 'no_casting': bool, 'str_dex_disadvantage': bool}: non-proficient armor or
    shield in use now (SRD), for any sheet, once asked and answered (asked_and_answered)."""
    sheet = (state or {}).get('player_sheet') or {}
    trained = proficiencies(sheet, (state or {}).get('homebrew_rulings'))
    names = [item['name'] for item in items(sheet)
             if item['type'] and in_use(state, item, fight) and not _proficient(item, trained)
             and asked_and_answered(state, item)]
    return {'gear': names, 'no_casting': bool(names), 'str_dex_disadvantage': bool(names)}


def why(state, fight=None):
    """'the Sentinel Shield you are not proficient with', or '' when nothing applies."""
    names = penalties(state, fight)['gear']
    if not names:
        return ''
    return f"the {' and the '.join(names)} you are not proficient with"


def advantage_from(state, what, fight=None):
    """Names of in-use items whose own text grants advantage on ``what`` (initiative, a skill)."""
    sheet = (state or {}).get('player_sheet') or {}
    return [item['name'] for item in items(sheet) if what in item['advantage'] and in_use(state, item, fight)]


def roll_mode(state, ability, what=None, fight=None):
    """('advantage'|'disadvantage'|'normal', reason) for a PC roll using ``ability`` (str/dex/...),
    and ``what`` (initiative, a skill) for an item's own advantage. Both apply: they cancel (SRD)."""
    disadvantage = ability in ('str', 'dex') and penalties(state, fight)['str_dex_disadvantage']
    advantage = advantage_from(state, what, fight) if what else []
    if advantage and disadvantage:
        return 'normal', (f"advantage from the {' and '.join(advantage)} and disadvantage from "
                          f"{why(state, fight)} cancel out")
    if advantage:
        return 'advantage', f"the {' and '.join(advantage)}"
    if disadvantage:
        return 'disadvantage', why(state, fight)
    return 'normal', ''


def initiative_prompt(state):
    """'Roll initiative.' with the mode the gear in use sets (a Dexterity check)."""
    mode, reason = roll_mode(state, 'dex', 'initiative', fight=True)
    if mode == 'normal' and not reason:
        return 'Roll initiative.'
    if mode == 'normal':
        return f'Roll initiative, a straight roll: {reason}.'
    return f'Roll initiative with {mode} ({reason}).'


def shield_ac(state, fight=None):
    """The AC the sheet's shields add that is not in use now (the sheet's AC counts its listed
    shield): subtract it. 0 when every listed shield is in use."""
    sheet = (state or {}).get('player_sheet') or {}
    return sum(item['ac_bonus'] for item in items(sheet)
               if item['type'] == 'shield' and item['equipped'] and not in_use(state, item, fight))


# -- swaps and answers -------------------------------------------------------------------
_OFF = (r"stow|stows|sling|slings|put away|puts away|set aside|sets aside|set down|sets down|drop|drops|"
        r"doff|doffs|take off|takes off|unstrap|unstraps|remove|removes|lower|lowers|shrug off|shrugs off|"
        r"hang|hangs|strap\s+\w+\s+(?:to|on)\s+my\s+back")
_ON = r"ready|readies|don|dons|put on|puts on|strap on|straps on|take up|takes up|pick up|picks up|grab|grabs|wield|wields|hold up|heft|hefts"


def read_swap(text, state):
    """{'item', 'name', 'in_use'} when the player readies or stows a listed armor or shield in so
    many words ('I stow my shield', 'I ready the Sentinel Shield'), else None. A question, or
    the Shield spell ('I cast Shield', 'I raise a shield'), is never a swap."""
    sheet = (state or {}).get('player_sheet') or {}
    words = _norm(text)
    if '?' in str(text) or re.search(r'\bcast\w*\s+(?:a\s+|the\s+|my\s+)?shield\b|\braises?\s+(?:a\s+|my\s+)?shield\b',
                                     words) or re.search(r'!cast\s+shield\b', str(text).casefold()):
        return None  # the Shield spell, or a question
    for item in items(sheet):
        if not item['type']:
            continue
        nouns = [re.escape(_norm(item['name']))]
        nouns.append(r'(?:my|the|his|her|that)\s+shield' if item['type'] == 'shield' else
                     r'(?:my|the|his|her)\s+(?:armor|armour|' + re.escape(_norm(item['name'])) + ')')
        noun = '(?:' + '|'.join(nouns) + ')'
        for verbs, use in ((_OFF, False), (_ON, True)):
            if re.search(r'\b(?:' + verbs + r')\b(?:\s+\w+){0,3}?\s+' + noun + r'\b', words) or \
                    re.search(r'\b' + noun + r'\s+(?:\w+\s+){0,2}?(?:' + ('off|away|aside|down' if not use else 'on|up') + r')\b',
                              words) and re.search(r'\b(?:' + verbs + r'|put|puts|take|takes|strap|straps)\b', words):
                return {'item': item['id'], 'name': item['name'], 'in_use': use, 'type': item['type']}
    return None


def after_swap(text):
    """The part of the message after its swap clause ('I drop my shield and cast Magic Missile at
    the imp' -> 'cast Magic Missile at the imp'), or ''."""
    words = str(text or '')
    swap = re.search(r'(?i)\b(?:' + _OFF + '|' + _ON + r')\b', words)
    if not swap:
        return ''
    tail = words[swap.end():]
    cut = re.search(r'(?i)\s*(?:[,;]|\.(?=\s|$)|\band\s+then\b|\bthen\b|\band\b)\s*', tail)
    if not cut:
        return ''
    rest = tail[cut.end():].strip()
    return ('I ' + rest) if rest and not re.match(r'(?i)(?:i|nik|he|she)\b', rest) else rest


def change_event(state, item, in_use_now, why_text, answer=None):
    """The gear_state event: the item's in-use state, and the clarification it answers."""
    return {'type': 'gear_state', 'item': item, 'in_use': bool(in_use_now),
            **({'answers': answer} if answer else {}), 'evidence': why_text[:300]}


def raised_event(clarification_id, turn_id):
    return {'type': 'gear_state', 'raised': clarification_id, 'turn': str(turn_id),
            'evidence': f'Kit raised the equipment clarification {clarification_id} in voice.'}


def apply_event(state, event):
    """state['gear'] after a gear_state event (an item's use, a clarification raised or answered)."""
    body = gear(state)
    sheet = state.get('player_sheet') or {}
    if 'item' in event:
        known = {item['id'] for item in items(sheet)}
        require(event['item'] in known, f"gear_state names an item not on the sheet: {event['item']}")
        body['in_use'][event['item']] = bool(event.get('in_use'))
        for entry in body['clarify']:
            if entry.get('item') == event['item'] and entry['status'] != 'answered':
                entry.update(status='answered', answer='in use' if event.get('in_use') else 'stowed')
    if event.get('answers'):
        for entry in body['clarify']:
            if entry['id'] == event['answers']:
                entry.update(status='answered', answer=entry.get('answer') or str(event.get('evidence'))[:120])
    for heard in event.get('heard') or ():
        # The player's reply after Kit asked was read as his answer once (kit_agent
        # RoomAdjudicator._question_answer); later refusals are refusals again.
        for entry in body['clarify']:
            if entry['id'] == heard:
                entry['heard'] = True
    if event.get('raised'):
        entry = next((e for e in body['clarify'] if e['id'] == event['raised']), None)
        require(entry is not None, 'gear_state raises a clarification that is not pending')
        if entry['status'] == 'pending':
            entry.update(status='raised', raised_turn=str(event.get('turn') or ''))
    state['gear'] = body
    return state


def pending(state):
    """The next clarification to raise, or None."""
    return next((e for e in gear(state)['clarify'] if e['status'] == 'pending'), None)


def raised(state):
    """Clarifications Kit raised that the player has not answered yet."""
    return [e for e in gear(state)['clarify'] if e['status'] == 'raised']


def awaiting_answer(state):
    """Raised clarifications whose answer has not been heard yet: the next reply that is not an act
    the engine resolves is the answer, quoted or not."""
    return [e for e in raised(state) if not e.get('heard')]


def heard_event(ids, why_text):
    return {'type': 'gear_state', 'heard': list(ids), 'evidence': why_text[:300]}


def clarify_view(entry):
    """What Kit sees for the one clarification to raise this turn."""
    return {'id': entry['id'], 'item': entry['name'], 'issue': entry['issue'], 'rule': entry['rule'],
            'ask': entry['ask'], 'how': CLARIFY_RULE}


def answer_offer(state):
    """The ``gear`` act offer while a raised clarification waits on the player's answer."""
    open_ = [e for e in raised(state) if e.get('item')]
    if not open_:
        return None
    return {'items': [e['item'] for e in open_], 'names': [e['name'] for e in open_]}


def check_spoken_clarify(entry, segments):
    """Kit raised it: the item named (attunement: the bond named) and a question asked, in this
    turn's performance. ``entry`` is the clarify_view Kit was given."""
    text = ' '.join(str(s.get('text') or '') for s in segments or ())
    folded = text.casefold()
    name = str(entry.get('item') or '')
    if entry.get('issue') == 'attunement_limit':
        named = 'attun' in folded or 'bond' in folded
    else:
        words = [w for w in re.findall(r"[a-z]+", name.casefold()) if len(w) > 3]
        named = any(w in folded for w in words)
    require(named and '?' in text,
            f"gear_clarify is due this turn: ask about the {name} in your own voice, as an in-fiction "
            f"question that names it and states the rule ({entry['rule']}). For example: {entry['ask']}")


# -- homebrew rulings: Kit's call on where a claimed proficiency came from ----------------------
# state['homebrew_rulings'] is a campaign-level record (generic, for the campaign record to pick
# up as homebrew): it travels with the character across rooms and sessions, so a claim ruled on
# once is never asked about again.
RULING_LIMIT = 50
# Sheet fields a player edits by hand between sessions: accepted as they are and only noted.
NOTED_FIELDS = ('gold_gp', 'gp', 'gold', 'hp', 'max_hp', 'temp_hp', 'xp', 'experience', 'ammo', 'ammunition',
                'arrows', 'bolts')


def ruling_offer(state):
    """The ``ruling`` act offer while a raised source question waits on the player's answer."""
    open_ = [e for e in raised(state) if e.get('issue') == 'unverified_proficiency']
    if not open_:
        return None
    return {'ids': [e['id'] for e in open_], 'names': [e['name'] for e in open_],
            'rules': {e['id']: e['rule'] for e in open_}}


def ruling_event(state, decl, turn=None, evidence=''):
    """The homebrew_ruling event for Kit's call on a raised source question."""
    entry = next(e for e in gear(state)['clarify'] if e['id'] == decl['id'])
    ruling = {'claim_id': entry['id'], 'kind': 'proficiency', 'subject': entry.get('kind'),
              'claim': entry.get('claim'), 'label': entry['name'], 'verdict': decl['verdict'],
              'source': decl.get('source') or None, 'cost': decl.get('cost') or None,
              'rule': entry['rule'], 'ruled_by': 'kit', 'turn': str(turn or ''),
              'scene': str(state.get('scene_id') or ''), 'room': str((state.get('room') or {}).get('id') or '')}
    return {'type': 'homebrew_ruling', 'ruling': ruling, 'evidence': str(evidence)[:300]}


def apply_ruling(state, event):
    """state after a homebrew_ruling: the ruling on record, its question answered, the audit re-run."""
    ruling = dict(event.get('ruling') or {})
    require(ruling.get('verdict') in RULINGS and ruling.get('claim_id'), 'homebrew_ruling needs claim_id and verdict')
    require(ruling['verdict'] == 'declined' or str(ruling.get('source') or '').strip(),
            'A granted ruling names the source the player gave')
    require(ruling['verdict'] != 'granted_with_cost' or str(ruling.get('cost') or '').strip(),
            'granted_with_cost names the cost or condition')
    rulings = list(state.get('homebrew_rulings') or [])
    require(not ruling_for(rulings, ruling['claim_id']), 'That claim is already ruled on')
    ruling['id'] = f"hb-{len(rulings) + 1}"
    state['homebrew_rulings'] = (rulings + [ruling])[-RULING_LIMIT:]
    body = gear(state)
    for entry in body['clarify']:
        if entry['id'] == ruling['claim_id']:
            entry.update(status='answered', answer=ruling['verdict'])
    state['gear'] = body
    return run_audit(state, 'homebrew ruling')  # declined: the gear question for it comes due


def sheet_notes(old, new):
    """Hand edits between two loads of the same character (gold, HP, XP, ammo): accepted, noted."""
    if not old or not new or old.get('name') != new.get('name'):
        return []
    return [{'field': key, 'from': old.get(key), 'to': new.get(key)} for key in NOTED_FIELDS
            if (key in old or key in new) and old.get(key) != new.get(key)]

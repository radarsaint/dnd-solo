"""Price hook: where every price comes from. Nothing in the runtime invents a price.

Precedence (Brendon, 2026-09-29):

1. **The source adventure.** A price the room source fixes (area 6c's 10 gp passage toll
   in ``numeric_facts``) wins, and ``kit_guards.check_numeric_facts`` enforces it.
2. **The DMG's official price** for a magic item, when the item data carries one
   (``official_price_gp`` on the pricing spec).
3. **The SRD 5.1 equipment tables** for everyday goods (runtime/data/srd_5_1_prices.json:
   adventuring gear, weapons, armor, tools, mounts and vehicles, trade goods, food/drink/
   lodging, services, lifestyle; CC-BY-4.0, attribution in the file). Kit may flavor a
   local variant (the house's "black-cherry cordial") but the price is the closest SRD
   entry's ("Wine, common (pitcher)"), and the ledger records which entry was used.
4. **Brendon's magic item formula** (runtime/pricing.py) for a magic item with no
   official price.
5. **Unpriced.** Anything listed nowhere returns ``UNPRICED`` with a flag. The NPC answers
   without a number (haggles, deflects, names a trade instead); nobody invents one.

The texture palette and the detail oracle never deal prices. Once set, a price is saved
in the canon ledger under the item's slot, and the item always keeps that price.
"""
import json
import re

from . import pricing
from .state_context import PROJECT_ROOT, require

SRD_FILE = PROJECT_ROOT / 'runtime/data/srd_5_1_prices.json'
UNPRICED = None
_SRD = None
# Context words too common to identify which source price a question is about.
_GENERIC_CUES = frozenset('each per way head price cost costs fee safe worth'.split())
_SKIP = frozenset('a an the of per and or for my your his her their one some day lb sq yd mile '
                  'how much does cost costs what is price'.split())


def srd_entries():
    global _SRD
    if _SRD is None:
        data = json.loads(SRD_FILE.read_text(encoding='utf-8'))
        require(data.get('schema') == 'srd_prices_v1' and 'Creative Commons Attribution 4.0' in
                data.get('_attribution', ''), 'SRD price data needs its schema and CC-BY attribution')
        _SRD = data['entries']
    return _SRD


def _tokens(text):
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", (text or '').casefold().replace('\u2019', "'"))
    words = [word[:-2] if word.endswith("'s") else word for word in words]
    return [re.sub(r"(es|s)$", '', word) if len(word) > 3 else word for word in words if word not in _SKIP]


def srd_entry(name):
    """The SRD entry with exactly this name (case-insensitive), or None."""
    wanted = ' '.join((name or '').casefold().split())
    return next((entry for entry in srd_entries() if entry['name'].casefold() == wanted), None)


# Everyday words for what an SRD entry calls something else: a "room at the inn" is an
# "Inn stay", a "pint of beer" is an "Ale, mug". Only words that name the same thing.
SYNONYMS = {'room': 'stay', 'bed': 'stay', 'lodging': 'stay', 'beer': 'ale', 'pint': 'mug',
            'tankard': 'mug', 'lodge': 'stay', 'meal': 'meal', 'food': 'meal', 'tavern': 'inn'}
# Time and quantity words an entry's bundle ("(per day)") already covers.
_BUNDLE_WORDS = frozenset('night nights day days tonight evening week here there place house at in on '
                          'with from to by that this these those your my our their his her yon'.split())
_ASKS = (
    re.compile(r"\bhow much (?:is|are|for|does|do|would|will|to|'s|would it be for|does it cost to|"
               r"to buy|to rent|to hire)?\s*(?P<item>[^?.!,;]+)"),
    re.compile(r"\bwhat (?:is|does|do|would|will|'s)\s+(?P<item>[^?.!,;]+?)\s+(?:cost|costs|go for|run|"
               r"sell for|fetch|worth)\b"),
    re.compile(r"\bwhat(?:'s| is) the (?:price|cost|going rate) (?:of|for|on)\s+(?P<item>[^?.!,;]+)"),
    re.compile(r"\b(?:price|cost) (?:of|for|on)\s+(?P<item>[^?.!,;]+)"),
    re.compile(r"\b(?:sell|buy|rent|hire) (?:me |you |us )?(?P<item>[^?.!,;]+?)(?: for| at the price|$)"),
)
_LEADING = re.compile(r"^(?:(?:a|an|the|your|that|this|those|these|one|some|my|his|her|their|of|for|to|"
                      r"buy|rent|get|cost)\s+)+")
_TRAILING = re.compile(r"(?:\s+(?:cost|costs|go for|run|be|worth|cost me|here|tonight|around here|"
                       r"in here|these days|then|now|exactly|again))+$")


def asked_item(text):
    """The item a price question names, in the player's words, whole: "wand of
    fireballs", "silver ring", "room at the inn". Falls back to the whole question."""
    norm = ' '.join((text or '').casefold().replace('\u2019', "'").split())
    for pattern in _ASKS:
        found = pattern.search(norm)
        if found:
            item = _TRAILING.sub('', _LEADING.sub('', found.group('item').strip())).strip()
            if re.search(r'[a-z]', item):
                return item
    return norm.strip(' ?.!')


def _entry_parts(name):
    """(head tokens, qualifier tokens, bundle tokens) of an SRD name:
    "Inn stay, modest (per day)" -> ([inn, stay], [modest], [day])."""
    bundle = ' '.join(re.findall(r'\(([^)]*)\)', name))
    bare = re.sub(r'\([^)]*\)', ' ', name)
    head, _, qualifier = bare.partition(',')
    return _tokens(head), _tokens(qualifier), _tokens(bundle)


def _query_words(text):
    words = [SYNONYMS.get(word, word) for word in _tokens(asked_item(text))]
    return {word for word in words if word not in _BUNDLE_WORDS}


def whole_item_matches(text):
    """SRD entries that are the whole item asked about, in table order. Every content
    word of the asked item must be in the entry's name (after SYNONYMS), and the entry's
    head noun must be asked: "silver ring" never matches "Silver (1 lb.)", and "wand of
    fireballs" never matches "Wand"."""
    query = _query_words(text)
    if not query:
        return []
    found = []
    for entry in srd_entries():
        head, qualifier, bundle = _entry_parts(entry['name'])
        if head and head[0] in query and query <= set(head) | set(qualifier) | set(bundle):
            found.append(entry)
    return found


def tier_of(name):
    """The qualifier of a tiered SRD entry (one of several with the same head: the six
    "Inn stay" entries, "Ale, gallon" / "Ale, mug"), as a slot segment, else None."""
    entry = srd_entry(name)
    if entry is None:
        return None
    head, qualifier, _ = _entry_parts(entry['name'])
    if not qualifier:
        return None
    siblings = [other for other in srd_entries() if _entry_parts(other['name'])[0] == head]
    return '_'.join(qualifier) if len(siblings) > 1 else None


def closest_srd(text):
    """(best entry, alternatives) that are the whole item asked about, or (None, [])."""
    found = whole_item_matches(text)
    return (found[0], found[1:]) if found else (None, [])


def _srd_result(entry, item):
    bundle = f' per {entry["per"]}' if entry.get('per') else ''
    return {'item': item, 'amount': entry['amount'], 'unit': entry['unit'],
            'basis': f'SRD 5.1 {entry["table"]}: {entry["name"]}{bundle}', 'srd_entry': entry['name'],
            'source': 'srd'}


def price_for(item, context=None):
    """The price for `item` by Brendon's precedence, or UNPRICED.

    context keys (all optional): 'source_price' ({'amount', 'unit', 'basis'} from the room
    source), 'magic_item' (a runtime/pricing.py spec), 'srd_entry' (an exact SRD name the
    host chose as the closest entry)."""
    context = context or {}
    source = context.get('source_price')
    if source:
        return {'item': item, **source, 'source': 'adventure'}
    spec = context.get('magic_item')
    if spec:
        result = pricing.price({**spec, 'item': spec.get('item') or item})
        official = spec.get('official_price_gp')
        return {**result, 'source': 'dmg_official' if type(official) is int and official > 0 else 'formula'}
    name = context.get('srd_entry')
    if name and name.strip().casefold() != 'none':
        entry = srd_entry(name)
        require(entry is not None, f'No SRD 5.1 entry named {name!r}; name the closest listed entry exactly')
        return _srd_result(entry, item)
    return UNPRICED


def lookup_hint(text, source_prices=()):
    """What prepare shows the private plan for a price question: a matching source price,
    else the closest SRD entries, else an unpriced flag. A hint, never a committed price."""
    words = set(_tokens(text))
    for name, fact in source_prices:
        cues = {_tokens(word)[0] for word in fact.get('context_words', [])
                if _tokens(word) and word not in _GENERIC_CUES}
        if words & cues:
            return {'status': 'source', 'name': name, 'amounts': fact['allowed_amounts'],
                    'unit': fact['unit_words'][0]}
    found = whole_item_matches(text)
    if found:
        tiers = [tier_of(entry['name']) for entry in found]
        hint = {'status': 'srd', 'item': asked_item(text),
                'closest': [_srd_result(entry, text)['basis'] for entry in found[:6]]}
        if any(tiers):
            hint['tiers'] = [tier for tier in tiers[:6] if tier]
            hint['tier_rule'] = ('Tiered entry: quote the tier the NPC names, and record it under '
                                 'the slot plus "/<tier>" (e.g. .../modest).')
        return hint
    return {'status': 'unpriced', 'flag': 'UNPRICED: no source, DMG, SRD, or formula price. Answer '
            'without a number; do not invent one.'}


def is_priced(result):
    return isinstance(result, dict) and type(result.get('amount')) is int and bool(result.get('unit'))

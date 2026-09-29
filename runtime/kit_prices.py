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


def closest_srd(text):
    """(best entry, alternatives) by shared words with an item description, or (None, []).
    The entry's head noun (the first word of its SRD name: "Ale" in "Ale, mug") must be
    among the words, so "glass eye" never matches "Bottle, glass"."""
    query = set(_tokens(text))
    scored = []
    for index, entry in enumerate(srd_entries()):
        tokens = _tokens(entry['name'])
        names = set(tokens)
        shared = len(query & names)
        if shared and tokens and tokens[0] in query:
            scored.append((shared / len(names), shared, -index, entry))
    if not scored:
        return None, []
    scored.sort(key=lambda item: item[:3], reverse=True)
    best = scored[0]
    ties = [item[3] for item in scored[1:] if item[:2] == best[:2]]
    return best[3], ties


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
    best, ties = closest_srd(text)
    if best:
        return {'status': 'srd', 'closest': [_srd_result(entry, text)['basis'] for entry in [best] + ties[:3]]}
    return {'status': 'unpriced', 'flag': 'UNPRICED: no source, DMG, SRD, or formula price. Answer '
            'without a number; do not invent one.'}


def is_priced(result):
    return isinstance(result, dict) and type(result.get('amount')) is int and bool(result.get('unit'))

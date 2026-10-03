"""Texture palette, detail slots, and the seeded detail oracle. Room-agnostic.

Why this exists: when the source leaves a gap,
a preference-tuned model fills it with the most typical answer available. The fix
every tradition uses is to prepare specific, local options before anyone asks, let
the DM pick and interpret one, and write down whatever gets used.

- **Palette** (``source['texture_palette']['areas'][area]``): DM texture, not adventure
  fact. Every item cites the source facts it comes from (``roots``); ``never_invent``
  lists what no invented detail may touch (the room's secrets). It is checked when the
  session is initialized and again whenever it is dealt from, and it never reaches the
  performer.
- **Slots**: a stable key for "a thing the player can ask about", ``<subject>/<facet>``
  (``actor:uktarl/drink``, ``area_06c/card_table/game``). Actor slots travel with the actor.
- **Oracle**: for an open slot, ``prepare`` deals 3-5 cards from the palette deck for
  that facet, seeded by the session's roll seed, the slot, and how many deals that slot
  has consumed, so a retried or re-prepared turn sees the same deal. Kit's taste profile
  re-ranks the deal and marks one ``kit_lean``. The private plan picks a dealt card or
  overrides once with a reason.
- **Prices are never dealt.** An unsourced price routes to runtime/kit_prices.py.

No model calls; everything is deterministic Python.
"""
import hashlib
import json
import random
import re

from . import kit_guards, kit_prices
from .state_context import PROJECT_ROOT, require

TASTE_FILE = PROJECT_ROOT / 'docs/personality/kit-taste.json'
DEAL_MIN, DEAL_MAX = 3, 5
DEAL_SIZE = 4
ITEM_KINDS = ('sense', 'material', 'mood', 'history', 'culture', 'wealth')

# Facet vocabulary: what the player is asking about. Order matters (first match wins).
FACETS = (
    ('price', re.compile(r"\bhow much\b|\bcosts?\b|\bprice\b|\bfee\b|\btoll\b|\bworth\b|\bgo for\b|\bfetch\b")),
    ('game', re.compile(r"\bgame\b|\bplaying\b|\bwhat are (you|they|we) playing\b")),
    ('drink', re.compile(r"\bdrink\w*|\bsipping\b|\bpouring\b|\bin (his|her|their|that) (cup|glass|mug)\b")),
    ('food', re.compile(r"\beat\w*|\bstew\b|\bfood\b|\bcooking\b|\bin the pot\b")),
    ('carving', re.compile(r"\bcarv\w*|\binscri\w*|\bwritten\b|\bengrav\w*|\betched\b|\bpainted on\b")),
    ('song', re.compile(r"\bsing\w*|\bsong\b|\bhumm\w*|\btune\b|\bwhistl\w*")),
    ('smell', re.compile(r"\bsmell\w*|\bstink\w*|\bodou?r\b")),
    ('wear', re.compile(r"\bwear\w*|\bdressed\b|\bclothes\b|\bouffit\b")),
    ('name', re.compile(r"\bname\b|\bcalled\b|\bwho (is|are)\b")),
)


def load_taste(path=TASTE_FILE):
    taste = json.loads(path.read_text(encoding='utf-8'))
    require(taste.get('schema') == 'kit_taste_v1', 'Unknown Kit taste schema')
    return taste


def _norm(text):
    return ' '.join((text or '').replace('\u2019', "'").casefold().split())


_CHECKED = set()


def area_palette(source, area):
    """The area's palette, checked the first time play reaches the area (the loader checks
    only the starting area's at mount: docs/architecture/ROOM_LOADER.md, stage 3)."""
    palette = ((source or {}).get('texture_palette') or {}).get('areas', {}).get(area)
    if palette is not None:
        key = ((source or {}).get('id'), area, json.dumps(palette, sort_keys=True))
        if key not in _CHECKED:
            check_palette(source, areas=[area])
            _CHECKED.add(key)
    return palette


def _roots_ok(root, source):
    if root in source.get('facts', {}):
        return True
    kind, _, key = root.partition(':')
    if kind == 'actor':
        return key in source.get('actors', {})
    if kind == 'level':
        return key in (source.get('level_context') or {})
    if kind == 'exit':
        return key in source.get('exits', {})
    return False


def palette_strings(palette):
    """Every palette string that could reach a decision."""
    texts = [item['text'] for item in palette.get('items', [])]
    for cards in palette.get('decks', {}).values():
        for card in cards:
            texts += [card['entry'], card.get('handle', '')]
    return [text for text in texts if text]


def check_palette(source, public_check=None, areas=None):
    """Validate every area palette: roots resolve to real source ids, no deck deals
    prices, and no string leaks a secret (the room's DM-only leak sets, and the caller's
    literal public-content check). Raises InvalidChange."""
    root = (source or {}).get('texture_palette')
    if not root:
        return
    require(root.get('schema') == 'palette_v1', 'Unknown texture palette schema')
    require('not adventure fact' in root.get('_status', ''),
            'The palette must be labelled as DM texture, not adventure fact')
    sets = kit_guards.leak_sets(source)
    for area, palette in root.get('areas', {}).items():
        require(area in source['areas'], f'Palette for unknown area {area!r}')
        if areas is not None and area not in areas:
            continue
        require(isinstance(palette.get('never_invent'), list) and palette['never_invent'],
                f'Palette {area} needs a never_invent list protecting its secrets')
        for item in palette.get('items', []):
            require(item.get('kind') in ITEM_KINDS, f'Palette item {item.get("id")} has an unknown kind')
            require(item.get('roots') and all(_roots_ok(r, source) for r in item['roots']),
                    f'Palette item {item.get("id")} must cite real source ids in roots')
        require('price' not in palette.get('decks', {}),
                'Prices are never dealt from a palette; they come from the source or runtime/kit_prices.py')
        for facet, cards in palette.get('decks', {}).items():
            require(facet in dict(FACETS), f'Palette deck for unknown facet {facet!r}')
            ids = [card.get('id') for card in cards]
            require(len(ids) == len(set(ids)) and all(ids), f'Deck {facet} needs unique card ids')
            for card in cards:
                require(card.get('roots') and all(_roots_ok(r, source) for r in card['roots']),
                        f'Card {card.get("id")} must cite real source ids in roots')
                require(isinstance(card.get('basis'), str) and card['basis'].split(':')[0] in
                        ('real', 'published', 'palette'),
                        f'Card {card.get("id")} basis must start real:, published:, or palette:')
                require('procedure' in card, f'Card {card.get("id")} must say its procedure or null')
        for text in palette_strings(palette):
            # Leak sets apply as if nothing were revealed: the palette is prep, written
            # before play, and must be safe to deal at any point.
            kit_guards.check_paraphrased_leaks(text, {}, '', sets)
            if public_check:
                public_check(text)


def slot_for(action, source, state):
    """(slot, facet, subject) the player's words ask about, or None."""
    text = _norm(action)
    facet = next((name for name, pattern in FACETS if pattern.search(text)), None)
    if facet is None:
        return None
    palette = area_palette(source, state['area']) or {}
    subject = 'room'
    for key, aliases in (palette.get('subjects') or {}).items():
        if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in aliases):
            subject = key
            break
    slot = f'{subject}/{facet}' if subject.startswith('actor:') else f'{state["area"]}/{subject}/{facet}'
    return slot, facet, subject


def _rng(seed, slot, number):
    material = f'{seed}|{slot}|{number}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], 'big'))


def _taste_score(card, taste):
    prefers = taste.get('prefers', {})
    return sum(prefers.get(tag, 0) for tag in card.get('tags', ()))


def deal(source, state, slot, facet, taste=None):
    """3-5 cards for an open slot, deterministic for (roll seed, slot, deals consumed).
    Cards already committed in this area are discarded from the deck."""
    palette = area_palette(source, state['area']) or {}
    oracle = state.get('oracle') or {}
    used = set((oracle.get('used') or {}).get(state['area'], []))
    cards = [card for card in palette.get('decks', {}).get(facet, []) if card['id'] not in used]
    if len(cards) < DEAL_MIN:
        return []
    number = (oracle.get('deals') or {}).get(slot, 0)
    drawn = _rng(state.get('roll_seed', ''), slot, number).sample(cards, min(DEAL_SIZE, len(cards)))
    taste = taste or load_taste()
    ranked = sorted(drawn, key=lambda card: -_taste_score(card, taste))  # stable: ties keep the draw
    hand = []
    for index, card in enumerate(ranked):
        hand.append({'draw_id': f'd{number}.{card["id"]}', 'card': card['id'],
                     'entry': card['entry'], 'basis': card['basis'], 'roots': card['roots'],
                     'procedure': card.get('procedure'), 'handle': card.get('handle', ''),
                     'kit_lean': index == 0})
    return hand


def oracle_packet(action, source, state, action_kind, price_lookup=None):
    """The private `detail_oracle` for this turn, or None when nothing is asked.

    status: canon_supplied (the ledger answers; reuse it), source_supplied (a source
    fact answers), priced / unpriced (a price: source or the price hook, never the
    palette), open (a deal of 3-5 cards), or open_no_deck (write your own candidates)."""
    if action_kind == 'opening':
        return None
    found = slot_for(action, source, state)
    if not found:
        return None
    slot, facet, subject = found
    palette = area_palette(source, state['area']) or {}
    hint = None
    if facet == 'price':
        # One slot per priced thing, so a set price stays that thing's price.
        hint = price_lookup(action) if price_lookup else {'status': 'unpriced'}
        slot = f'{state["area"]}/price/{price_slug(action, hint)}'
    packet = {'slot': slot, 'facet': facet, 'subject': subject}
    canon = (state.get('canon') or {}).get(slot)
    if facet == 'price' and not canon:
        canon = price_canon(state.get('canon') or {}, slot, hint or {})
    answers = palette.get('source_answers') or {}
    if canon:
        packet.update(status='canon_supplied', canon=canon)
    elif slot in answers:
        packet.update(status='source_supplied', source_fact=answers[slot])
    elif facet == 'price':
        packet.update(status='unpriced' if hint['status'] == 'unpriced' else 'priced', price=hint)
    else:
        hand = deal(source, state, slot, facet)
        packet.update(status='open' if hand else 'open_no_deck', deal=hand)
    if palette:
        packet['texture'] = {'items': [{'id': item['id'], 'text': item['text']}
                                       for item in palette.get('items', [])],
                             'never_invent': palette['never_invent'],
                             'label': 'DM texture from the keyed room; not adventure fact'}
    return packet


_PRICE_WORDS = frozenset('how much does do is are the a an for of cost costs price worth what fee '
                         'would will it this that one your you me i buy sell'.split())


_SLUG_FILLER = frozenset('a an the that this these those your my our their his her yon'.split())


def price_slug(action, hint):
    """A stable name for the priced thing: the source price's name, else the whole item
    the player asked about ("wand_of_fireballs", "room_at_the_inn"), never the SRD word it
    happened to match. A tiered SRD match drops the tier word from the item: the tier is
    its own slot segment (".../room_at_the_inn/modest"), keyed by the tier quoted."""
    if hint.get('status') == 'source':
        return hint['name']
    item = hint.get('item') or kit_prices.asked_item(action)
    tiers = set(hint.get('tiers') or ())
    words = [word for word in re.findall(r"[a-z0-9]+", _norm(item))
             if word not in tiers and word not in _SLUG_FILLER]
    while words and words[0] in _PRICE_WORDS:
        words.pop(0)
    return re.sub(r'[^a-z0-9]+', '_', ' '.join(words)).strip('_')[:60] or 'item'


def price_canon(canon, slot, hint):
    """The ledger entry that answers a price question: the slot itself, or for a tiered
    item the tier the player named, or every tier already priced when they named none."""
    if slot in canon:
        return canon[slot]
    tiers = {key[len(slot) + 1:]: entry for key, entry in canon.items() if key.startswith(slot + '/')}
    if not tiers:
        return None
    named = hint.get('tiers') or []
    if len(named) == 1:
        return tiers.get(named[0])
    return {'fact': '; '.join(entry['fact'] for entry in tiers.values()), 'tiers': sorted(tiers)}


def model_view(packet):
    """The oracle as the decision sees it: what it needs to choose, nothing it doesn't.
    The full packet (roots, basis) stays in the staged body for the checks and commit."""
    if not packet:
        return packet
    lean = {key: value for key, value in packet.items() if key not in ('deal', 'texture', 'canon')}
    if packet.get('canon'):
        lean['canon'] = {'fact': packet['canon']['fact']}
    if packet.get('deal'):
        lean['deal'] = [{key: card[key] for key in ('draw_id', 'entry', 'handle')} |
                        ({'procedure': card['procedure']} if card.get('procedure') else {}) |
                        ({'kit_lean': True} if card.get('kit_lean') else {})
                        for card in packet['deal']]
    if packet.get('texture') and packet.get('status') == 'open_no_deck':
        # Texture only when the decision must write its own candidates; a deal already
        # carries the palette's material, and canon, source, and price need none.
        lean['texture'] = [item['text'] for item in packet['texture']['items']]
        lean['never_invent'] = packet['texture']['never_invent']
    return lean


def sensory_words(source, area):
    palette = area_palette(source, area) or {}
    words = set()
    for item in palette.get('items', []):
        if item.get('kind') in ('sense', 'material'):
            words |= {word for word in re.findall(r"[a-z']+", _norm(item['text'])) if len(word) >= 5}
    return words

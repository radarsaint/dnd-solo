"""Detail generation: answer the invitation, then keep the answer true. Room-agnostic.

The failure this module counters is the *assistant default*. A model trained to be
helpful, harmless, and brief answers an unsupplied detail with the smallest safe thing
it can: the answer that could be said at any table. At a game table that wastes an
invitation. When the player asks for a detail, or the scene needs one the source does
not supply, Kit answers with something specific that reveals a character, place, or
situation and hands the player a handle (something to bet, drink, steal, follow, or
ask about). Familiar real-world or published material, adapted to the setting, comes
before building from scratch.

Guardrails: the answer contradicts nothing established (source, canon, what was just
said), passes the "true because ___" test using only established facts and known
motives, never touches hidden information, a rules outcome, or the player's choices,
and is saved in the canon ledger so it stays true. Boldness goes into *which* detail,
never into length.

Carrier pattern (docs/architecture/kit-expression-gap.md, sections b and j):
prepare's ``detail_oracle`` (slot, canon, texture, a seeded deal) -> the private
``detail`` decision (pick a dealt card or override once; owner, handle, because;
candidates first when there is no deal) -> ``canon_entry`` events in the ledger and the
public ``established_details`` view -> performer instruction -> checks -> tests.

Checks validate structure, never self-rated typicality or word lists: a candidate
builds from something established, the typical one is rejected, and the canon ledger
makes the chosen answer stick.
"""
import re

from . import kit_guards, kit_prices
from . import kit_texture
from .state_context import normalize_fact, require

INVENTION_KINDS = ('object', 'drink_food', 'appearance', 'name', 'price', 'inscription',
                   'procedure', 'history', 'other')
SCOPES = ('scene', 'location', 'actor', 'campaign')
MAX_INVENTIONS = 4
INVENTION_FACT_MAX_CHARS = 240
INVENTION_BASIS_MAX_CHARS = 200  # the canon ledger's bound (state_context.CANON_BASIS_MAX_CHARS)
SLOT_PATTERN = re.compile(r'^[a-z0-9_:]+(/[a-z0-9_]+){1,3}$')
MIN_CANDIDATES, MAX_CANDIDATES = 3, 5
LINE_MAX_CHARS = 160
FIELD_MAX_CHARS = 200
SCENE_NEED_PREFIX = 'scene_need:'
SELF_PREFIX = 'self:'
OVERRIDE_PREFIX = 'override:'
BECAUSE_PREFIX = 'true because'
OWNER_EXTRAS = ('room', 'kit')
FIXED_CHOICES = ('none', 'canon', 'source', 'priced', 'unpriced', 'self')

_LINE = {'type': 'string'}
DETAIL_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'request': _LINE,   # none | the player's words, quoted | "scene_need: <what>"
        'slot': _LINE,      # none | detail_oracle.slot | "self: <subject>/<facet>"
        'choice': _LINE,    # none | a dealt draw_id | "override: <reason>" | canon | source | priced | unpriced | self
        'candidates': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'idea': _LINE, 'uses': _LINE, 'creates': _LINE},
            'required': ['idea', 'uses', 'creates']}},
        'typical': {'type': 'integer'},
        'chosen': {'type': 'integer'},
        'owner': _LINE,     # "<actor id|room|kit>: <what they want from it>"
        'handle': _LINE,    # what the player can do to or with it
        'because': _LINE,   # "true because <established facts or known motives only>"
        'price_quote': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'item': _LINE, 'srd_entry': _LINE, 'magic': _LINE},
            'required': ['item', 'srd_entry', 'magic']}},
        'inventions': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'slot': _LINE,
                'kind': {'type': 'string', 'enum': list(INVENTION_KINDS)},
                'fact': _LINE, 'basis': _LINE,
                'public': {'type': 'boolean'},
                'scope': {'type': 'string', 'enum': list(SCOPES)},
                'procedure': _LINE,       # none, or a runtime-supported procedure id
                'change_reason': _LINE,   # none, or the in-story event that changes a canon entry
            },
            'required': ['slot', 'kind', 'fact', 'basis', 'public', 'scope', 'procedure',
                         'change_reason']}},
    },
    'required': ['request', 'slot', 'choice', 'candidates', 'typical', 'chosen', 'owner', 'handle',
                 'because', 'price_quote', 'inventions'],
}
NO_DETAIL = {'request': 'none', 'slot': 'none', 'choice': 'none', 'candidates': [], 'typical': -1,
             'chosen': -1, 'owner': 'none', 'handle': 'none', 'because': 'none', 'price_quote': [],
             'inventions': []}

# A player asking for a detail. Broad and room-agnostic: a miss only means the host was
# not reminded; the host sets request whenever the player asks for a detail.
DETAIL_ASK = re.compile(
    r"\bwhat(?:'s| is| are| was| were| kind of| sort of)?\b[^.?!]{0,40}?\b("
    r"drink|drinking|eat|eating|smok|playing|game|wear|wearing|read|reading|carv|written|"
    r"says|inscri|made of|inside|in it|on it|smell|taste|called|name|"
    r"look like|hum|singing|cooking|brewing|selling|for sale|cost|worth|price|fee|toll|go for|fetch)\w*"
    r"|\bhow much\b|\bwho (is|are)\b|\btell me (about|more)\b|\bdescribe\b")

# Rules or stakes stated as settled. Naming any game as flavor is fine; offering one as
# playable (its rules, its stakes) needs a procedure the runtime can run.
PROCEDURE_STATEMENT = re.compile(
    r"\b(the )?rules? (is|are)\b|\bhighest\b[^.]{0,20}\b(wins|takes)\b|\bwinner takes\b"
    r"|\b(stakes?|ante|buy-in) (is|are)\b|\b(matching )?coin from each\b|\bone card (apiece|each)\b"
    r"|\beach player (puts|antes|pays|bets|gets)\b")

_SMALL = frozenset('''
    a an the and or but of to in on at is it its this that with for from by as be are was were
    he she they them his her their you your i me my we our who what which when where how why
    because true none there here has have had will would can could not no so than then just
'''.split())
_NUMBER = re.compile(r"\b\d+\b|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                     r"twenty|thirty|forty|fifty|hundred|dozen)\b")
_CONTRACTION = re.compile(r"\b(what|where|who|how|that|there|here)s\b")


def _norm(text):
    text = (text or '').replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    # Typed without the apostrophe ("whats the game"): the same question.
    text = _CONTRACTION.sub(r"\1's", text.casefold())
    return ' '.join(text.split())


def _tokens(text):
    return re.findall(r"[a-z0-9']+", _norm(text))


def keywords(text):
    return {word for word in _tokens(text) if len(word) >= 3 and word not in _SMALL}


def is_none(value):
    return isinstance(value, str) and value.strip().casefold() == 'none'


# "What is that worth (to you)?" bargains; it asks no item's price.
_BARGAIN_WORTH = re.compile(r"\bwhat(?:'s| is| are| would| will)?\s+(?:that|it|this|those|these|they)\s+"
                            r"(?:be\s+)?worth\b")


def asks_for_detail(player_action):
    text = _norm(player_action)
    match = bool(player_action) and DETAIL_ASK.search(text)
    if match and match.group(1) and match.group(1).startswith('worth') and _BARGAIN_WORTH.search(text):
        return False
    return bool(match)


def specific_enough(fact, basis, sensory_words):
    """The taste floor: a proper noun, a number, a palette sensory word, or a real-world or
    published basis. Returns the kind found, or None."""
    words = fact.split()
    if any(word[:1].isupper() for word in words[1:] if word.strip('"\'(').isalpha()):
        return 'proper_noun'
    if _NUMBER.search(_norm(fact)):
        return 'number_with_unit'
    if set(_tokens(fact)) & set(sensory_words):
        return 'palette_sensory_word'
    if _norm(basis).startswith(('real:', 'published:')):
        return 'real_world_basis'
    return None


def _line(value, name, max_chars=LINE_MAX_CHARS):
    require(isinstance(value, str) and value.strip() and len(value) <= max_chars and '\n' not in value,
            f'detail {name} must be one line of 1-{max_chars} characters')


def price_result(quote):
    """Run one price_quote through the precedence in runtime/kit_prices.py."""
    context = {}
    if not is_none(quote['srd_entry']):
        context['srd_entry'] = quote['srd_entry']
    if not is_none(quote['magic']):
        context['magic_item'] = parse_magic(quote['magic'])
    require(context, 'price_quote needs an SRD entry or a magic item spec')
    result = kit_prices.price_for(quote['item'], context)
    require(kit_prices.is_priced(result), 'price_quote did not produce a price')
    return result


def source_quote(oracle):
    """The adventure's own price when the oracle found one (precedence 1), as a quote."""
    price = (oracle or {}).get('price') or {}
    if price.get('status') != 'source' or not price.get('amounts'):
        return None
    return {'item': price['name'], 'amount': price['amounts'][0], 'unit': price['unit'],
            'basis': f'adventure source: {price["name"]}', 'source': 'adventure'}


_MAGIC_KEYS = ('impact_kind', 'dice', 'charges', 'bonus', 'levels', 'utility', 'aoe', 'renews',
               'entry_level', 'category', 'official_price_gp')
_MAGIC_FLAGS = ('aoe', 'renews')


def parse_magic(text):
    """'impact_kind=charged; dice=8d6; charges=7; aoe=yes; entry_level=9; category=Rare...'"""
    spec = {}
    for part in text.split(';'):
        key, _, value = part.partition('=')
        key, value = key.strip(), value.strip()
        if not key:
            continue
        require(key in _MAGIC_KEYS, f'Unknown magic item spec key {key!r}')
        if value.casefold() in ('yes', 'true'):
            spec[key] = True
        elif value.casefold() in ('no', 'false', 'none'):
            if key in _MAGIC_FLAGS:
                spec[key] = False  # "renews=no" is a statement, not an omission
            continue
        elif re.fullmatch(r'-?\d+', value):
            spec[key] = int(value)
        else:
            spec[key] = value
    return spec


def _check_candidates(detail, known):
    candidates = detail['candidates']
    require(MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES,
            f'Write {MIN_CANDIDATES}-{MAX_CANDIDATES} one-line candidates before choosing')
    for index, item in enumerate(candidates):
        require(isinstance(item, dict) and set(item) == {'idea', 'uses', 'creates'},
                'Each candidate needs idea, uses, and creates')
        for field in ('idea', 'uses', 'creates'):
            _line(item[field], f'candidate {field}')
        require(keywords(item['uses']) & known,
                f'Candidate {index} uses nothing established: name the source fact, person, object, '
                'or player words it builds from')
    count = len(candidates)
    require(0 <= detail['typical'] < count and 0 <= detail['chosen'] < count,
            'detail typical and chosen must index the candidates')
    require(detail['chosen'] != detail['typical'],
            'The most typical candidate is written down to be rejected; choose another')


def _check_owner_handle_because(detail, owners, known):
    owner, _, want = detail['owner'].partition(':')
    require(owner.strip().casefold() in set(owners) | set(OWNER_EXTRAS) and len(want.split()) >= 2,
            'detail owner must read "<actor id|room|kit>: <what they want from it>" naming a live '
            f'actor ({", ".join(owners) or "none"}), the room, or kit')
    _line(detail['handle'], 'handle', FIELD_MAX_CHARS)
    require(len(detail['handle'].split()) >= 3, 'detail handle must say what the player can do with it')
    _line(detail['because'], 'because', FIELD_MAX_CHARS)
    because = _norm(detail['because'])
    require(because.startswith(BECAUSE_PREFIX) and len(because.split()) >= 5,
            'detail because must read "true because <established facts or known motives>"')
    require(keywords(because[len(BECAUSE_PREFIX):]) & known,
            'The because test failed: finish "true because ___" with established facts or known '
            'motives. If it needs a new world fact, a hidden-information leak, or an NPC knowing '
            'something new, it is nonsense, not entertainment.')


def check_detail(detail, player_action, action_kind, source, state, supported_procedures=(),
                 established='', owners=(), oracle=None):
    """Private decision checks: structure, not self-rated quality."""
    require(isinstance(detail, dict) and set(detail) == set(DETAIL_SCHEMA['required']),
            'Invalid detail: needs ' + ', '.join(DETAIL_SCHEMA['required']))
    for key in ('request', 'slot', 'choice', 'owner', 'handle', 'because'):
        require(isinstance(detail[key], str) and detail[key].strip(), f'Invalid detail {key}')
    require(isinstance(detail['candidates'], list) and isinstance(detail['inventions'], list) and
            isinstance(detail['price_quote'], list) and type(detail['typical']) is int and
            type(detail['chosen']) is int, 'Invalid detail')
    request, choice, slot = detail['request'], detail['choice'].strip(), detail['slot'].strip()
    known = keywords(established) | keywords(player_action)
    asked = action_kind != 'opening' and asks_for_detail(player_action)
    dealt = {card['draw_id']: card for card in ((oracle or {}).get('deal') or [])}
    if is_none(request):
        require(not asked, 'The player asked for a detail. Set detail.request to their words and '
                'answer the invitation.')
        require(is_none(choice) and is_none(slot) and not detail['candidates'] and
                not detail['price_quote'] and detail['chosen'] == detail['typical'] == -1 and
                all(is_none(detail[key]) for key in ('owner', 'handle', 'because')),
                'With no detail request: slot and choice none, no candidates or price_quote, chosen '
                'and typical -1, owner, handle, and because none')
    else:
        if request.strip().casefold().startswith(SCENE_NEED_PREFIX):
            require(len(request.split(':', 1)[1].split()) >= 2, 'detail.request scene_need must say what')
        else:
            excerpt = _norm(request).strip(' .,!?;:"\'')
            require(excerpt and player_action and excerpt in _norm(player_action),
                    'detail.request must quote the player\'s words, be "scene_need: <what>", or be none')
        if oracle:
            require(slot == oracle['slot'], f'detail.slot must be the oracle\'s slot {oracle["slot"]!r}')
            status = oracle['status']
            allowed = {'canon_supplied': ('canon',), 'source_supplied': ('source',),
                       'priced': ('priced', 'unpriced'), 'unpriced': ('priced', 'unpriced'),
                       'open_no_deck': ('self',)}.get(status)
            if source_quote(oracle):
                allowed = ('source', 'unpriced')  # the adventure prices it; no SRD or formula
            if status == 'open':
                require(choice in dealt or choice.casefold().startswith(OVERRIDE_PREFIX),
                        'Pick a dealt card by draw_id, or override once: "override: <reason>"')
            else:
                require(choice in allowed, f'detail_oracle status {status}: choice must be '
                        f'{" or ".join(allowed)}')
        else:
            require(slot.casefold().startswith(SELF_PREFIX) and
                    SLOT_PATTERN.match(slot[len(SELF_PREFIX):].strip()),
                    'With no oracle slot, detail.slot reads "self: <subject>/<facet>"')
            require(choice in FIXED_CHOICES and choice != 'none',
                    'With no oracle slot, choice is self, canon, source, priced, or unpriced')
        if choice.casefold().startswith(OVERRIDE_PREFIX):
            require(len(choice.split(':', 1)[1].split()) >= 4, 'An override needs its reason')
        if choice == 'self' or choice.casefold().startswith(OVERRIDE_PREFIX):
            _check_candidates(detail, known)
        else:
            require(not detail['candidates'] or len(detail['candidates']) >= MIN_CANDIDATES,
                    'Candidates, when listed, number at least three')
            if detail['candidates']:
                _check_candidates(detail, known)
        if choice in dealt or choice == 'self' or choice.casefold().startswith(OVERRIDE_PREFIX):
            _check_owner_handle_because(detail, owners, known)
    # Prices: only through the precedence in kit_prices; never invented.
    quotes = [price_result(quote) for quote in detail['price_quote']]
    sourced = source_quote(oracle) if choice == 'source' else None
    require(not (sourced and quotes), 'The adventure sets this price; leave price_quote empty')
    quotes += [sourced] if sourced else []
    require(choice != 'priced' or quotes, 'choice priced needs a price_quote')
    target = oracle['slot'] if oracle else (slot[len(SELF_PREFIX):].strip()
                                            if slot.casefold().startswith(SELF_PREFIX) else None)
    _check_inventions(detail, source, state, supported_procedures, dealt, choice, target, quotes,
                      needs_price=bool(sourced))


def _check_inventions(detail, source, state, supported, dealt, choice, target, quotes, needs_price=False):
    inventions = detail['inventions']
    require(len(inventions) <= MAX_INVENTIONS, f'At most {MAX_INVENTIONS} inventions per turn')
    canon = (state or {}).get('canon') or {}
    sensory = kit_texture.sensory_words(source, (state or {}).get('area'))
    seen = set()
    answers_target = False
    for item in inventions:
        require(isinstance(item, dict) and set(item) == set(
            DETAIL_SCHEMA['properties']['inventions']['items']['required']),
            'Invalid invention: needs ' + ', '.join(DETAIL_SCHEMA['properties']['inventions']['items']['required']))
        slot = item['slot'].strip() if isinstance(item['slot'], str) else ''
        require(SLOT_PATTERN.match(slot), 'Invention slot must read like "<subject>/<facet>" (snake_case)')
        require(slot not in seen, 'Two inventions for one slot')
        seen.add(slot)
        require(item['kind'] in INVENTION_KINDS and item['scope'] in SCOPES and
                type(item['public']) is bool, 'Invalid invention kind, scope, or public flag')
        fact = item['fact']
        require(isinstance(fact, str) and 0 < len(fact.strip()) <= INVENTION_FACT_MAX_CHARS,
                f'Invention fact must be 1-{INVENTION_FACT_MAX_CHARS} characters')
        require(isinstance(item['basis'], str) and len(item['basis'].split()) >= 3 and
                len(item['basis'].strip()) <= INVENTION_BASIS_MAX_CHARS,
                'Invention basis must say why this is a DM choice (what the source leaves open), '
                f'in at most {INVENTION_BASIS_MAX_CHARS} characters')
        require(slot.split('/')[-1] not in (source or {}).get('facts', {}),
                'Invention collides with a source fact; the source already settles it')
        prior = canon.get(slot)
        if prior and normalize_fact(prior['fact']) != normalize_fact(fact):
            require(not is_none(item['change_reason']) and len(item['change_reason'].split()) >= 4,
                    f'Canon says {slot} is: {prior["fact"]} Keep it, or give the in-story event that '
                    'changed it in change_reason.')
        procedure = item['procedure'].strip()
        if not is_none(procedure):
            require(procedure in supported and item['kind'] == 'procedure',
                    'Only a procedure the runtime can run may be offered as playable. Supported: '
                    f'{", ".join(supported) or "none"}. Any game may be named as flavor (procedure none).')
        require(item['kind'] != 'procedure' or not is_none(procedure),
                'A procedure invention names the runtime procedure that runs it')
        if item['kind'] == 'price':
            quote = quote_in(fact, quotes)
            require(quote is not None,
                    'A price comes from the source, the DMG, the SRD, or Brendon\'s formula through '
                    'price_quote, and the fact states that amount and unit. Never invent one.')
            tier = kit_prices.tier_of(quote.get('srd_entry') or '') if target else None
            if tier:
                require(slot == f'{target}/{tier}',
                        f'{quote["srd_entry"]} is one tier of several: record it under {target}/{tier}, '
                        'the tier quoted')
        if slot == target or (target and slot.startswith(target + '/')):
            answers_target = True
            if choice in dealt:
                card = dealt[choice]
                require(keywords(fact) & keywords(card['entry']) or
                        set(_tokens(fact)) & set(_tokens(card['entry'])),
                        'The invention must be the dealt card you chose, interpreted, not a different idea')
                require(is_none(procedure) or procedure == card.get('procedure'),
                        'The chosen card names no such procedure')
            if item['kind'] != 'price':
                basis = dealt[choice]['basis'] if choice in dealt else item['basis']
                require(specific_enough(fact, basis, sensory),
                        'Specificity floor: the detail needs a proper noun, a number, a sensory word '
                        'from this place\'s texture, or a real-world or published basis.')
    needs_answer = choice in dealt or choice == 'self' or choice.casefold().startswith(OVERRIDE_PREFIX) \
        or choice == 'priced' or needs_price
    require(not needs_answer or answers_target,
            f'Record the answer: an invention for slot {target!r} persists it in the canon ledger')


def quote_in(fact, quotes):
    """The quote whose amount and unit the fact states, however it is said ("5 sp",
    "five silver"); whole numbers only, so a 25 gp quote is never found in "125 gp"."""
    stated = set(kit_guards.spoken_amounts(fact))
    return next((quote for quote in quotes if (quote['amount'], quote['unit']) in stated), None)


def canon_events(detail, turn_id, oracle, supported_prices=()):
    """Ledger events for this turn's inventions, plus the oracle draw it consumed."""
    detail = detail or NO_DETAIL
    dealt = {card['draw_id']: card for card in ((oracle or {}).get('deal') or [])}
    quotes = [price_result(quote) for quote in detail['price_quote']]
    sourced = source_quote(oracle) if detail['choice'] == 'source' else None
    quotes += [sourced] if sourced else []
    events = []
    for item in detail['inventions']:
        roots = dealt[detail['choice']]['roots'] if detail['choice'] in dealt and oracle and \
            item['slot'] == oracle['slot'] else []
        price = quote_in(item['fact'], quotes) if item['kind'] == 'price' else None
        events.append({'type': 'canon_entry', 'slot': item['slot'].strip(), 'kind': item['kind'],
                       'fact': item['fact'].strip(), 'basis': item['basis'].strip(),
                       'public': item['public'], 'scope': item['scope'],
                       'procedure': None if is_none(item['procedure']) else item['procedure'].strip(),
                       'change_reason': None if is_none(item['change_reason']) else item['change_reason'],
                       'choice': detail['choice'], 'roots': roots,
                       'price': {key: price[key] for key in ('amount', 'unit', 'basis', 'source')
                                 if key in price} if price else None,
                       'evidence': f'DM detail recorded with turn {turn_id}; the source does not supply it.'})
    if oracle and oracle.get('status') == 'open' and (detail['choice'] in dealt or
                                                      detail['choice'].casefold().startswith(OVERRIDE_PREFIX)):
        events.append({'type': 'oracle_draw', 'slot': oracle['slot'],
                       'card': dealt[detail['choice']]['card'] if detail['choice'] in dealt else None,
                       'evidence': f'Detail oracle deal consumed with turn {turn_id}.'})
    return events


def public_inventions(detail):
    return [item for item in (detail or NO_DETAIL)['inventions'] if item['public']]


# Rules from some other game, stated while a table game runs. Kit's game is the one the
# runtime runs; "high card takes it" or "one card apiece" is a game nobody is playing.
# Brendon's table call 1 (2026-10-02): never "high card for 1 gp" or "one card apiece".
# Blackjack and poker words are fine now: call 7 asks for an easy game of that class.
FOREIGN_RULES = re.compile(r"\bhigh(?:est)? card\b|\bone card (?:apiece|each)\b")


def check_detail_performance(segments, declared_procedures=(), game_terms=()):
    """HARD: rules or stakes stated as settled with no runtime procedure declared.

    While a procedure runs the guard stays on: only the running game's rules and stakes
    may be stated. A rules or stakes sentence must use that game's own terms
    (``game_terms``: ante, flight, gambit, stakes, strength...), and rules from another
    game ("highest card takes the pot", "one card apiece") are rejected."""
    for segment in segments:
        if segment['speaker'] == 'Kit':
            continue
        for sentence in re.split(r'(?<=[.!?])\s+|\n+', segment['text']):
            text = _norm(sentence)
            if not declared_procedures:
                require(not PROCEDURE_STATEMENT.search(text),
                        f'Undeclared procedure: the {segment["speaker"]} states rules or stakes '
                        f'("{sentence[:70]}") that no runtime procedure backs. Name any game as flavor, '
                        'or declare a supported one as a procedure invention.')
                continue
            words = set(re.findall(r"[a-z]+", text))
            foreign = FOREIGN_RULES.search(text)
            stated = PROCEDURE_STATEMENT.search(text)
            require(not foreign and not (stated and not words & set(game_terms)),
                    f'Rules the running game does not use: the {segment["speaker"]} states '
                    f'("{sentence[:70]}"). While a table game runs, only its own rules and stakes '
                    '(the procedure in table_procedures) may be stated.')


def check_detail_answer(segments, detail, player_action=''):
    """SOFT: the invention never showed, or a priced question got no number."""
    if detail is None or is_none(detail.get('request', 'none')):
        return
    spoken = set(_tokens(' '.join(segment['text'] for segment in segments)))
    shown = public_inventions(detail)
    wanted = {word for item in shown for word in keywords(item['fact'])}
    require(not wanted or spoken & wanted,
            'The performance never showed the detail it chose. Let the answer land in the scene.')
    said = set(kit_guards.spoken_amounts(' '.join(segment['text'] for segment in segments)))
    if detail.get('choice') == 'source':
        amounts = {pair for item in shown if item['kind'] == 'price'
                   for pair in kit_guards.spoken_amounts(item['fact'])}
        require(not amounts or said & amounts, 'Answer the literal question first: the player asked '
                'a price, so someone names it. Put the boldness in the terms around it.')
    if detail.get('choice') == 'priced':
        amounts = {(result['amount'], result['unit'])
                   for result in (price_result(quote) for quote in detail['price_quote'])}
        require(said & amounts, 'Answer the literal question first: the player asked a price, so '
                'someone names it (amount and unit). Put the boldness in the terms around it.')

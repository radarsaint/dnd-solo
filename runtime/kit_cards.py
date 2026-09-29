"""A table card game the runtime can actually run: the area 6c worked example of
"no NPC offers a procedure the runtime cannot carry".

The room source (area 6c) says only that four gamblers play cards with a marked deck
the dealer carries, with coins on the table. It names no game, rules, or stakes. Kit's
choice, declared as a DM choice through a ``procedure`` canon entry, is Three-Dragon
Ante, a Forgotten Realms card game many D&D players know, run with her own short
table rules (not the published rules). Texas hold 'em or blackjack would have been
equally valid; docs/architecture/kit-expression-gap.md (section i6) shows how the marked deck
works in each.

Everything here is deterministic and persisted: the procedure's state lives in world
state (``state['procedures'][id]``) as a ``public`` half the player sees and a
``private`` half only the DM sees, replaced by one ``procedure_state`` event per turn,
so every wager, round, cheat, check, and payout is in the append-only ledger.

The game config (stakes, seats, cheat bonuses) comes from the room source's
``procedures`` entry; this module names no room, actor, or amount of its own except
the dealer role the config names.
"""
import copy
import hashlib
import random
import re

from .state_context import InvalidChange, require

COLORS = ('red', 'blue', 'green', 'black', 'white')
STRENGTHS = tuple(range(1, 10))
HAND_SIZE = 3
MAX_LEVEL = 2  # bet levels above the ante: one NPC raise, one player raise


class NeedsRuling(Exception):
    """A card action the table cannot resolve yet (message says why). `attempt` is
    True for an in-fiction attempt, False for a host input the player must supply."""
    def __init__(self, message, attempt=False):
        super().__init__(message)
        self.attempt = attempt


def card_name(card):
    color, strength = card
    return f'{color} {strength}'


def score(hand):
    """A flight (all three one color) beats any mixed hand; otherwise higher total wins."""
    total = sum(strength for _, strength in hand)
    return (100 + total) if len({color for color, _ in hand}) == 1 else total


def describe_hand(hand):
    kind = 'a flight' if score(hand) >= 100 else 'mixed'
    return f'{", ".join(card_name(card) for card in hand)} ({kind}, strength {sum(s for _, s in hand)})'


def initial_state(config):
    seats = {actor: {'gp': gp, 'in_hand': False} for actor, gp in config['seats'].items()}
    return {
        'public': {
            'name': config['name'], 'dm_choice': config['dm_choice'], 'rules': config['public_rules'],
            'unit': config['unit'], 'ante': config['ante'], 'raise': config['raise'],
            'stacks': {actor: seat['gp'] for actor, seat in seats.items()},
            'stacks_note': config.get('stacks_note', ''),
            'player': None, 'hand': None, 'hands_played': 0, 'last_result': None,
            'table_mood': 'open',
        },
        'private': {'hands': {}, 'cheat_log': [], 'deck_order_seed': None},
    }


def _rng(seed, *parts):
    material = ':'.join(str(part) for part in (seed, *parts)).encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], 'big'))


def _d20(seed, *parts):
    return _rng(seed, 'd20', *parts).randint(1, 20)


# Player-supplied rolls: "rolled 14", "roll: 14", "d20 14", "natural 14", or Nik's
# "7 + 4 = 11" (die, modifier, total).
_ROLL_SUM = re.compile(r'\b(\d{1,2})\s*\+\s*(-?\d{1,2})\s*=\s*(-?\d{1,3})\b')
_ROLL = re.compile(r'\b(?:rolled|roll(?:ed)?:?|d20:?|natural|nat)\s*(?:a\s+)?(\d{1,2})\b')


def supplied_roll(action):
    """(die, modifier or None) from the player's own words, or None."""
    text = action.casefold()
    found = _ROLL_SUM.search(text)
    if found:
        die, modifier, total = (int(group) for group in found.groups())
        require(1 <= die <= 20 and die + modifier == total, 'Supplied roll does not add up')
        return die, modifier
    found = _ROLL.search(text)
    if found:
        die = int(found.group(1))
        require(1 <= die <= 20, 'A supplied d20 roll must be 1-20')
        return die, None
    return None


_AMOUNT = re.compile(r'\b(\d{1,4})\s*(?:gp|gold)\b')

CARD_INTENTS = (
    ('card_accuse', re.compile(r"\b(accuse|cheat|cheating|cheater|cheats|crooked|rigged|marked)\w*\b")),
    ('card_swap', re.compile(r"\b(palm|swap|switch|slip|sleight of hand|hold out|hide a card|"
                             r"card up my sleeve)\w*\b")),
    ('card_read', re.compile(r"\b(bluff\w*|read (him|the dealer|his face|them)|insight|tell)\b")),
    ('card_watch', re.compile(r"\b(watch|eye|study|keep an eye on)\w*\b[^.]*\b(deal|dealing|hands|"
                              r"fingers|dealer|cards)\b")),
    ('card_leave', re.compile(r"\b(cash out|leave the (game|table)|i'?m out|quit the game|stand up from)\b")),
    ('card_bet', re.compile(r"\b(fold|folds|call|calls|check|raise|raises|bet|bets|match)\b")),
    ('card_join', re.compile(r"\b(buy in|buy-in|deal me in|i'?m in|join|sit in|ante|next hand|"
                             r"deal (again|another)|another hand|play a hand|deal)\b")),
)


def card_intent(action, procedure_state):
    """A card-table action, when a card procedure is declared; otherwise None."""
    if procedure_state is None:
        return None
    text = action.casefold().replace('\u2019', "'")
    hand = procedure_state['public']['hand']
    seated = procedure_state['public']['player'] is not None
    for kind, pattern in CARD_INTENTS:
        if not pattern.search(text):
            continue
        if kind == 'card_accuse' and not (seated or hand):
            return None  # an accusation away from the game is ordinary conversation
        if kind in ('card_swap', 'card_read', 'card_bet') and not (seated and hand and hand['phase'] == 'betting'):
            continue  # no live hand: "call", "check", "tell" are ordinary words
        if kind == 'card_watch' and not seated:
            continue
        if kind == 'card_leave' and not seated:
            continue
        if kind == 'card_join' and seated and hand and hand['phase'] == 'betting':
            continue
        return kind
    return None


def _order(config):
    """Seat order: the player acts after the others; the dealer deals and acts last among them."""
    dealer = config['cheat']['actor']
    return [actor for actor in config['seats'] if actor != dealer] + [dealer]


class CardTable:
    """Resolve one card action into (public_event, new_state, reveal_facts)."""

    def __init__(self, procedure_id, config, modifiers, seed):
        self.id = procedure_id
        self.config = config
        self.modifiers = modifiers  # {'perception': int|None, 'insight': ..., 'sleight_of_hand': ...}
        self.seed = seed

    def _modifier(self, skill, action):
        supplied = supplied_roll(action)
        if supplied and supplied[1] is not None:
            return supplied[1]
        value = self.modifiers.get(skill)
        if value is None:
            flag = skill.replace('_', '-')
            raise NeedsRuling(f'Supply your {skill.replace("_", " ").title()} modifier with --{flag} '
                              f'(or give your roll as "d20 + modifier = total"). No turn was committed.')
        return value

    def _player_roll(self, action, revision, label):
        supplied = supplied_roll(action)
        return supplied[0] if supplied else _d20(self.seed, revision, label, action.casefold())

    def resolve(self, kind, action, revision, state):
        game = copy.deepcopy(state)
        public, private = game['public'], game['private']
        handler = getattr(self, '_' + kind[len('card_'):])
        text, reveals = handler(action, revision, public, private)
        return text, game, reveals

    # -- seating and dealing ------------------------------------------------
    def _join(self, action, revision, public, private):
        if public['player'] is None:
            found = _AMOUNT.search(action.casefold())
            if not found:
                raise NeedsRuling('How much gold do you bring to the table? Say it in your action, for '
                                  f'example "I buy in with 20 gold." The ante is {public["ante"]} '
                                  f'{public["unit"]}. No turn was committed.')
            amount = int(found.group(1))
            require(amount >= public['ante'], f'A buy-in must cover the {public["ante"]} gp ante')
            public['player'] = {'gp': amount, 'bought_in': amount, 'watch_next_deal': False,
                                'unwelcome': False}
            text = (f'You buy in with {amount} gp (your declared purse). {public["name"]}: '
                    f'ante {public["ante"]} gp, raises {public["raise"]} gp.')
            if not re.search(r'\bdeal\b', action.casefold()):
                return text, []
            deal_text, reveals = self._deal(action, revision, public, private)
            return f'{text} {deal_text}', reveals
        return self._deal(action, revision, public, private)

    def _watch(self, action, revision, public, private):
        public['player']['watch_next_deal'] = True
        if public['hand'] and public['hand']['phase'] == 'betting':
            return 'You settle your eyes on the dealer\'s hands for the next deal.', []
        return self._deal(action, revision, public, private)

    def _deal(self, action, revision, public, private):
        player = public['player']
        require(player is not None, 'Buy in before the deal')
        if player['unwelcome']:
            raise NeedsRuling('The table will not deal you in after you were caught. No turn was committed.',
                              attempt=True)
        require(not (public['hand'] and public['hand']['phase'] == 'betting'),
                'A hand is already in play')
        ante = public['ante']
        if player['gp'] < ante:
            raise NeedsRuling('You do not have the ante left. No turn was committed.', attempt=True)
        number = public['hands_played'] + 1
        deck = [(color, strength) for color in COLORS for strength in STRENGTHS]
        _rng(self.seed, 'deck', number).shuffle(deck)
        order = _order(self.config)
        dealer = self.config['cheat']['actor']
        hands, cursor = {}, 0
        for seat in ['player'] + order:
            hands[seat] = deck[cursor:cursor + HAND_SIZE]
            cursor += HAND_SIZE
        # The marked deck: the dealer reads the backs and deals himself the better of his
        # own hand and the next three off the top (dealing seconds).
        honest, alternative = hands[dealer], deck[cursor:cursor + HAND_SIZE]
        cheated = score(alternative) > score(honest)
        if cheated:
            hands[dealer] = alternative
            cursor += HAND_SIZE
        pot = public['hand']['pot'] if public['hand'] else 0  # an odd split carries over
        in_hand = []
        paid = {}
        for seat in order:
            if public['stacks'][seat] >= ante:
                public['stacks'][seat] -= ante
                pot += ante
                paid[seat] = ante
                in_hand.append(seat)
        player['gp'] -= ante
        pot += ante
        paid['player'] = ante
        known = score(hands['player'])  # what the marks tell the dealer about your hand
        level, raised_by, bluffing = 0, None, False
        folded = []
        for seat in in_hand:
            mine = score(hands[seat])
            if seat == dealer:
                ahead = mine > known
                bluffing = (not ahead and level == 0 and _rng(self.seed, 'bluff', number).random() < 0.34)
                wants_raise = (ahead or bluffing) and level == 0
            else:
                wants_raise = level == 0 and mine >= 20
            if wants_raise and public['stacks'][seat] >= public['raise']:
                level, raised_by = 1, seat
                public['stacks'][seat] -= public['raise']
                pot += public['raise']
                paid[seat] += public['raise']
            elif level and seat != raised_by:
                stays = (mine > known) if seat == dealer else mine >= 14
                if stays and public['stacks'][seat] >= public['raise']:
                    public['stacks'][seat] -= public['raise']
                    pot += public['raise']
                    paid[seat] += public['raise']
                else:
                    folded.append(seat)
        if raised_by:
            # Seats that checked before the raise must now call it or fold; nobody stays
            # in the hand for less than the bet.
            for seat in in_hand[:in_hand.index(raised_by)]:
                mine = score(hands[seat])
                stays = (mine > known) if seat == dealer else mine >= 14
                if stays and public['stacks'][seat] >= public['raise']:
                    public['stacks'][seat] -= public['raise']
                    pot += public['raise']
                    paid[seat] += public['raise']
                else:
                    folded.append(seat)
        remaining = [seat for seat in in_hand if seat not in folded]
        watched = player['watch_next_deal']
        player['watch_next_deal'] = False
        detection = None
        reveals = []
        if watched:
            modifier = self._modifier('perception', action)
            die = self._player_roll(action, revision, 'watch')
            bonus = self.config['cheat']['sleight_bonus']
            his = _d20(self.seed, revision, 'deal-sleight', number) + bonus
            caught = cheated and die + modifier > his
            detection = {'skill': 'Perception', 'die': die, 'modifier': modifier,
                         'total': die + modifier, 'opposed': his, 'caught': caught}
            if caught:
                reveals.append(self.config['cheat']['reveals_fact'])
        public['hand'] = {
            'number': number, 'phase': 'betting', 'your_cards': [card_name(c) for c in hands['player']],
            'pot': pot, 'bet_level': level, 'to_call': level * public['raise'],
            'raised_by': raised_by, 'folded': folded, 'in_hand': remaining, 'paid': paid,
            'cheat_seen': bool(detection and detection['caught']), 'read': None, 'swapped': False,
        }
        private['hands'] = {str(number): {
            'hands': {seat: [list(card) for card in cards] for seat, cards in hands.items()},
            'cheated': cheated, 'bluffing': bluffing, 'dealer_knows_player_score': known,
            'deck_cursor': cursor}}
        private['cheat_log'].append({'hand': number, 'cheated': cheated,
                                     'detection': detection})
        private['cheat_log'] = private['cheat_log'][-8:]
        lines = [f'Hand {number}: everyone antes {ante} gp; the pot holds {pot} gp. Your cards: '
                 f'{describe_hand(hands["player"])}.']
        if raised_by:
            lines.append(f'{self.config["labels"][raised_by]} raises {public["raise"]} gp; '
                         f'{public["raise"]} gp to call.')
        else:
            lines.append('Nobody raises before you.')
        if folded:
            lines.append('Folded: ' + ', '.join(self.config['labels'][seat] for seat in folded) + '.')
        if detection:
            outcome = (self.config['cheat']['caught_text'] if detection['caught'] else
                       'Nothing about the deal looks wrong to you.')
            lines.append(f'{outcome} (Perception {detection["total"]} vs {detection["opposed"]})')
        lines.append('Fold, call, or raise.')
        return ' '.join(lines), reveals

    # -- betting and showdown -------------------------------------------------
    def _bet(self, action, revision, public, private):
        hand = public['hand']
        text = action.casefold()
        player = public['player']
        if re.search(r'\bfolds?\b', text):
            return self._showdown(public, private, player_in=False,
                                  lead='You fold.'), []
        if re.search(r'\braises?\b|\bbet\b', text) and hand['bet_level'] < MAX_LEVEL:
            cost = hand['to_call'] + public['raise']
            if player['gp'] < cost:
                raise NeedsRuling(f'A raise costs {cost} gp and you have {player["gp"]} gp. No turn was '
                                  'committed.', attempt=True)
            player['gp'] -= cost
            hand['pot'] += cost
            hand['paid']['player'] += cost
            hand['bet_level'] += 1
            lead = f'You raise: {cost} gp in.'
            secret = private['hands'][str(hand['number'])]
            known = secret['dealer_knows_player_score']
            dealer = self.config['cheat']['actor']
            for seat in list(hand['in_hand']):
                mine = score([tuple(card) for card in secret['hands'][seat]])
                stays = (mine > known) if seat == dealer else mine >= 16
                if stays and public['stacks'][seat] >= public['raise']:
                    public['stacks'][seat] -= public['raise']
                    hand['pot'] += public['raise']
                    hand['paid'][seat] += public['raise']
                else:
                    hand['in_hand'].remove(seat)
                    hand['folded'].append(seat)
            return self._showdown(public, private, player_in=True, lead=lead), []
        cost = hand['to_call']
        if player['gp'] < cost:
            raise NeedsRuling(f'Calling costs {cost} gp and you have {player["gp"]} gp. No turn was '
                              'committed.', attempt=True)
        player['gp'] -= cost
        hand['pot'] += cost
        hand['paid']['player'] += cost
        lead = f'You call {cost} gp.' if cost else 'You check.'
        return self._showdown(public, private, player_in=True, lead=lead), []

    def _showdown(self, public, private, player_in, lead):
        hand = public['hand']
        secret = private['hands'][str(hand['number'])]
        hands = {seat: [tuple(card) for card in cards] for seat, cards in secret['hands'].items()}
        contenders = list(hand['in_hand']) + (['player'] if player_in else [])
        best = max(score(hands[seat]) for seat in contenders)
        winners = [seat for seat in contenders if score(hands[seat]) == best]
        share, remainder = divmod(hand['pot'], len(winners))
        for seat in winners:
            if seat == 'player':
                public['player']['gp'] += share
            else:
                public['stacks'][seat] += share
        labels = {**self.config['labels'], 'player': 'You'}
        shown = '; '.join(f'{labels[seat]}: {describe_hand(hands[seat])}' for seat in contenders)
        result = {'hand': hand['number'], 'winners': [labels[seat] for seat in winners],
                  'pot': hand['pot'], 'share': share, 'shown': shown,
                  'your_gp': public['player']['gp'],
                  'net_since_buy_in': public['player']['gp'] - public['player']['bought_in']}
        hand['phase'] = 'done'
        hand['pot'] = remainder
        public['hands_played'] = hand['number']
        public['last_result'] = result
        who = ' and '.join(result['winners'])
        return (f'{lead} Showdown. {shown}. {who} take{"" if who == "You" else "s"} '
                f'{share} gp. You now hold {result["your_gp"]} gp.')

    # -- reading, counter-cheating, accusing, leaving --------------------------
    def _read(self, action, revision, public, private):
        hand = public['hand']
        modifier = self._modifier('insight', action)
        die = self._player_roll(action, revision, 'read')
        his = _d20(self.seed, revision, 'deception', hand['number']) + self.config['cheat']['deception_bonus']
        secret = private['hands'][str(hand['number'])]
        dealer_in = self.config['cheat']['actor'] in hand['in_hand']
        total = die + modifier
        if total > his and dealer_in:
            if secret['bluffing']:
                seen = 'His confidence is a performance: he is bluffing.'
            elif secret['cheated'] or hand['raised_by'] == self.config['cheat']['actor']:
                seen = 'He bets like a man who already knows what you are holding.'
            else:
                seen = 'He is playing it straight this hand, and he does not love his cards.'
        elif not dealer_in:
            seen = 'The dealer has already folded; there is nothing of his left to read.'
        else:
            seen = 'You cannot see past the performance.'
        hand['read'] = seen
        return f'{seen} (Insight {total} vs {his})', []

    def _swap(self, action, revision, public, private):
        hand = public['hand']
        require(not hand['swapped'], 'You already worked a card this hand')
        modifier = self._modifier('sleight_of_hand', action)
        die = self._player_roll(action, revision, 'swap')
        passive = self.config['cheat']['passive_perception']
        total = die + modifier
        secret = private['hands'][str(hand['number'])]
        hand['swapped'] = True
        if total >= passive:
            deck = [(color, strength) for color in COLORS for strength in STRENGTHS]
            _rng(self.seed, 'deck', hand['number']).shuffle(deck)
            cards = [tuple(card) for card in secret['hands']['player']]
            fresh = deck[secret['deck_cursor']]
            secret['deck_cursor'] += 1
            lowest = min(cards, key=lambda card: card[1])
            cards[cards.index(lowest)] = fresh
            secret['hands']['player'] = [list(card) for card in cards]
            hand['your_cards'] = [card_name(card) for card in cards]
            # The dealer's knowledge of your hand is now stale: the marks told him the old one.
            return (f'Your {card_name(lowest)} goes up your sleeve and the {card_name(fresh)} comes '
                    f'off the deck unseen. Your cards: {describe_hand(cards)}. (Sleight of Hand '
                    f'{total} vs passive Perception {passive})'), []
        forfeited = hand['pot']
        public['player']['unwelcome'] = True
        public['table_mood'] = 'hostile: caught you cheating'
        # The table splits your stake in the pot; the hand ends.
        takers = hand['in_hand'] or [self.config['cheat']['actor']]
        share, remainder = divmod(forfeited, len(takers))
        for seat in takers:
            public['stacks'][seat] += share
        hand['phase'] = 'done'
        hand['pot'] = remainder
        public['hands_played'] = hand['number']
        public['last_result'] = {'hand': hand['number'], 'caught_cheating': True, 'pot': forfeited,
                                 'your_gp': public['player']['gp']}
        return (f'The dealer\'s hand closes over your wrist before the card clears your cuff. The pot '
                f'({forfeited} gp) goes to the table, and nobody will deal to you now. (Sleight of Hand '
                f'{total} vs passive Perception {passive})'), []

    def _accuse(self, action, revision, public, private):
        hand = public['hand']
        seen = bool(hand and hand.get('cheat_seen'))
        record = public.setdefault('accusations', [])
        if seen and hand['phase'] == 'betting':
            # Proof in the open: the hand is dead and every stake goes back to whoever paid it.
            # The dealer, true to the source, blames someone else rather than confess.
            for seat, amount in hand['paid'].items():
                if seat == 'player':
                    public['player']['gp'] += amount
                else:
                    public['stacks'][seat] += amount
            hand['phase'] = 'done'
            hand['pot'] -= sum(hand['paid'].values())  # a remainder carried from the last hand stays
            public['hands_played'] = hand['number']
            public['table_mood'] = 'tense: accused with proof'
            record.append({'hand': hand['number'], 'backed': True})
            return ('The hand is dead: every stake goes back to its owner. You saw the deal, and the '
                    'whole table knows you saw it. The dealer does not confess.'), []
        public['table_mood'] = 'tense: accused without proof'
        record.append({'hand': hand['number'] if hand else None, 'backed': False})
        return ('Nothing on the table proves it. The game stops while every face at the table turns '
                'to you.'), []

    def _leave(self, action, revision, public, private):
        player = public['player']
        net = player['gp'] - player['bought_in']
        public['last_result'] = {'left_table': True, 'your_gp': player['gp'], 'net_since_buy_in': net}
        public['player'] = None
        return (f'You gather your {player["gp"]} gp and leave the game '
                f'({"up" if net >= 0 else "down"} {abs(net)} gp on your {player["bought_in"]} gp buy-in).'), []


def public_view(config, public):
    """The player-visible half with every seat under its public label. Seat keys are DM
    actor ids (one of them names a hidden identity), so they never leave the DM side."""
    labels = {**config.get('labels', {}), 'player': 'you'}

    def label(seat):
        return labels.get(seat, seat)
    view = copy.deepcopy(public)
    view['stacks'] = {label(seat): gp for seat, gp in view['stacks'].items()}
    hand = view.get('hand')
    if hand:
        hand['paid'] = {label(seat): gp for seat, gp in hand.get('paid', {}).items()}
        hand['in_hand'] = [label(seat) for seat in hand.get('in_hand', [])]
        hand['folded'] = [label(seat) for seat in hand.get('folded', [])]
        if hand.get('raised_by'):
            hand['raised_by'] = label(hand['raised_by'])
    return view


def declared_procedures(state):
    return sorted((state or {}).get('procedures', {}))


def check_config(config):
    for key in ('name', 'dm_choice', 'public_rules', 'unit', 'ante', 'raise', 'seats', 'cheat', 'labels'):
        require(key in config, f'Card procedure config needs {key}')
    for key in ('actor', 'sleight_bonus', 'deception_bonus', 'passive_perception', 'reveals_fact',
                'caught_text'):
        require(key in config['cheat'], f'Card procedure cheat config needs {key}')
    if not all(actor in config['labels'] for actor in config['seats']):
        raise InvalidChange('Every seat needs a public label')

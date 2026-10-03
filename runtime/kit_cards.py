"""A table card game the runtime can actually run: the area 6c worked example of
"no NPC offers a procedure the runtime cannot carry".

The room source (area 6c) says only that four gamblers play cards with a marked deck
the dealer carries, with coins on the table. It names no game, rules, or stakes. Kit's
choice, declared as a DM choice through a ``procedure`` canon entry, is Three-Dragon
Ante, a Forgotten Realms card game many D&D players know. This module runs it in the
game's real shape: each gambit opens with every player anteing a card, the strongest
ante card sets the gold everyone pays into the stakes, and players then play cards into
a flight over three rounds. A card no stronger than the card played just before it that
round (or the first card of a round) triggers its color's power; three of one color or
one strength in a flight is a special flight that pays at once; the strongest flight
takes the stakes. The deck, the ten powers, and the tie rules below are Kit's own short
table version, written in our own words; they are not the published card text.
docs/architecture/kit-expression-gap.md (section i6) shows how the marked deck works in
this game and in the alternatives Kit could have picked.

Everything here is deterministic and persisted: the procedure's state lives in world
state (``state['procedures'][id]``) as a ``public`` half the player sees and a
``private`` half only the DM sees, replaced by one ``procedure_state`` event per turn,
so every ante, card, power, cheat, check, and payout is in the append-only ledger. Gold
only moves between seats, the player's table purse, and the stakes: the total is
conserved (tests/test_kit_06c_play.py).

The game config (seats, stacks, cheat bonuses) comes from the room source's
``procedures`` entry; this module names no room, actor, or amount of its own except
the dealer role the config names.
"""
import copy
import hashlib
import random
import re

from .state_context import InvalidChange, require

# Kit's deck: ten dragon colors, six cards each. Chromatic dragons' powers move gold;
# metallic dragons' powers move cards (the published game's broad theme, simplified).
DECK = {
    'red': (2, 3, 5, 8, 10, 12), 'blue': (1, 2, 4, 7, 9, 11), 'green': (1, 2, 4, 6, 8, 10),
    'black': (1, 2, 3, 5, 7, 9), 'white': (1, 2, 3, 4, 6, 8),
    'gold': (2, 4, 6, 9, 11, 13), 'silver': (2, 3, 6, 8, 10, 12), 'bronze': (1, 3, 5, 7, 9, 11),
    'brass': (1, 2, 4, 5, 7, 9), 'copper': (1, 3, 5, 7, 8, 10),
}
COLORS = tuple(DECK)
POWERS = {
    'red': 'the owner of the strongest other flight pays you 1 gp',
    'blue': 'every other player pays 1 gp into the stakes',
    'green': 'the next player in turn order pays you 1 gp',
    'black': 'you take 2 gp from the stakes',
    'white': 'the owner of the weakest flight pays 1 gp into the stakes',
    'gold': 'you draw 2 cards',
    'silver': 'every player draws 1 card',
    'bronze': 'you take the weakest ante card into your hand',
    'brass': 'you draw 1 card',
    'copper': 'you discard your weakest card in hand and draw 2',
}
HAND_SIZE = 6
HAND_LIMIT = 10
ROUNDS = 3
RULES = (
    'Kit\'s table version of Three-Dragon Ante: a deck of dragon cards in ten colors, five '
    'chromatic (red, blue, green, black, white) and five metallic (gold, silver, bronze, brass, '
    'copper), strengths 1 to 13. Everyone holds six cards and refills to six before each gambit.',
    'A gambit opens with the ante: each player puts one card from hand face down, and all are '
    'turned up together. The strongest ante card sets the stakes: every player pays that many gp '
    '(or all they have). The player with the strongest ante leads; if the strongest ante cards '
    'tie, the tied player nearest the dealer\'s left leads.',
    'Then three rounds: in turn, each player plays one card face up into their flight. The first '
    'card of a round, or a card no stronger than the card played just before it that round, '
    'triggers its color\'s power. The strongest card of a round leads the next.',
    'A flight with three cards of one color is a color flight: every other player pays you the '
    'strength of its second-strongest card of that color. Three cards of one strength is a '
    'strength flight: take that much gold from the stakes and up to two ante cards into your hand.',
    'After the third round the flight with the highest total strength takes the stakes; tied '
    'flights split them and any odd gp stays for the next gambit.',
)
RULE_TERMS = ('ante', 'gambit', 'flight', 'dragon', 'stakes', 'strength', 'strongest', 'lead',
              'leads', 'color', 'chromatic', 'metallic', 'power', 'round', 'hoard')


class NeedsRuling(Exception):
    """A card action the table cannot resolve yet (message says why). `attempt` is
    True for an in-fiction attempt, False for a host input the player must supply."""
    def __init__(self, message, attempt=False):
        super().__init__(message)
        self.attempt = attempt


def card_name(card):
    color, strength = card
    return f'{color} {strength}'


def strength(card):
    return card[1]


def flight_total(cards):
    return sum(strength(card) for card in cards)


def _tda_initial_state(config):
    return {
        'public': {
            'name': config['name'], 'dm_choice': config['dm_choice'], 'unit': config['unit'],
            'stacks': dict(config['seats']), 'stacks_note': config.get('stacks_note', ''),
            'player': None, 'gambit': None, 'carried': 0, 'gambits_played': 0,
            'last_result': None, 'table_mood': 'open',
        },
        'private': {'hands': {}, 'deck': None, 'discard': [], 'cheated': False,
                    'cheat_log': [], 'snapshot': None},
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
_NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13}
_NUM = r'(\d{1,2}|' + '|'.join(_NUMBER_WORDS) + r')'


def _number(token):
    return int(token) if token.isdigit() else _NUMBER_WORDS[token]


def parse_card(action, hand):
    """The card in `hand` the player's words name ("the red 8", "red eight", "my 8 of
    red", "the gold dragon" when only one gold is held, "my strongest card"), or None."""
    text = action.casefold().replace('\u2019', "'")
    cards = [tuple(card) for card in hand]
    for card in cards:
        color = card[0]
        for pattern in (rf'\b{color}\b(?:\s+(?:dragon|card))?(?:\s*,)?(?:\s+(?:of\s+)?strength)?\s+{_NUM}\b',
                        rf'\b{_NUM}\s+(?:of\s+)?{color}\b'):
            for found in re.finditer(pattern, text):
                if _number(found.group(1)) == card[1]:
                    return card
    named = [color for color in COLORS if re.search(rf'\b{color}\b', text)]
    if len(named) == 1:
        matching = [card for card in cards if card[0] == named[0]]
        if len(matching) == 1:
            return matching[0]
    if not named and cards:
        if re.search(r'\b(strongest|highest|best|biggest)\b', text):
            return max(cards, key=strength)
        if re.search(r'\b(weakest|lowest|worst|smallest)\b', text):
            return min(cards, key=strength)
    return None


# Accusations say the dealer did it: "You dealt yourself the second card", "you're
# cheating", "he palmed one", "I accuse him". Watching for cheating is not one.
_ACCUSE = re.compile(
    r"\baccus\w*|\b(you|he|she|the dealer)(?:'re|'s| is| are)? (?:(?:just|clearly|always|been|obviously|"
    r"definitely|totally) ){0,2}"
    r"(cheat\w*|dealt (?:yourself|himself|herself)|deal(?:s|ing)? (?:yourself|himself|herself|"
    r"seconds|from the bottom|off the bottom)|palm\w*|stack\w* the deck|mark\w* (?:the|these|this))\b"
    r"|\b(?:this|the|your|his) deck(?:'s| is) (?:marked|rigged|stacked)\b"
    r"|^\s*(?:\w+,\s*)?cheat(?:er|ing)?\s*[!.]*$|\bcheat(?:er|ing)!")
_CHEAT_WORD = re.compile(r"\b(cheat\w*|crooked|rigged|marked)\b")
_WATCH = re.compile(
    r"\b(?:i|i'll|i will|i'm going to|let me)\s+(?:\w+\s+){0,2}?(?:watch\w*|eye\w*|study\w*|"
    r"keep (?:an|my|both) eyes? on|look(?:s|ing)? (?:for|at|closely at)|track\w*|scrutini[sz]e\w*)\b"
    r"[^.?!]*\b(deal|dealing|dealt|hands?|fingers|dealer|cards?|deck|cheat\w*|seconds|shuffle)\b"
    r"|^\s*(?:watch|eye|study)\w*\b[^.?!]*\b(deal|dealing|hands?|fingers|dealer|cards?|deck|cheat\w*)\b")
_SWAP = re.compile(r"\b(palm|swap|switch|slip|sleight of hand|hold out|hide a card|"
                   r"card up my sleeve)\w*\b")
_READ = re.compile(r"\b(bluff\w*|read (him|the dealer|his face|them|her)|insight|his tell|"
                   r"size (him|the dealer|them) up)\b")
_LEAVE = re.compile(r"\b(cash out|leave the (game|table)|i'?m out|quit the game|stand up from)\b")
_JOIN = re.compile(r"\b(buy in|buy-in|deal me in|i'?m in|join|sit in|sit down|next gambit|"
                   r"another gambit|another (hand|round)|deal (again|another|the next)|play a gambit|"
                   r"deal)\b")
_PLAY_VERB = re.compile(r"\b(ante|play|plays|lay|lays|throw|put down|put up|lead with|drop)\b")


def in_gambit(procedure_state):
    gambit = procedure_state['public'].get('gambit')
    return bool(gambit and gambit['phase'] in ('ante', 'play'))


def _tda_intent(action, procedure_state):
    """A card-table action, when a card procedure is declared; otherwise None (speech).

    Order matters: an accusation names what the dealer did; watching the deal is a
    Perception move even when the words say "cheating"; a question that is not a card
    move ("Tell me about the ring", "Are you cheating?") is ordinary speech."""
    if procedure_state is None:
        return None
    text = action.casefold().replace('\u2019', "'").strip()
    public = procedure_state['public']
    seated = public['player'] is not None
    live = in_gambit(procedure_state)
    playing = seated and live and 'player' not in public['gambit'].get('out', [])
    question = text.rstrip().endswith('?')
    if _LEAVE.search(text):
        return 'card_leave' if seated else None
    if _ACCUSE.search(text) and not question:
        return 'card_accuse' if (seated or public['gambit']) else None
    if _WATCH.search(text):
        return 'card_watch' if seated else None
    if playing and _SWAP.search(text) and not question:
        return 'card_swap'
    if playing and _READ.search(text) and not question:
        return 'card_read'
    if playing and public['gambit']['to_act'] == 'player':
        hand = public['player']['hand']
        names = parse_card(text, [_parse_name(name) for name in hand])
        if names and (_PLAY_VERB.search(text) or not question):
            return 'card_ante' if public['gambit']['phase'] == 'ante' else 'card_play'
        if _PLAY_VERB.search(text) and not question:
            return 'card_ante' if public['gambit']['phase'] == 'ante' else 'card_play'
    if _CHEAT_WORD.search(text) and not question and (seated or public['gambit']):
        return 'card_accuse'
    if not live and not question and _JOIN.search(text):
        return 'card_join'
    return None


def _parse_name(name):
    color, value = name.split()
    return (color, int(value))


def order_from(config, first):
    seats = seat_order(config)
    index = seats.index(first)
    return seats[index:] + seats[:index]


def seat_order(config):
    """Turn order: the player sits at the dealer's left and acts first; the dealer last."""
    dealer = config['cheat']['actor']
    return ['player'] + [actor for actor in config['seats'] if actor != dealer] + [dealer]


class CardTable:
    """Resolve one card action into (public_event, new_state, reveal_facts)."""

    def __init__(self, procedure_id, config, modifiers, seed, passives=None, dcs=None):
        self.id = procedure_id
        self.config = config
        self.modifiers = modifiers  # {'perception': int|None, 'insight': ..., 'sleight_of_hand': ...}
        # The PC's passive scores: a passive that meets the number succeeds with no roll.
        self.passives = passives or {}
        # NPCs never roll here: each contest is a fixed number, the NPC's flat 10 + skill
        # (or, for watching the deal, the hidden claim's own DC so both paths agree).
        cheat = config['cheat']
        self.dcs = {'watch': 10 + cheat['sleight_bonus'], 'read': 10 + cheat['deception_bonus'],
                    'swap': cheat['passive_perception'], **(dcs or {})}
        self.seed = seed
        self.labels = {**config['labels'], 'player': 'You'}
        self.trace = []  # the numbers behind this action, for the ledger only
        self.toll_outcome = None

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

    def _contest(self, skill, key, action, revision, label, passive_counts=True):
        """The PC against one fixed number (meet or beat). When their passive already
        meets it the result is automatic and nothing is rolled (passive_counts False for
        something the PC must actively pull off, like a sleight)."""
        dc = self.dcs[key]
        passive = self.passives.get(skill) if passive_counts else None
        if passive is not None and passive >= dc:
            return {'auto': True, 'total': passive, 'dc': dc, 'success': True, 'die': None, 'modifier': None}
        modifier = self._modifier(skill, action)
        die = self._player_roll(action, revision, label)
        return {'auto': False, 'die': die, 'modifier': modifier, 'total': die + modifier, 'dc': dc,
                'success': die + modifier >= dc}

    def _note(self, name, result, against='DC'):
        """Record the numbers behind a contest in the turn's trace (ledger evidence).
        Numbers never reach public text (Brendon's table call 4)."""
        if result['auto']:
            line = f'passive {name} {result["total"]} meets {against} {result["dc"]}; no roll'
        else:
            line = (f'{name} d20 {result["die"]} + {result["modifier"]} = {result["total"]} vs '
                    f'{against} {result["dc"]}: {"success" if result["success"] else "failure"}')
        self.trace.append(line)
        return ''

    def resolve(self, kind, action, revision, state):
        game = copy.deepcopy(state)
        public, private = game['public'], game['private']
        handler = getattr(self, '_' + kind[len('card_'):])
        text, reveals = handler(action, revision, public, private)
        self._sync_player_hand(public, private)
        return text, game, reveals

    # -- gold -------------------------------------------------------------
    def _gp(self, public, seat):
        return public['player']['gp'] if seat == 'player' else public['stacks'][seat]

    def _add(self, public, seat, amount):
        if seat == 'player':
            public['player']['gp'] += amount
        else:
            public['stacks'][seat] += amount

    def _pay(self, public, payer, payee, amount):
        """Move up to `amount` gp from payer to payee ('stakes' or a seat); returns what moved."""
        gambit = public['gambit']
        amount = max(0, min(amount, gambit['stakes'] if payer == 'stakes' else self._gp(public, payer)))
        if payer == 'stakes':
            gambit['stakes'] -= amount
        else:
            self._add(public, payer, -amount)
        if payee == 'stakes':
            gambit['stakes'] += amount
        else:
            self._add(public, payee, amount)
        return amount

    # -- cards ----------------------------------------------------------------
    def _draw(self, private, number):
        if not private['deck']:
            private['deck'] = private['discard']
            private['discard'] = []
            _rng(self.seed, 'reshuffle', number, len(private['deck'])).shuffle(private['deck'])
        return private['deck'].pop(0) if private['deck'] else None

    def _give(self, private, seat, count, number):
        hand = private['hands'].setdefault(seat, [])
        for _ in range(count):
            if len(hand) >= HAND_LIMIT:
                break
            card = self._draw(private, number)
            if card is None:
                break
            hand.append(card)

    def _sync_player_hand(self, public, private):
        if public['player'] is not None:
            public['player']['hand'] = [card_name(card) for card in private['hands'].get('player', [])]

    # -- seating and dealing ------------------------------------------------
    def _join(self, action, revision, public, private):
        if public['player'] is None:
            found = _AMOUNT.search(action.casefold())
            if not found:
                raise NeedsRuling('How much gold do you bring to the table? Say it in your action, for '
                                  'example "I buy in with 20 gold." The strongest ante card sets each '
                                  'gambit\'s stakes (1 to 13 gp). No turn was committed.')
            amount = int(found.group(1))
            require(amount >= 1, 'A buy-in must be at least 1 gp')
            public['player'] = {'gp': amount, 'bought_in': amount, 'hand': [], 'watch_next_deal': False,
                                'unwelcome': False}
            text = f'You buy in with {amount} gp (your declared purse) at {public["name"]}.'
            if not re.search(r'\bdeal\b', action.casefold()):
                return text, []
            deal_text, reveals = self._deal(action, revision, public, private)
            return f'{text} {deal_text}', reveals
        return self._deal(action, revision, public, private)

    def _watch(self, action, revision, public, private):
        public['player']['watch_next_deal'] = True
        if public['gambit'] and public['gambit']['phase'] in ('ante', 'play'):
            return 'You settle your eyes on the dealer\'s hands for the next deal.', []
        return self._deal(action, revision, public, private)

    def _deal(self, action, revision, public, private):
        player = public['player']
        require(player is not None, 'Buy in before the deal')
        if player['unwelcome']:
            raise NeedsRuling('The table will not deal you in after you were caught. No turn was committed.',
                              attempt=True)
        require(not (public['gambit'] and public['gambit']['phase'] in ('ante', 'play')),
                'A gambit is already in play')
        if player['gp'] < 1:
            raise NeedsRuling('You have no gold left to ante. No turn was committed.', attempt=True)
        number = public['gambits_played'] + 1
        if private['deck'] is None:
            private['deck'] = [[color, value] for color in COLORS for value in DECK[color]]
            _rng(self.seed, 'deck').shuffle(private['deck'])
        dealer = self.config['cheat']['actor']
        seats = [seat for seat in seat_order(self.config) if self._gp(public, seat) > 0]
        # Deal one card at a time around the table until everyone holds six. The marked
        # deck: the dealer reads the backs and, when the second card is stronger than the
        # top one, deals himself the second (dealing seconds).
        cheated = False
        need = {seat: max(0, HAND_SIZE - len(private['hands'].get(seat, []))) for seat in seats}
        while any(need.values()):
            for seat in seats:
                if not need[seat]:
                    continue
                if not private['deck']:
                    self._draw(private, number)  # reshuffles the discard in
                deck = private['deck']
                if not deck:
                    need[seat] = 0
                    continue
                take = 0
                if seat == dealer and len(deck) > 1 and strength(deck[1]) > strength(deck[0]):
                    take, cheated = 1, True
                private['hands'].setdefault(seat, []).append(deck.pop(take))
                need[seat] -= 1
        private['cheated'] = cheated
        private['snapshot'] = {'stacks': dict(public['stacks']), 'player_gp': player['gp'],
                               'carried': public['carried']}
        watched = player['watch_next_deal']
        player['watch_next_deal'] = False
        detection, reveals = None, []
        if watched:
            result = self._contest('perception', 'watch', action, revision, 'watch')
            caught = cheated and result['success']
            detection = {'skill': 'Perception', 'die': result['die'], 'modifier': result['modifier'],
                         'total': result['total'], 'dc': result['dc'], 'auto': result['auto'],
                         'success': result['success'], 'caught': caught}
            if caught:
                reveals.append(self.config['cheat']['reveals_fact'])
        public['gambit'] = {
            'number': number, 'phase': 'ante', 'seats': seats, 'out': [], 'stakes': public['carried'],
            'ante_cards': {}, 'ante_amount': None, 'leader': None, 'round': 0, 'round_cards': [],
            'flights': {seat: [] for seat in seats}, 'plays': [], 'to_act': 'player', 'last_round': None,
            'cheat_seen': bool(detection and detection['caught']), 'read': None, 'swapped': False,
        }
        public['carried'] = 0
        private['cheat_log'].append({'gambit': number, 'cheated': cheated, 'detection': detection})
        private['cheat_log'] = private['cheat_log'][-8:]
        self._sync_player_hand(public, private)
        lines = [f'Gambit {number}: the dealer deals everyone up to six cards. Your hand: '
                 f'{", ".join(player["hand"])}.']
        if detection:
            outcome = (self.config['cheat']['caught_text'] if detection['caught'] else
                       'Nothing about the deal looks wrong to you.')
            self._note('Perception', detection)
            # The catch is told as prose, first, not buried in the dealing log (call 4).
            lines.insert(0, outcome)
        return ' '.join(lines), reveals

    # -- the ante -------------------------------------------------------------
    def _npc_ante(self, seat, private):
        hand = sorted((tuple(card) for card in private['hands'][seat]), key=strength)
        if seat == self.config['cheat']['actor']:
            # The marks tell him your hand: when his best three beat yours he antes high to
            # lead and to raise the stakes; otherwise he antes his weakest card.
            mine = flight_total(hand[-3:])
            yours = flight_total(sorted((tuple(c) for c in private['hands']['player']), key=strength)[-3:]) \
                if private['hands'].get('player') else 0
            return hand[-1] if mine > yours else hand[0]
        return hand[len(hand) // 2 - 1]

    def _ante(self, action, revision, public, private):
        gambit = public['gambit']
        require(gambit['phase'] == 'ante', 'The ante is already made')
        card = self._named_card(action, private, phase='ante')
        lines = []
        antes = {}
        for seat in gambit['seats']:
            chosen = card if seat == 'player' else self._npc_ante(seat, private)
            private['hands'][seat].remove(list(chosen))
            antes[seat] = list(chosen)
        amount = max(strength(c) for c in antes.values())
        top = [seat for seat in gambit['seats'] if strength(antes[seat]) == amount]
        gambit['ante_cards'] = {seat: card_name(c) for seat, c in antes.items()}
        gambit['antes_revealed'] = dict(gambit['ante_cards'])  # ante_cards shrinks as powers take them
        private['ante_cards'] = antes
        gambit['ante_amount'] = amount
        paid = {seat: self._pay(public, seat, 'stakes', amount) for seat in gambit['seats']}
        gambit['leader'] = top[0]  # ties: the tied player nearest the dealer's left
        gambit['phase'] = 'play'
        gambit['round'] = 1
        shown = ', '.join(f'{self.labels[seat]} {gambit["ante_cards"][seat]}' for seat in gambit['seats'])
        short = [self.labels[seat] for seat in gambit['seats'] if paid[seat] < amount]
        lines.append(f'Antes: {shown}. Stakes {amount} gp each'
                     f'{" (" + ", ".join(short) + " all in)" if short else ""}; the stakes hold '
                     f'{gambit["stakes"]} gp. {self.labels[gambit["leader"]]} lead'
                     f'{"" if gambit["leader"] == "player" else "s"}.')
        lines.append(self._advance(public, private))
        return ' '.join(line for line in lines if line), []

    # -- playing into the flight ----------------------------------------------
    def _named_card(self, action, private, phase='play'):
        """The card the player named, else a sensible default (table call 7: a bare "I play"
        never stalls on a sub-choice the player was not asked for): the weakest card to
        ante, the strongest to play into the flight."""
        hand = [tuple(card) for card in private['hands']['player']]
        card = parse_card(action, hand)
        if card is None:
            card = min(hand, key=strength) if phase == 'ante' else max(hand, key=strength)
        return card

    def _play(self, action, revision, public, private):
        gambit = public['gambit']
        require(gambit['phase'] == 'play' and gambit['to_act'] == 'player', 'It is not your turn to play')
        card = self._named_card(action, private)
        lines = [self._place(public, private, 'player', card)]
        lines.append(self._advance(public, private, after='player'))
        return ' '.join(line for line in lines if line), []

    def _npc_card(self, seat, public, private):
        hand = [tuple(card) for card in private['hands'][seat]]
        flight = [tuple(card) for card in private.get('flights', {}).get(seat, [])]
        # Finish a color flight when it can; otherwise play the strongest card.
        for color in COLORS:
            if sum(1 for c in flight if c[0] == color) == 2:
                matching = [c for c in hand if c[0] == color]
                if matching:
                    return max(matching, key=strength)
        return max(hand, key=strength)

    def _place(self, public, private, seat, card):
        gambit = public['gambit']
        private['hands'][seat].remove(list(card))
        flights = private.setdefault('flights', {})
        flights.setdefault(seat, []).append(list(card))
        gambit['flights'][seat].append(card_name(card))
        previous = gambit['round_cards'][-1] if gambit['round_cards'] else None
        gambit['round_cards'].append([seat, card_name(card)])
        who = self.labels[seat]
        text = f'{who} play{"" if seat == "player" else "s"} {card_name(card)}'
        triggered = previous is None or strength(card) <= _parse_name(previous[1])[1]
        gambit['plays'].append([seat, card_name(card), gambit['round'], triggered])
        if triggered:
            text += f' ({self._power(public, private, seat, card)})'
        text += self._special_flight(public, private, seat, card)
        return text + '.'

    def _pays(self, seat):
        return 'you pay' if seat == 'player' else f'{self.labels[seat]} pays'

    def _others(self, public, seat):
        gambit = public['gambit']
        return [s for s in gambit['seats'] if s != seat and s not in gambit['out']]

    def _power(self, public, private, seat, card):
        gambit = public['gambit']
        color = card[0]
        number = gambit['number']
        totals = {s: flight_total(private['flights'].get(s, [])) for s in gambit['seats']
                  if s not in gambit['out']}
        others = self._others(public, seat)
        if color == 'red' and others:
            target = max(others, key=lambda s: totals[s])
            moved = self._pay(public, target, seat, 1)
            return f'red: {self._pays(target)} {moved} gp'
        if color == 'blue':
            moved = sum(self._pay(public, s, 'stakes', 1) for s in others)
            return f'blue: the others pay {moved} gp into the stakes'
        if color == 'green' and others:
            order = order_from(self.config, seat)[1:]
            target = next(s for s in order if s in others)
            moved = self._pay(public, target, seat, 1)
            return f'green: {self._pays(target)} {moved} gp'
        if color == 'black':
            moved = self._pay(public, 'stakes', seat, 2)
            return f'black: takes {moved} gp from the stakes'
        if color == 'white':
            target = min(totals, key=lambda s: totals[s])
            moved = self._pay(public, target, 'stakes', 1)
            return f'white: {self._pays(target)} {moved} gp into the stakes'
        if color == 'gold':
            self._give(private, seat, 2, number)
            return 'gold: draws 2 cards'
        if color == 'silver':
            for s in [seat] + others:
                self._give(private, s, 1, number)
            return 'silver: every player draws a card'
        if color == 'bronze':
            antes = private.get('ante_cards', {})
            if antes and len(private['hands'][seat]) < HAND_LIMIT:
                owner = min(antes, key=lambda s: strength(antes[s]))
                private['hands'][seat].append(antes.pop(owner))
                gambit['ante_cards'].pop(owner, None)
                return 'bronze: takes the weakest ante card'
            return 'bronze: no ante card to take'
        if color == 'brass':
            self._give(private, seat, 1, number)
            return 'brass: draws a card'
        if color == 'copper':
            hand = private['hands'][seat]
            if hand:
                weakest = min(hand, key=strength)
                hand.remove(weakest)
                private['discard'].append(weakest)
            self._give(private, seat, 2, number)
            return 'copper: discards a card and draws 2'
        return f'{color}: no one to pay'

    def _special_flight(self, public, private, seat, card):
        flight = [tuple(c) for c in private['flights'][seat]]
        text = ''
        same_color = sorted((c for c in flight if c[0] == card[0]), key=strength, reverse=True)
        if len(same_color) == 3:
            value = strength(same_color[1])
            moved = sum(self._pay(public, other, seat, value) for other in self._others(public, seat))
            text += f'; color flight: the others pay {moved} gp'
        if sum(1 for c in flight if strength(c) == strength(card)) == 3:
            moved = self._pay(public, 'stakes', seat, strength(card))
            antes = private.get('ante_cards', {})
            taken = 0
            for owner in sorted(antes, key=lambda s: -strength(antes[s]))[:2]:
                if len(private['hands'][seat]) < HAND_LIMIT:
                    private['hands'][seat].append(antes.pop(owner))
                    public['gambit']['ante_cards'].pop(owner, None)
                    taken += 1
            text += f'; strength flight: takes {moved} gp from the stakes and {taken} ante cards'
        return text

    def _advance(self, public, private, after=None):
        """Play NPC cards until the player must act or the gambit ends."""
        gambit = public['gambit']
        lines = []
        while gambit['phase'] == 'play':
            active = [s for s in gambit['seats'] if s not in gambit['out']]
            played = [seat for seat, _ in gambit['round_cards']]
            turn = [s for s in order_from(self.config, gambit['leader']) if s in active]
            pending = [s for s in turn if s not in played]
            if not pending:
                # Round over: its strongest card leads the next.
                best = max(gambit['round_cards'], key=lambda item: _parse_name(item[1])[1])
                gambit['last_round'] = {'round': gambit['round'], 'strongest': self.labels[best[0]]}
                lines.append(f'Round {gambit["round"]} goes to {self.labels[best[0]]}.')
                gambit['round_cards'] = []
                gambit['leader'] = best[0] if best[0] in active else turn[0]
                if gambit['round'] >= ROUNDS:
                    lines.append(self._showdown(public, private))
                    break
                gambit['round'] += 1
                continue
            seat = pending[0]
            if not private['hands'].get(seat):
                gambit['out'].append(seat)  # an empty hand drops out of the gambit
                continue
            if seat == 'player':
                gambit['to_act'] = 'player'
                lines.append(f'Round {gambit["round"]}: your play. Your hand: '
                             f'{", ".join(card_name(c) for c in private["hands"]["player"])}.')
                return ' '.join(lines)
            lines.append(self._place(public, private, seat, self._npc_card(seat, public, private)))
        gambit['to_act'] = None
        return ' '.join(lines)

    def _showdown(self, public, private):
        gambit = public['gambit']
        active = [s for s in gambit['seats'] if s not in gambit['out']]
        totals = {s: flight_total(private['flights'].get(s, [])) for s in active}
        best = max(totals.values())
        winners = [s for s in active if totals[s] == best]
        share, remainder = divmod(gambit['stakes'], len(winners))
        for seat in winners:
            self._add(public, seat, share)
        shown = '; '.join(f'{self.labels[s]} {totals[s]}' for s in active)
        result = {'gambit': gambit['number'], 'flights': {self.labels[s]: totals[s] for s in active},
                  'winners': [self.labels[s] for s in winners], 'stakes': gambit['stakes'],
                  'share': share, 'carried': remainder}
        if public['player'] is not None:
            result['your_gp'] = public['player']['gp']
            result['net_since_buy_in'] = public['player']['gp'] - public['player']['bought_in']
        self._close(public, private, carried=remainder)
        public['last_result'] = result
        who = ' and '.join(result['winners'])
        tail = f' You now hold {result["your_gp"]} gp.' if 'your_gp' in result else ''
        return (f'Flights: {shown}. {who} take{"" if who == "You" else "s"} {share} gp'
                f'{f" ({remainder} gp carries)" if remainder else ""}.{tail}')

    def _close(self, public, private, carried):
        gambit = public['gambit']
        for cards in list(private.get('flights', {}).values()) + list(private.get('ante_cards', {}).values()):
            if cards and isinstance(cards[0], list):
                private['discard'].extend(cards)
            elif cards:
                private['discard'].append(cards)
        private['flights'] = {}
        private['ante_cards'] = {}
        gambit['phase'] = 'done'
        gambit['stakes'] = 0
        gambit['to_act'] = None
        public['carried'] = carried
        public['gambits_played'] = gambit['number']

    # -- reading, counter-cheating, accusing, leaving --------------------------
    def _read(self, action, revision, public, private):
        gambit = public['gambit']
        result = self._contest('insight', 'read', action, revision, 'read')
        if result['success']:
            seen = ('He plays like a man who already knows what you are holding.' if private['cheated']
                    else 'He is playing it straight this gambit, and he does not love his cards.')
        else:
            seen = 'He gives you nothing to read.'
        gambit['read'] = seen
        self._note('Insight', result)
        return seen, []

    def _swap(self, action, revision, public, private):
        gambit = public['gambit']
        require(not gambit['swapped'], 'You already worked a card this gambit')
        result = self._contest('sleight_of_hand', 'swap', action, revision, 'swap', passive_counts=False)
        gambit['swapped'] = True
        hand = private['hands']['player']
        if result['success']:
            fresh = self._draw(private, gambit['number'])
            lowest = min(hand, key=strength)
            hand[hand.index(lowest)] = fresh
            private['discard'].append(lowest)
            self._note('Sleight of Hand', result, 'passive Perception')
            return (f'Your {card_name(lowest)} goes up your sleeve and the {card_name(fresh)} comes off '
                    'the deck unseen.'), []
        public['player']['unwelcome'] = True
        public['table_mood'] = 'hostile: caught you cheating'
        gambit['out'].append('player')
        private['discard'].extend(private['hands'].pop('player', []))
        self._note('Sleight of Hand', result, 'passive Perception')
        lead = ('The dealer\'s hand closes over your wrist before the card clears your cuff. You are out '
                'of the gambit, your gold stays in the stakes, and nobody will deal to you now.')
        rest = self._advance(public, private) if gambit['phase'] == 'play' else self._finish_ante_out(public, private)
        return f'{lead} {rest}'.strip(), []

    def _finish_ante_out(self, public, private):
        """The player dropped out before anteing: the others ante and play it out."""
        gambit = public['gambit']
        gambit['seats'] = [s for s in gambit['seats'] if s != 'player']
        gambit['out'] = [s for s in gambit['out'] if s != 'player']
        gambit['flights'].pop('player', None)
        if len(gambit['seats']) < 2:
            self._close(public, private, carried=gambit['stakes'])
            return ''
        antes = {seat: list(self._npc_ante(seat, private)) for seat in gambit['seats']}
        for seat, card in antes.items():
            private['hands'][seat].remove(card)
        private['ante_cards'] = antes
        gambit['ante_cards'] = {seat: card_name(c) for seat, c in antes.items()}
        amount = max(strength(c) for c in antes.values())
        gambit['ante_amount'] = amount
        for seat in gambit['seats']:
            self._pay(public, seat, 'stakes', amount)
        gambit['leader'] = next(s for s in gambit['seats'] if strength(antes[s]) == amount)
        gambit['phase'], gambit['round'] = 'play', 1
        return self._advance(public, private)

    def _accuse(self, action, revision, public, private):
        gambit = public['gambit']
        seen = bool(gambit and gambit.get('cheat_seen'))
        record = public.setdefault('accusations', [])
        if seen and gambit['phase'] in ('ante', 'play'):
            # Proof in the open: the gambit is void and all gold goes back to where it
            # stood at the deal. The dealer, true to the source, blames someone else.
            snapshot = private['snapshot']
            public['stacks'] = dict(snapshot['stacks'])
            public['player']['gp'] = snapshot['player_gp']
            gambit['stakes'] = 0
            self._close(public, private, carried=snapshot['carried'])
            public['table_mood'] = 'tense: accused with proof'
            record.append({'gambit': gambit['number'], 'backed': True})
            return ('The gambit is void: every coin goes back to where it stood before the deal. You saw '
                    'the deal, and the whole table knows you saw it. The dealer does not confess.'), []
        public['table_mood'] = 'tense: accused without proof'
        record.append({'gambit': gambit['number'] if gambit else None, 'backed': False})
        return ('Nothing on the table proves it. The game stops while every face at the table turns '
                'to you.'), []

    def _leave(self, action, revision, public, private):
        player = public['player']
        lead = ''
        gambit = public['gambit']
        if gambit and gambit['phase'] in ('ante', 'play') and 'player' not in gambit['out']:
            # Leaving mid-gambit forfeits it: the others play it out, so the table never
            # waits on an empty seat and the stakes have an owner.
            private['discard'].extend(private['hands'].pop('player', []))
            if gambit['phase'] == 'play':
                gambit['out'].append('player')
                rest = self._advance(public, private)
            else:
                rest = self._finish_ante_out(public, private)
            lead = f'You drop out of the gambit. {rest} '
        net = player['gp'] - player['bought_in']
        private['discard'].extend(private['hands'].pop('player', []))
        public['last_result'] = {**(public['last_result'] or {}), 'left_table': True,
                                 'your_gp': player['gp'], 'net_since_buy_in': net}
        public['player'] = None
        return (f'{lead}You gather your {player["gp"]} gp and leave the game '
                f'({"up" if net >= 0 else "down"} {abs(net)} gp on your {player["bought_in"]} gp buy-in).'), []


def table_gold(public):
    """All gold the game holds: seat stacks, the player's table purse, the stakes, and
    any odd gold carried to the next gambit."""
    gambit = public.get('gambit') or {}
    return (sum(public['stacks'].values()) + (public['player']['gp'] if public['player'] else 0) +
            gambit.get('stakes', 0) + public.get('carried', 0))


def _tda_public_view(config, public):
    """The player-visible half with every seat under its public label. Seat keys are DM
    actor ids (one of them names a hidden identity), so they never leave the DM side."""
    labels = {**config.get('labels', {}), 'player': 'you'}

    def label(seat):
        return labels.get(seat, seat)
    view = copy.deepcopy(public)
    # The rules and powers are the module's, the same every turn: shown, never stored.
    view['rules'], view['powers'] = list(RULES), dict(POWERS)
    view['stacks'] = {label(seat): gp for seat, gp in view.get('stacks', {}).items()}
    gambit = view.get('gambit')
    if gambit:
        for key in ('ante_cards', 'antes_revealed', 'flights'):
            gambit[key] = {label(seat): value for seat, value in gambit.get(key, {}).items()}
        for key in ('seats', 'out'):
            gambit[key] = [label(seat) for seat in gambit.get(key, [])]
        gambit['round_cards'] = [[label(seat), name] for seat, name in gambit.get('round_cards', [])]
        gambit['plays'] = [[label(seat), *rest] for seat, *rest in gambit.get('plays', [])]
        for key in ('leader', 'to_act'):
            if gambit.get(key):
                gambit[key] = label(gambit[key])
    return view


def declared_procedures(state):
    return sorted((state or {}).get('procedures', {}))


def _tda_check_config(config):
    for key in ('name', 'dm_choice', 'unit', 'seats', 'cheat', 'labels'):
        require(key in config, f'Card procedure config needs {key}')
    for key in ('actor', 'sleight_bonus', 'deception_bonus', 'passive_perception', 'reveals_fact',
                'caught_text'):
        require(key in config['cheat'], f'Card procedure cheat config needs {key}')
    if not all(actor in config['labels'] for actor in config['seats']):
        raise InvalidChange('Every seat needs a public label')
    require(config['cheat']['actor'] in config['seats'], 'The dealer must hold a seat')


# ---------------------------------------------------------------------------
# One entry point per table game. A card procedure's config names its ``game``
# (default Three-Dragon Ante); twenty-one lives in runtime/kit_twenty_one.py.
# ---------------------------------------------------------------------------
def _twenty_one():
    from . import kit_twenty_one  # local import: kit_twenty_one imports this module
    return kit_twenty_one


def game_of(config_or_public):
    return (config_or_public or {}).get('game') or 'three_dragon_ante'


def initial_state(config):
    return _twenty_one().initial_state(config) if game_of(config) == 'twenty_one' else _tda_initial_state(config)


def check_config(config):
    return _twenty_one().check_config(config) if game_of(config) == 'twenty_one' else _tda_check_config(config)


def card_intent(action, procedure_state):
    if procedure_state is None:
        return None
    if game_of(procedure_state.get('public')) == 'twenty_one':
        return _twenty_one().card_intent(action, procedure_state)
    return _tda_intent(action, procedure_state)


def public_view(config, public):
    if game_of(public) == 'twenty_one' or game_of(config) == 'twenty_one':
        return _twenty_one().public_view(config, public)
    return _tda_public_view(config, public)


def engine_for(procedure_id, config, modifiers, seed, passives=None, dcs=None):
    if game_of(config) == 'twenty_one':
        return _twenty_one().TwentyOneTable(procedure_id, config, modifiers, seed, passives=passives, dcs=dcs)
    return CardTable(procedure_id, config, modifiers, seed, passives=passives, dcs=dcs)


def rule_terms(configs):
    """The running games' own words, for the rules-statement guard."""
    terms = set()
    for config in configs:
        terms |= set(_twenty_one().GAME_TERMS if game_of(config) == 'twenty_one' else RULE_TERMS)
    return tuple(sorted(terms))


def offered(source):
    """Card procedures this room offers as playable (``offered`` false keeps a game's
    engine available without offering it here)."""
    return tuple(key for key, config in ((source or {}).get('procedures') or {}).items()
                 if not key.startswith('_') and isinstance(config, dict) and config.get('offered', True))


def can_carry(config, item):
    """True when the procedure can pay out a stake of this kind (gold always)."""
    return item == 'gold' or item in ((config or {}).get('carries') or ())


def is_live(public):
    """A round or gambit is in progress."""
    gambit = (public or {}).get('gambit') or (public or {}).get('round')
    return bool(gambit and gambit.get('phase') in ('ante', 'play'))


def card_words():
    """Words a hand or table reminder is made of (exempt from the padding guard)."""
    tw = _twenty_one()
    return tuple(COLORS) + tuple(tw.RANKS) + tuple(tw.SUITS) + (
        'dragon', 'dragons', 'card', 'cards', 'hand', 'your', 'ace', 'aces', 'jack', 'queen', 'king', 'shows',
        'showing', 'holds', 'hold', 'stakes', 'flight', 'round', 'dealer')

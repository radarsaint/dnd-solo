"""Gravedigger: a playable card game and wager procedure for the area 6c card table.

Why this exists (tests/playtests/2026-09-29-area-06c-voice-spec-nik.md): the source
says Uktarl and three companions play cards with a marked deck he carries and that
each has coins on the table. It names no game, rules, or stakes. In play the host
made up "high card, a matching coin" in a private plan and it was spoken as room
canon, and nothing could actually deal a hand, let Uktarl use his deck, let the
player catch him, or pay anybody out.

This module is that missing machinery. Everything in it is a DECLARED DM CHOICE
(see DM_CHOICES), not an adventure fact:

- The game. Gravedigger is an original draw-and-bluff game written for this table.
  It is not from the adventure and not a published D&D game.
- The stakes. The ante and bet limits are DM choices; the money on the table is the
  source's own coins (85 gp in the hidden count), split between the four seats by the DM.
- The cheating. Uktarl reads the marks on the card backs while he deals (so he knows
  every hand and the next few cards of the stock) and slips himself a better card
  when one is near the top. He rolls Dexterity (Sleight of Hand) to hide it. The
  player's Perception (passive, or an active roll when they say they watch the deal)
  is contested against that roll. A challenge that is not backed by a sighting is
  Wisdom (Insight) against his Charisma (Deception).

Everything is deterministic from the session's roll seed and the hand number, so a
retried turn deals the same cards and rolls the same dice. The player's own d20 can
be supplied for their checks (player-supplied rolls).

The module imports nothing from kit_agent. It is a pure procedure: it takes the
current game state and one move, and returns the next state and a public result.
"""
import copy
import hashlib
import random
import re

from .state_context import InvalidChange, require

GAME_ID = 'gravedigger'
GAME_NAME = 'Gravedigger'
SUITS = ('Bones', 'Candles', 'Crowns', 'Spades')
RANKS = tuple(range(1, 10))
HAND_SIZE = 3
ANTE_GP = 2
BET_MIN_GP = 1
BET_MAX_GP = 10
FULL_GRAVE_VALUE = 25        # three cards of one rank beat any suit total (max 24)
HISTORY_LIMIT = 6

# How the NPCs play. Simple, visible policies so the table behaves the same way every
# time and a watchful player can learn it.
COMPANION_SWAP_BELOW = 12    # a companion swaps their weakest card below this value
COMPANION_STAY_VALUE = 12    # ...stays in on a check at or above it
COMPANION_CALL_VALUE = 15    # ...calls a bet at or above it
DEALER_READ_DEPTH = 3        # stock cards whose marks Uktarl can read while dealing
DEALER_BET_MIN_GP = 3        # his bet into a check he knows he wins
HONEST_DEALER_BET_VALUE = 18  # once exposed he plays blind: bets only on a strong hand
HONEST_DEALER_CALL_VALUE = 15

# DM choices for his checks. The room rules give only Performance +4 and say he
# "lies and cheats for fun"; these come from the bandit captain statistics the room
# names (Dexterity 16, Deception +4).
DEALER_SLEIGHT_MOD = 3
DEALER_DECEPTION_MOD = 4
PASSIVE_BASE = 10

SEATS = ('player', 'bandit_a', 'bandit_b', 'doppelganger', 'uktarl')
NPC_SEATS = SEATS[1:]
# DM split of the hidden table count (85 gp; the copper and silver stay out of the game).
STARTING_STACKS_GP = {'bandit_a': 18, 'bandit_b': 20, 'doppelganger': 16, 'uktarl': 31}
SEAT_NAMES = {'player': 'you', 'uktarl': 'the dealer', 'bandit_a': 'the door-side player',
              'bandit_b': 'the fresco-side player', 'doppelganger': 'the fourth player'}
EVENT_MAX_CHARS = 500

# One declared DM choice, stated once for the private stage (and in the docs).
DM_CHOICES = (
    f'{GAME_NAME}, stakes, and NPC stacks (a split of the table coins) are the DM\'s choice; the '
    f'adventure names no game. The dealer reads the marked backs and slips himself better cards: '
    f'Sleight of Hand +{DEALER_SLEIGHT_MOD} vs Perception; a blind challenge is Insight vs '
    f'Deception +{DEALER_DECEPTION_MOD}.'
)

PUBLIC_RULES = (
    f'Ante {ANTE_GP} gp; three cards each from a 36-card deck (ranks 1-9; Bones, Candles, Crowns, '
    f'Spades). A hand is worth its best single suit\'s total; three of a rank (a full grave) is '
    f'{FULL_GRAVE_VALUE}, the best. Each player keeps or swaps one card from the stock, then one '
    f'betting round: check or bet {BET_MIN_GP}-{BET_MAX_GP} gp, called or folded; the dealer may '
    'bet once into a check. Best hand still in takes the pot; ties split.'
)

# Moves the host can pass (CLI --game-move), by phase.
MOVES_BY_PHASE = {
    'idle': ('join', 'join watch'),
    'left': ('join', 'join watch'),
    'between_hands': ('deal', 'deal watch', 'leave'),
    'draw': ('keep', 'swap 1', 'swap 2', 'swap 3', 'fold', 'challenge'),
    'bet': ('check', f'bet {BET_MIN_GP}-{BET_MAX_GP}', 'fold', 'challenge'),
    'answer_raise': ('call', 'fold', 'challenge'),
}
IN_HAND_PHASES = ('draw', 'bet', 'answer_raise')
MOVE_PATTERN = re.compile(r'^\s*(join|deal|keep|swap|check|bet|call|fold|challenge|leave)'
                          r'(?:\s+(watch|\d+))?\s*$', re.I)

# Player words that mean a game move. When a hand is being played (or the player
# accepts a seat) the host must pass the move, so no one pretends to play in prose.
GAME_MOVE_WORDS = re.compile(
    r"\b(fold|folds|i check|check\b(?! (the|his|her|their|for|if|out))|i call|call(ing)? (it|the bet|your bet)|"
    r"i bet|bet \d+|raise|swap|i keep|keep (them|my cards|these)|deal me in|deal me another|"
    r"another hand|i'?m in\b|count me in|i ante|ante up|i('ll| will) play|let'?s play|i join)\b", re.I)
SEAT_WORDS = re.compile(r"\b(deal me in|i'?m in\b|count me in|i ante|ante up|i('ll| will) play|"
                        r"let'?s play|i join|take a hand|sit in)\b", re.I)


class MissingInput(InvalidChange):
    """A host input problem (a modifier, the purse, or a move that is not legal now).
    Not an in-fiction attempt: nothing is recorded."""



def fresh_state():
    return {'game': GAME_ID, 'phase': 'idle', 'hand_no': 0, 'player': None,
            'stacks_gp': dict(STARTING_STACKS_GP), 'pot_gp': 0, 'contributions': {},
            'hands': {}, 'stock': [], 'in_hand': [], 'to_call_gp': 0,
            'dealer_status': 'reading_backs', 'this_hand': None, 'history': [],
            'accusations_failed': 0}


def card_text(card):
    return f'{card[0]} of {card[1]}'


def hand_value(cards):
    ranks = [card[0] for card in cards]
    if len(cards) == HAND_SIZE and len(set(ranks)) == 1:
        return FULL_GRAVE_VALUE
    return max(sum(card[0] for card in cards if card[1] == suit) for suit in SUITS)


def best_suit(cards):
    if hand_value(cards) == FULL_GRAVE_VALUE:
        return 'full grave'
    return max(SUITS, key=lambda suit: sum(card[0] for card in cards if card[1] == suit))


def hand_text(cards):
    value = hand_value(cards)
    shape = 'a full grave' if value == FULL_GRAVE_VALUE else f'{value} in {best_suit(cards)}'
    return f'{", ".join(card_text(card) for card in cards)} ({shape})'


def parse_move(text):
    """('join', 'watch') / ('swap', 2) / ('bet', 5) / ('check', None) ..."""
    found = MOVE_PATTERN.match(text or '')
    require(found is not None, f'Unknown game move {text!r}. Moves: join [watch], deal [watch], '
            'keep, swap 1-3, check, bet N, call, fold, challenge, leave.')
    verb, arg = found.group(1).lower(), found.group(2)
    if verb in ('join', 'deal'):
        require(arg in (None, 'watch'), f'{verb} takes only "watch"')
        return verb, arg == 'watch'
    if verb == 'swap':
        require(arg is not None and arg.isdigit() and 1 <= int(arg) <= HAND_SIZE,
                f'swap needs a card position 1-{HAND_SIZE}')
        return verb, int(arg)
    if verb == 'bet':
        require(arg is not None and arg.isdigit() and BET_MIN_GP <= int(arg) <= BET_MAX_GP,
                f'bet needs an amount from {BET_MIN_GP} to {BET_MAX_GP} gp')
        return verb, int(arg)
    require(arg is None, f'{verb} takes no argument')
    return verb, None


def _stream(seed, hand_no, label):
    return int.from_bytes(hashlib.sha256(f'{seed}:{GAME_ID}:{hand_no}:{label}'.encode()).digest()[:8], 'big')


def _d20(seed, hand_no, label):
    return _stream(seed, hand_no, label) % 20 + 1


def _gold_total(game):
    purse = (game.get('player') or {}).get('purse_gp', 0)
    return purse + sum(game['stacks_gp'].values()) + game['pot_gp']


class Move:
    """What one adjudicated move produced: next state, public text, facts revealed."""
    def __init__(self, state, public, reveals=(), evidence=''):
        self.state, self.public, self.reveals, self.evidence = state, public, list(reveals), evidence


class TableGame:
    """One move of Gravedigger. `roll` is the player's own d20 for an active check
    (a callable or None); without it the check is seeded like every other roll."""

    def __init__(self, state, seed, perception=None, insight=None, purse_gp=None, roll=None,
                 known_facts=()):
        self.game = copy.deepcopy(state) if state else fresh_state()
        self.seed = seed
        self.perception, self.insight, self.purse_gp = perception, insight, purse_gp
        self.roll = roll
        self.known = set(known_facts)
        self.lines = []
        self.reveals = []
        self.evidence = []

    # -- helpers -----------------------------------------------------------
    def _player_d20(self, label):
        if self.roll:
            die = self.roll()
            require(type(die) is int and 1 <= die <= 20, 'Invalid d20 roll')
            return die, 'player roll'
        return _d20(self.seed, self.game['hand_no'], label), 'seeded roll'

    def _modifier(self, name):
        given = getattr(self, name)
        stored = (self.game.get('player') or {}).get(name)
        value = given if given is not None else stored
        if value is None:
            raise MissingInput(f'Supply the character\'s {name.capitalize()} modifier with '
                               f'--{name} before this {GAME_NAME} move. No turn was committed.')
        if self.game.get('player') is not None:
            self.game['player'][name] = value
        return value

    def _pay(self, seat, amount):
        game = self.game
        if seat == 'player':
            require(game['player']['purse_gp'] >= amount, 'Not enough gold in the purse')
            game['player']['purse_gp'] -= amount
        else:
            require(game['stacks_gp'][seat] >= amount, 'NPC stack cannot cover the amount')
            game['stacks_gp'][seat] -= amount
        game['pot_gp'] += amount
        game['contributions'][seat] = game['contributions'].get(seat, 0) + amount

    def _can_pay(self, seat, amount):
        if seat == 'player':
            return self.game['player']['purse_gp'] >= amount
        return self.game['stacks_gp'][seat] >= amount

    def _value(self, seat):
        return hand_value(self.game['hands'][seat])

    def _drop(self, seat):
        if seat in self.game['in_hand']:
            self.game['in_hand'].remove(seat)

    # -- moves -------------------------------------------------------------
    def play(self, move_text):
        verb, arg = parse_move(move_text)
        phase = self.game['phase']
        allowed = {'join': ('idle', 'left'), 'deal': ('between_hands',), 'leave': ('between_hands',),
                   'keep': ('draw',), 'swap': ('draw',), 'check': ('bet',), 'bet': ('bet',),
                   'call': ('answer_raise',), 'fold': IN_HAND_PHASES, 'challenge': IN_HAND_PHASES}
        if phase not in allowed[verb]:
            raise MissingInput(f'{verb!r} is not a move right now ({GAME_NAME} phase: {phase}). '
                               f'Moves now: {", ".join(MOVES_BY_PHASE[phase])}. No turn was committed.')
        before = _gold_total(self.game) if self.game.get('player') else None
        getattr(self, f'_{verb}')(arg)
        if before is not None and verb != 'join':
            require(_gold_total(self.game) == before, 'Gold was created or lost by the game procedure')
        public = ' '.join(self.lines)
        require(len(public) <= EVENT_MAX_CHARS, 'Game result exceeds the event bound')
        return Move(self.game, public, self.reveals, ' '.join(self.evidence))

    def _join(self, watch):
        # A returning player brings back what they left with; a new one declares a purse.
        stored = (self.game.get('player') or {}).get('purse_gp')
        purse = stored if stored is not None else self.purse_gp
        if purse is None:
            raise MissingInput(f'The character sheet is not loaded: supply how much gold the character '
                               f'carries with --purse-gp before they join {GAME_NAME}. No turn was committed.')
        require(type(purse) is int and purse >= 0, 'Purse must be a whole number of gold pieces')
        if purse < ANTE_GP:
            raise MissingInput(f'The character has {purse} gp; the ante is {ANTE_GP} gp. No turn was committed.')
        previous = self.game.get('player') or {}
        self.game['player'] = {'purse_gp': purse, 'perception': previous.get('perception'),
                               'insight': previous.get('insight')}
        self._modifier('perception')
        if self.insight is not None:
            self.game['player']['insight'] = self.insight
        self.evidence.append(f'Player joined {GAME_NAME} with {purse} gp (host-declared purse).')
        self._start_hand(watch)

    def _deal(self, watch):
        if self.game['player']['purse_gp'] < ANTE_GP:
            raise MissingInput(f'The character has {self.game["player"]["purse_gp"]} gp, less than the '
                               f'{ANTE_GP} gp ante. No turn was committed.')
        self._start_hand(watch)

    def _leave(self, _):
        game = self.game
        game['phase'] = 'left'
        self.lines.append(f'You leave the {GAME_NAME} table with {game["player"]["purse_gp"]} gp.')
        self.evidence.append('Player left the table between hands.')

    def _start_hand(self, watch):
        game = self.game
        game['hand_no'] += 1
        hand_no = game['hand_no']
        game.update(pot_gp=0, contributions={}, hands={}, in_hand=[], to_call_gp=0)
        seated = [seat for seat in SEATS if self._can_pay(seat, ANTE_GP)]
        for seat in seated:
            self._pay(seat, ANTE_GP)
        deck = [[rank, suit] for suit in SUITS for rank in RANKS]
        random.Random(_stream(self.seed, hand_no, 'shuffle')).shuffle(deck)
        for _ in range(HAND_SIZE):
            for seat in seated:
                game['hands'].setdefault(seat, []).append(deck.pop(0))
        game['stock'] = deck
        game['in_hand'] = seated
        perception = self._modifier('perception')
        record = {'watch': bool(watch), 'dealer_read_backs': False, 'dealer_improved': False,
                  'sleight_total': None, 'notice_total': None, 'noticed': False}
        if game['dealer_status'] == 'reading_backs' and 'uktarl' in seated:
            record['dealer_read_backs'] = True
            record['dealer_improved'] = self._dealer_takes_a_better_card()
            sleight = _d20(self.seed, hand_no, 'sleight') + DEALER_SLEIGHT_MOD
            if watch:
                die, how = self._player_d20('watch')
                notice = die + perception
            else:
                notice, how = PASSIVE_BASE + perception, 'passive'
            # Reading the backs is only a glance; passive Perception can catch the
            # physical move of slipping a card, while watching the deal can catch either.
            catchable = watch or record['dealer_improved']
            record.update(sleight_total=sleight, notice_total=notice, notice_basis=how,
                          noticed=catchable and notice >= sleight)
        game['this_hand'] = record
        game['phase'] = 'draw'
        others = [SEAT_NAMES[seat] for seat in seated if seat != 'player']
        self.lines.append(f'{GAME_NAME}, hand {hand_no}: you and {len(others)} others ante {ANTE_GP} gp; '
                          f'the pot is {game["pot_gp"]} gp and you hold {game["player"]["purse_gp"]} gp. '
                          f'Your cards: {hand_text(game["hands"]["player"])}.')
        if record['noticed']:
            lead = (f'Watching his hands (Perception {record["notice_total"]})' if watch else
                    f'Something in his rhythm snags your eye (passive Perception {record["notice_total"]})')
            self.lines.append(f'{lead}: you catch the dealer reading the backs of the cards as he deals'
                              + (' and slipping himself one from below the top' if record['dealer_improved'] else '')
                              + '. The backs carry small marks.')
            if 'marked_deck' not in self.known:
                self.reveals.append('marked_deck')
        elif watch:
            self.lines.append(f'You watch the deal closely and see nothing out of place '
                              f'(Perception {record["notice_total"]}).')
        self.lines.append('Keep your cards or swap one (swap 1, 2, or 3).')
        self.evidence.append(f'Hand {hand_no} dealt; dealer record {record}.')

    def _dealer_takes_a_better_card(self):
        """He knows the next cards by their marks and deals himself the best one near the top."""
        game = self.game
        hand, stock = game['hands']['uktarl'], game['stock']
        best = (hand_value(hand), None, None)
        for index in range(min(DEALER_READ_DEPTH, len(stock))):
            for slot in range(HAND_SIZE):
                trial = hand[:slot] + [stock[index]] + hand[slot + 1:]
                if hand_value(trial) > best[0]:
                    best = (hand_value(trial), index, slot)
        _, index, slot = best
        if index is None:
            return False
        hand[slot], stock[index] = stock[index], hand[slot]
        return True

    def _best_swap(self, hand, card):
        """The slot whose replacement by `card` gives the best hand, and that value."""
        options = [(hand_value(hand[:slot] + [card] + hand[slot + 1:]), slot) for slot in range(HAND_SIZE)]
        return max(options)

    def _npc_draws(self):
        game = self.game
        notes = []
        for seat in NPC_SEATS:
            if seat not in game['in_hand'] or not game['stock']:
                continue
            hand = game['hands'][seat]
            top = game['stock'][0]
            value, slot = self._best_swap(hand, top)
            reads = seat == 'uktarl' and game['dealer_status'] == 'reading_backs'
            # The dealer knows the top card by its back; the others swap blind when weak.
            if (reads and value > hand_value(hand)) or (not reads and hand_value(hand) < COMPANION_SWAP_BELOW):
                if not reads:
                    slot = min(range(HAND_SIZE), key=lambda i: hand[i][0])
                hand[slot] = game['stock'].pop(0)
                notes.append(f'{SEAT_NAMES[seat]} swaps one')
        return notes

    def _keep(self, _):
        self.lines.append('You keep your cards.')
        self._after_draw()

    def _swap(self, position):
        game = self.game
        hand = game['hands']['player']
        old = hand[position - 1]
        hand[position - 1] = game['stock'].pop(0)
        self.lines.append(f'You swap the {card_text(old)} and draw the {card_text(hand[position - 1])}.')
        self._after_draw()

    def _after_draw(self):
        notes = self._npc_draws()
        self.lines.append(f'Your hand: {hand_text(self.game["hands"]["player"])}. '
                          + ((', '.join(notes).capitalize() + '. ') if notes else 'The others keep. ')
                          + f'Betting: check, or bet {BET_MIN_GP} to {BET_MAX_GP} gp.')
        self.game['phase'] = 'bet'

    def _check(self, _):
        game = self.game
        self.lines.append('You check.')
        for seat in ('bandit_a', 'bandit_b', 'doppelganger'):
            if seat in game['in_hand'] and self._value(seat) < COMPANION_STAY_VALUE:
                self._drop(seat)
                self.lines.append(f'{SEAT_NAMES[seat].capitalize()} folds.')
        if 'uktarl' in game['in_hand']:
            knows = game['dealer_status'] == 'reading_backs'
            his, yours = self._value('uktarl'), self._value('player')
            wants = his > yours if knows else his >= HONEST_DEALER_BET_VALUE
            amount = min(BET_MAX_GP, max(DEALER_BET_MIN_GP, game['pot_gp'] // 2),
                         game['stacks_gp']['uktarl'], game['player']['purse_gp'])
            if wants and amount > 0:
                self._pay('uktarl', amount)
                game['to_call_gp'] = amount
                self.lines.append(f'The dealer bets {amount} gp.')
                self._others_answer(amount)
                self.lines.append(f'The pot is {game["pot_gp"]} gp. Call {amount} gp or fold.')
                game['phase'] = 'answer_raise'
                return
            self.lines.append('The dealer checks.')
        self._showdown()

    def _others_answer(self, amount):
        game = self.game
        for seat in ('bandit_a', 'bandit_b', 'doppelganger'):
            if seat not in game['in_hand']:
                continue
            if self._value(seat) >= COMPANION_CALL_VALUE and self._can_pay(seat, amount):
                self._pay(seat, amount)
                self.lines.append(f'{SEAT_NAMES[seat].capitalize()} calls.')
            else:
                self._drop(seat)
                self.lines.append(f'{SEAT_NAMES[seat].capitalize()} folds.')

    def _bet(self, amount):
        game = self.game
        if game['player']['purse_gp'] < amount:
            raise MissingInput(f'The character holds {game["player"]["purse_gp"]} gp and cannot bet '
                               f'{amount}. No turn was committed.')
        self._pay('player', amount)
        self.lines.append(f'You bet {amount} gp.')
        self._others_answer_with_dealer(amount)
        self._showdown()

    def _others_answer_with_dealer(self, amount):
        game = self.game
        self._others_answer(amount)
        if 'uktarl' in game['in_hand']:
            knows = game['dealer_status'] == 'reading_backs'
            his, yours = self._value('uktarl'), self._value('player')
            calls = his >= yours if knows else his >= HONEST_DEALER_CALL_VALUE
            if calls and self._can_pay('uktarl', amount):
                self._pay('uktarl', amount)
                self.lines.append('The dealer calls.')
            else:
                self._drop('uktarl')
                self.lines.append('The dealer folds.')

    def _call(self, _):
        game = self.game
        amount = min(game['to_call_gp'], game['player']['purse_gp'])
        self._pay('player', amount)
        self.lines.append(f'You call {amount} gp.')
        self._showdown()

    def _fold(self, _):
        self._drop('player')
        self.lines.append(f'You fold; your {self.game["contributions"].get("player", 0)} gp stays in the pot.')
        self._showdown()

    def _challenge(self, _):
        game = self.game
        record = game['this_hand'] or {}
        if record.get('noticed'):
            self.lines.append('You call out the dealer\'s handling of the cards, and you saw it happen.')
            self._void_hand('upheld: the player saw the dealer read the backs')
            return
        insight = self._modifier('insight')
        die, how = self._player_d20('challenge')
        total = die + insight
        deception = _d20(self.seed, game['hand_no'], f'deception{game["accusations_failed"]}') + DEALER_DECEPTION_MOD
        cheating = record.get('dealer_read_backs', False)
        self.evidence.append(f'Challenge: Insight {total} ({how}) vs Deception {deception}; '
                             f'dealer reading backs this hand: {cheating}.')
        if cheating and total >= deception:
            self.lines.append(f'You challenge the deal and read the dealer as he answers (Insight {total}): '
                              'his eyes keep going to the backs of the cards, and the backs carry small marks.')
            if 'marked_deck' not in self.known:
                self.reveals.append('marked_deck')
            self._void_hand('upheld: Insight beat his Deception')
            return
        game['accusations_failed'] += 1
        self.lines.append(f'You challenge the deal (Insight {total}). Nothing you can point to backs it up; '
                          'the hand goes on.')
        self.lines.append(f'Moves: {", ".join(MOVES_BY_PHASE[game["phase"]])}.')

    def _void_hand(self, why):
        game = self.game
        for seat, amount in game['contributions'].items():
            if seat == 'player':
                game['player']['purse_gp'] += amount
            else:
                game['stacks_gp'][seat] += amount
        game.update(pot_gp=0, contributions={}, to_call_gp=0, phase='between_hands',
                    dealer_status='exposed')
        game['history'] = (game['history'] + [{'hand_no': game['hand_no'], 'result': 'void',
                                               'why': why, 'player_net_gp': 0}])[-HISTORY_LIMIT:]
        self.lines.append(f'The hand is void and every stake goes back; you hold '
                          f'{game["player"]["purse_gp"]} gp.')
        self.evidence.append(f'Hand {game["hand_no"]} voided ({why}).')

    def _showdown(self):
        game = self.game
        contenders = game['in_hand']
        values = {seat: self._value(seat) for seat in contenders}
        top = max(values.values())
        winners = [seat for seat in SEATS if values.get(seat) == top]
        share, remainder = divmod(game['pot_gp'], len(winners))
        pot = game['pot_gp']
        for index, seat in enumerate(winners):
            amount = share + (remainder if index == 0 else 0)
            if seat == 'player':
                game['player']['purse_gp'] += amount
            else:
                game['stacks_gp'][seat] += amount
        paid = game['contributions'].get('player', 0)
        won = sum(share + (remainder if i == 0 else 0) for i, s in enumerate(winners) if s == 'player')
        shown = [f'{SEAT_NAMES[seat]} {values[seat]}'
                 for seat in SEATS if seat in contenders]
        if len(contenders) > 1:
            self.lines.append('Showdown: ' + ', '.join(shown) + '.')
        names = ' and '.join('you' if seat == 'player' else SEAT_NAMES[seat] for seat in winners)
        verb = 'split' if len(winners) > 1 else ('take' if winners == ['player'] else 'takes')
        self.lines.append(f'{names[0].upper() + names[1:]} {verb} the {pot} gp pot; you hold '
                          f'{game["player"]["purse_gp"]} gp.')
        game['history'] = (game['history'] + [{
            'hand_no': game['hand_no'], 'result': 'showdown' if len(contenders) > 1 else 'uncontested',
            'winners': winners, 'pot_gp': pot, 'player_net_gp': won - paid,
            'shown': {seat: game['hands'][seat] for seat in contenders} if len(contenders) > 1 else {}}]
        )[-HISTORY_LIMIT:]
        game.update(pot_gp=0, contributions={}, to_call_gp=0, phase='between_hands')
        self.evidence.append(f'Hand {game["hand_no"]} paid out: winners {winners}, pot {pot} gp.')


def play(state, move_text, **kwargs):
    """Adjudicate one move. Returns a Move (next state, public text, reveals, evidence)."""
    return TableGame(state, **kwargs).play(move_text)


# ---------------------------------------------------------------------------
# Views. The public view is what the player can see at the table; the private view
# adds what only the DM knows (other hands, the dealer's reading of the backs, the
# rolls). The stock order is never shown to anyone.
# ---------------------------------------------------------------------------
OFFER_LIMITS = (f'{GAME_NAME} only, on these rules and amounts; no other game, prize, side bet, or '
                'house rule exists until the procedure supports it.')
HOST_HOW = ('To play, map the player\'s words to one move and pass it as game_move (CLI --game-move) '
            'with the player\'s own words as the action. Joining needs the character\'s gold '
            '(--purse-gp) and Perception modifier (--perception); a challenge needs Insight '
            '(--insight). A player who rolled their own d20 passes it with --roll. The procedure '
            'deals, rolls the dealer\'s checks, and pays out; the performance reacts to its result '
            'and never changes it.')


def _names(seats):
    return [SEAT_NAMES[seat] for seat in seats]


def public_view(state, known_facts=()):
    game = state or fresh_state()
    view = {'name': GAME_NAME, 'rules': PUBLIC_RULES, 'offer_limits': OFFER_LIMITS, 'phase': game['phase']}
    if game['hand_no']:
        view.update(hand_no=game['hand_no'], pot_gp=game['pot_gp'])
    if game.get('player'):
        view['your_purse_gp'] = game['player']['purse_gp']
    if game['phase'] in IN_HAND_PHASES:
        view['your_cards'] = hand_text(game['hands']['player']) if 'player' in game['hands'] else None
        view['still_in'] = _names(game['in_hand'])
        if game['to_call_gp']:
            view['to_call_gp'] = game['to_call_gp']
    if game['history']:
        last = dict(game['history'][-1])
        last['winners'] = _names(last.get('winners', []))
        last['shown'] = {SEAT_NAMES[seat]: hand_text(cards) for seat, cards in last.get('shown', {}).items()}
        view['last_hand'] = last
    if game['dealer_status'] == 'exposed':
        view['dealer_exposed'] = 'The dealer\'s reading of the card backs has been exposed at this table.'
    return view


def private_view(state):
    """DM-only: for the private decision stage, never the performer."""
    game = state or fresh_state()
    view = {'dm_choice': DM_CHOICES,
            'stacks_gp': dict(game['stacks_gp'])}
    if game['phase'] in IN_HAND_PHASES:
        view['hands'] = {seat: hand_text(cards) for seat, cards in game['hands'].items()}
        view['this_hand'] = game['this_hand']
        view['dealer_knows_player_hand'] = game['dealer_status'] == 'reading_backs'
    if game['accusations_failed']:
        view['accusations_failed'] = game['accusations_failed']
    return view


def allowed_amounts(state):
    """Gold amounts a wager sentence may name right now."""
    game = state or fresh_state()
    amounts = set(range(BET_MIN_GP, BET_MAX_GP + 1)) | {ANTE_GP}
    for value in (game['pot_gp'], game['to_call_gp'], (game.get('player') or {}).get('purse_gp')):
        if value:
            amounts.add(value)
    for entry in game['history'][-1:]:
        amounts.add(entry.get('pot_gp') or 0)
    amounts.discard(0)
    return amounts


def host_view(state):
    game = state or fresh_state()
    return {'game': GAME_NAME, 'phase': game['phase'], 'moves_now': list(MOVES_BY_PHASE[game['phase']]),
            'how': HOST_HOW, 'public': public_view(game)}


def check_state(game, previous):
    """Integrity for a committed game state: known shape, no negative money, and gold
    conserved except when the player first brings a purse to the table."""
    require(isinstance(game, dict) and game.get('game') == GAME_ID and game.get('phase') in MOVES_BY_PHASE,
            'Invalid table game state')
    require(all(type(v) is int and v >= 0 for v in game['stacks_gp'].values()) and
            type(game['pot_gp']) is int and game['pot_gp'] >= 0, 'Table game money must be whole and non-negative')
    if game.get('player') is not None:
        require(type(game['player'].get('purse_gp')) is int and game['player']['purse_gp'] >= 0,
                'Player purse must be whole and non-negative')
    if previous and previous.get('player') is not None:
        require(_gold_total(game) == _gold_total(previous), 'Table game gold must be conserved')

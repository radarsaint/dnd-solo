"""Twenty-one (blackjack), with a one-check mode: the simple table game Brendon asked for.

Brendon's table call 7 (2026-10-02): a player who says "I play the game" gets a choice
between resolving the round with one check and an easy, familiar game (blackjack- or
poker-class). Call 1: the stake is what the player bets, or what the dealer will risk
(a 10 gp default round is fine; a 1 gp high-card flip is not), and the rules stay light
enough to be worth the table time.

So this procedure has two modes, chosen by the player and persisted:

* ``check``: one roll settles the round. The PC rolls the configured skill against the
  dealer's flat 10 + bonus (NPCs never roll); the marked deck still tilts it unless the
  player caught the cheat. Gold moves at the agreed stake.
* ``play``: twenty-one. Closest to 21 without going over beats the dealer; the only
  decisions are hit or stand. The dealer draws to 17.

The marked deck survives in both: the dealer reads the backs and deals himself the
second card when it is better (dealing seconds); in check mode that is an edge on his
number. Watching the deal is a Perception contest against the hidden claim's DC, and a
catch reveals the claim's fact and lets an accusation void the round.

Numbers never reach public text (call 4): no DCs, totals of rolls, or modifiers. They
stay in the private cheat log and in ``trace`` (the turn's ledger evidence).

Gold only moves between the dealer's stack, the stakes, and the player's running net
(the PC's purse lives outside this table unless the player declares a buy-in):
sum(stacks) + player net is conserved.
"""
import copy
import re

from .kit_cards import (NeedsRuling, _ACCUSE, _CHEAT_WORD, _LEAVE, _WATCH, _d20, _rng, supplied_roll)
from .state_context import InvalidChange, require

GAME = 'twenty_one'
MODES = ('check', 'play')
RANKS = ('ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king')
SUITS = ('spades', 'hearts', 'clubs', 'diamonds')
DEALER_STANDS = 17
RULES = (
    'Twenty-one (blackjack): get closer to 21 than the dealer without going over. Number cards '
    'count their number, faces count 10, an ace counts 1 or 11.',
    'Each hand you hit (take a card) or stand. The dealer draws until he holds 17 or more. A win '
    'pays even money on your bet; a tie is a push.',
    'Or settle a round with one check instead of playing the hand out; the bet moves the same way.',
)
GAME_TERMS = ('twenty-one', 'twenty', 'blackjack', 'hit', 'stand', 'bust', 'bet', 'bets', 'stake', 'stakes',
              'hand', 'hands', 'dealer', 'ante', 'blind', 'round', 'house', 'push', 'card', 'cards', 'deal',
              'pot', 'check', 'roll')

# The player picks the weight of the round.
CHECK_MODE = re.compile(
    r"\broll (?:for it|it|for the (?:round|hand|pot))\b|\b(?:one|a|single|quick|just a) (?:check|roll)\b"
    r"|\bresolve (?:it|the round|this|the hand)\b|\bskill (?:check|test)\b|\b(?:with|on) a check\b"
    r"|\bcheck mode\b|\bquick (?:way|version)\b|\bjust roll\b")
PLAY_MODE = re.compile(
    r"\bblackjack\b|\btwenty[- ]one\b|\bplay (?:it|the hand|a hand|the round|the game) out\b"
    r"|\bplay (?:a|the) (?:hand|mini ?game)\b|\bmini ?game\b|\bdeal me (?:a hand|cards)\b|\bplay for real\b")
PLAY_REQUEST = re.compile(
    r"\b(?:play|plays|playing|join|sit in|sit down|deal me in|deal me|i'?m in|count me in|buy in|buy-in|"
    r"another (?:round|hand|game)|(?:play|go|deal) again|next (?:round|hand)|let'?s go|"
    r"dealt in|deal (?:me|us|her|him) in|be dealt|get dealt|a seat at the table|take (?:the|a|an) (?:empty |open |free )?(?:chair|seat))\b"
    r"|(?:^|[.!;]\s*)deal\b(?!-)")
_BET = re.compile(r"\b(?:bet|bets|betting|wager|stake|ante|put (?:up|down|in))\b")
_HIT = re.compile(r"\b(?:hit|hit me|another card|card me|one more card|draw)\b")
_STAND = re.compile(r"\b(?:stand|stay|hold|i'?m good|i'?ll keep|stick|no more)\b")


def card_name(card):
    rank, suit = card
    return f'{rank} of {suit}'


def hand_value(cards):
    total, aces = 0, 0
    for rank, _ in cards:
        if rank == 'ace':
            total, aces = total + 11, aces + 1
        elif rank in ('jack', 'queen', 'king'):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total


def _better(old, new):
    """True when hand `new` is better for its holder than `old` (higher without busting)."""
    a, b = hand_value(old), hand_value(new)
    if a > 21:
        return b < a
    return b <= 21 and b > a


_BUY_IN = re.compile(r"\bbuy(?:ing)?[- ]in\b")


def bet_amount(action, loose=False):
    """The player's bet in this action. A buy-in amount ("I buy in with 20 gold") is the
    purse they bring to the table, not a bet, unless they also use betting words. With
    ``loose`` (the table is waiting on a bet), a bare number counts ("Fine, twenty.")."""
    text = action.casefold()
    if _BUY_IN.search(text) and not _BET.search(text):
        return None
    return player_amount(action, loose=loose)


def can_cover(public, amount):
    """True when the player can risk ``amount`` on one round: within the table's most per
    round, and within the gold they brought to the table when they declared a purse (the
    purse plus what they have won or lost since). The same cap every bet obeys."""
    if amount > public['max_stake']:
        return False
    player = public.get('player')
    purse = (player or {}).get('purse')
    return purse is None or amount <= purse + player['net']


def player_amount(action, loose=False):
    """A gold amount the player names, in digits or words ("twenty" is 20): a number with a
    coin word after it, or right after a betting word ("bet fifteen"). With ``loose`` (the
    table is waiting on the player's bet), a bare number counts too ("Fine, twenty."),
    except the game's name ("twenty-one") and counts of hands, rounds, or cards."""
    from .kit_rolls import number_words, without_rolls
    text = without_rolls(action.casefold().replace('\u2019', "'"))
    numbers = number_words(text)
    for value, start, end in numbers:
        if re.match(r'\s*(?:gp|gold|coins?|gold pieces)\b', text[end:]):
            return value
    for value, start, end in numbers:
        if re.search(r"\b(?:bet|bets|betting|wager|stake|put (?:up|down|in)|raise|make it|i'?ll do|go)\s+(?:\w+\s+)?$",
                     text[max(0, start - 24):start]) and not _NOT_A_BET.match(text[end:]) and \
                not _GAME_NAME.match(text[start:]):
            return value
    if loose:
        for value, start, end in numbers:
            if _GAME_NAME.match(text[start:]) or _NOT_A_BET.match(text[end:]):
                continue
            if value == 1 and not text[start:end].isdigit():
                continue  # "one hand", "one more"
            return value
    return None


_GAME_NAME = re.compile(r'twenty[- ]one\b|21\b(?!\s*(?:gp|gold))')
_NOT_A_BET = re.compile(r'[- ]?\s*(?:hands?|rounds?|cards?|checks?|rolls?|more|of (?:spades|hearts|clubs|diamonds)|'
                        r'times|minutes|feet|ft|percent|%)\b')


# Skills a player may choose to settle a one-check round (the table's own skill always counts).
ROUND_SKILLS = {
    'sleight_of_hand': re.compile(r"\b(?:cheat\w*|palm\w*|sleight of hand|swap\w* (?:a|the|my) card|"
                                  r"slip\w* (?:a|an|the) (?:card|ace)|stack\w* the deck|card up my sleeve)\b"),
    'insight': re.compile(r"\bread(?:ing|s)? (?:the dealer|him|his (?:face|eyes|hands|tells?)|the table)\b|\btells?\b"),
    'deception': re.compile(r"\bbluff\w*\b"),
}


def initial_state(config):
    return {
        'public': {
            'game': GAME, 'name': config['name'], 'dm_choice': config['dm_choice'], 'unit': config['unit'],
            'stacks': dict(config['seats']), 'stacks_note': config.get('stacks_note', ''),
            'default_stake': config['default_stake'], 'max_stake': config['max_stake'],
            'offered': False, 'mode': None, 'player': None, 'round': None, 'rounds_played': 0,
            'last_result': None, 'table_mood': 'open', 'toll_stake': None, 'watch_next_deal': False,
        },
        'private': {'deck': None, 'dealer_cards': [], 'cheated': False, 'cheat_log': []},
    }


def check_config(config):
    for key in ('name', 'dm_choice', 'unit', 'seats', 'cheat', 'labels', 'default_stake', 'max_stake', 'check'):
        require(key in config, f'Twenty-one config needs {key}')
    for key in ('actor', 'sleight_bonus', 'reveals_fact', 'caught_text', 'check_edge'):
        require(key in config['cheat'], f'Twenty-one cheat config needs {key}')
    require(config['check'].get('skill') and type(config['check'].get('npc_bonus')) is int,
            'Twenty-one check mode needs a skill and the dealer\'s flat bonus')
    require(type(config['default_stake']) is int and config['default_stake'] >= 1 and
            type(config['max_stake']) is int and config['max_stake'] >= config['default_stake'],
            'Twenty-one stakes: a default of at least 1 gp and a maximum no lower than it')
    if not all(actor in config['labels'] for actor in config['seats']):
        raise InvalidChange('Every seat needs a public label')
    require(config['cheat']['actor'] in config['seats'], 'The dealer must hold a seat')


def _asked(text, match):
    """True when the words matched sit in a question ("Do you lot play blackjack? I don't
    know your games."): a '?' closes their sentence."""
    rest = re.split(r'[.!]', text[match.end():], maxsplit=1)[0]
    return '?' in rest


def card_intent(action, procedure_state):
    """A table action for this game, or None (ordinary speech)."""
    text = action.casefold().replace('\u2019', "'").strip()
    public = procedure_state['public']
    seated = public['player'] is not None
    live = bool(public['round'] and public['round']['phase'] == 'play')
    # A stated roll is not table talk: Avrae's output (titles, fields, dice) goes whole.
    from .kit_rolls import AVRAE_TITLE, without_rolls
    text = AVRAE_TITLE.sub(' ', without_rolls(text)).strip()
    question = text.rstrip(' .\'"\u201d').endswith('?')
    if _LEAVE.search(text):
        return 'card_leave' if seated else None
    if _ACCUSE.search(text) and not question:
        return 'card_accuse' if seated or public['round'] else None
    if _WATCH.search(text):
        return 'card_watch'
    if live:
        if CHECK_MODE.search(text):
            return 'card_mode_check'  # "just roll for this one": the live hand settles on a check
        if _STAND.search(text) and not question:
            return 'card_stand'
        if _HIT.search(text) and not question:
            return 'card_hit'
        return None  # anything else mid-hand is talk; the menu never comes back mid-hand
    if question:
        return None
    if CHECK_MODE.search(text) and not _asked(text, CHECK_MODE.search(text)):
        return 'card_mode_check'
    if PLAY_MODE.search(text) and not _asked(text, PLAY_MODE.search(text)):
        return 'card_mode_play'
    if _CHEAT_WORD.search(text) and seated:
        return 'card_accuse'
    request = PLAY_REQUEST.search(text)
    if (request and not _asked(text, request)) or (_BET.search(text) and player_amount(text)) or \
            (public['offered'] and not public['mode'] and bet_amount(text, loose=True) and
             not re.search(r'\b(no|not|never)\b', text)):
        return 'card_round' if public['mode'] else 'card_offer'
    return None


class TwentyOneTable:
    """Resolve one table action into (public_event, new_state, reveals). ``trace`` holds the
    numbers behind it for the ledger; ``toll_outcome`` is 'won' or 'lost' when a round
    with the toll riding on it settles."""

    def __init__(self, procedure_id, config, modifiers, seed, passives=None, dcs=None):
        self.id = procedure_id
        self.config = config
        self.modifiers = modifiers
        self.passives = passives or {}
        cheat = config['cheat']
        self.dcs = {'watch': 10 + cheat['sleight_bonus'], **(dcs or {})}
        self.seed = seed
        self.labels = dict(config['labels'])
        self.dealer = cheat['actor']
        self.trace = []
        self.toll_outcome = None
        self.toll_note = ''

    def resolve(self, kind, action, revision, state):
        self._supplied_spent = False
        game = copy.deepcopy(state)
        handler = getattr(self, '_' + kind[len('card_'):])
        text, reveals = handler(action, revision, game['public'], game['private'])
        return text, game, reveals

    # -- rolls -----------------------------------------------------------------
    def _modifier(self, skill, action, supplied=None):
        if supplied and supplied[1] is not None:
            return supplied[1]
        value = self.modifiers.get(skill)
        if value is None:
            raise NeedsRuling(f'Load a character sheet or state the {skill.replace("_", " ").title()} roll '
                              '(e.g. "I rolled 12 + 4 = 16"). No turn was committed.')
        return value

    def _roll(self, skill, dc, action, revision, label, passive_counts=True):
        passive = self.passives.get(skill) if passive_counts else None
        name = skill.replace('_', ' ').title().replace(' Of ', ' of ')
        if passive is not None and passive >= dc:
            self.trace.append(f'{label}: passive {name} {passive} meets {dc}; no roll')
            return {'auto': True, 'total': passive, 'dc': dc, 'success': True, 'die': None, 'modifier': None}
        # A roll the player states counts once: for the first check this action makes.
        supplied = None if getattr(self, '_supplied_spent', False) else \
            supplied_roll(action, self.modifiers.get(skill), skill)
        self._supplied_spent = bool(supplied) or getattr(self, '_supplied_spent', False)
        modifier = self._modifier(skill, action, supplied)
        die = supplied[0] if supplied else _d20(self.seed, revision, label, action.casefold())
        total = die + modifier
        self.trace.append(f'{label}: {name} d20 {die} + {modifier} = {total} vs {dc}')
        return {'auto': False, 'die': die, 'modifier': modifier, 'total': total, 'dc': dc,
                'success': total >= dc}

    # -- seating, the offer, and the mode ---------------------------------------
    def _seat(self, action, public):
        from .kit_rolls import without_rolls
        found = re.search(r'\bbuy(?:ing)?[- ]in (?:with|for) (\d{1,4})\s*(?:gp|gold)\b', without_rolls(action))
        purse = int(found.group(1)) if found else None
        if public['player'] is None:
            public['player'] = {'net': 0, 'purse': purse, 'unwelcome': False}
        elif public['player']['purse'] is None and purse is not None:
            # Seated before naming a purse (e.g. offered the game first): the buy-in sets it now.
            public['player']['purse'] = purse

    def _offer(self, action, revision, public, private):
        self._seat(action, public)
        public['offered'] = True
        bet = bet_amount(action, loose=bool(public['offered']))
        note = ''
        if bet:
            bet, note = self._capped(bet, public)
            public['pending_bet'] = bet
        stake = f'your {bet} gp' if bet else f'whatever you bet; the house plays {public["default_stake"]} gp a round'
        return (f'{note}You want in. Two ways to play a round: settle it with one check, or play it out as '
                f'twenty-one (blackjack), closest to 21 without going over. The stake is {stake}. Which way?'), []

    def _capped(self, bet, public):
        """A bet over the table's most a round, or over the purse the player brought, comes
        down to the cap, and the player is told why (same cap as ``can_cover``)."""
        cap, why = public['max_stake'], f'The most this table plays is {public["max_stake"]} gp a round'
        player = public.get('player') or {}
        if player.get('purse') is not None and player['purse'] + player['net'] < cap:
            cap, why = player['purse'] + player['net'], 'That is all you brought to the table'
        if bet > cap:
            self.trace.append(f'bet {bet} gp capped at {cap} gp')
            return cap, f'{why}, so the bet is {cap} gp. '
        return bet, ''

    def _mode_check(self, action, revision, public, private):
        public['mode'] = 'check'
        round_ = public.get('round')
        if round_ and round_.get('phase') == 'play':
            # Mid-hand "just roll for this one": the live hand settles on one check instead.
            round_['mode'] = 'check'
            lines = ['You set the hand aside and settle it the quick way.']
            stake_text = (f'the toll, {round_["stake"]} gp, rides on it' if round_.get('toll')
                          else f'{round_["stake"]} gp a side')
            return self._check_round(action, revision, public, private, lines, stake_text,
                                     round_.get('cheat_seen')), []
        return self._round(action, revision, public, private)

    def _mode_play(self, action, revision, public, private):
        public['mode'] = 'play'
        text, reveals = self._round(action, revision, public, private)
        spoken = action.casefold().replace('\u2019', "'")
        if public['round'] and public['round']['phase'] == 'play' and _HIT.search(spoken) and \
                not re.search(r'\bhit or stand\b', spoken):
            # "Twenty, and I'll play it out. Hit." The hit in the same breath is played.
            more, _ = self._hit(action, revision, public, private)
            text = f'{text.removesuffix("Hit or stand?").strip()} {more}'
        return text, reveals

    def _stake(self, action, public):
        dealer_gp = public['stacks'][self.dealer]
        toll = public.get('toll_stake')
        if toll:
            if can_cover(public, toll):
                return toll, True
            # The toll can ride on a round only if the player can lose all of it, under
            # the same cap as any bet. It goes back to being owed; this round is for gold.
            public['toll_stake'] = None
            self.toll_outcome = 'unstaked'
            self.trace.append(f'toll stake {toll} gp exceeds what the player can cover; unstaked')
            self.toll_note = ('You cannot cover the toll from what you brought to the table, so it '
                              'stays owed; this round is for gold.')
        named = bet_amount(action, loose=bool(public['offered']))
        if named:
            named, note = self._capped(named, public)
            self.toll_note = (self.toll_note + ' ' + note).strip() if note else self.toll_note
            public.pop('pending_bet', None)
        asked = named or public.pop('pending_bet', None) or \
            ((public['last_result'] or {}).get('stake')) or public['default_stake']
        stake = min(asked, public['max_stake'], dealer_gp)
        purse = public['player']['purse']
        if purse is not None:
            stake = min(stake, purse + public['player']['net'])
        return stake, False

    # -- a round ---------------------------------------------------------------------
    def _round(self, action, revision, public, private):
        self._seat(action, public)
        player = public['player']
        if player['unwelcome']:
            raise NeedsRuling('The table will not deal you in after you were caught. No turn was committed.',
                              attempt=True)
        stake, toll = self._stake(action, public)
        if stake < 1:
            raise NeedsRuling('There is no gold left on one side of the table to play for. No turn was '
                              'committed.', attempt=True)
        number = public['rounds_played'] + 1
        lines = []
        reveals = []
        watched = public.get('watch_next_deal')
        public['watch_next_deal'] = False
        caught = False
        if watched:
            result = self._roll('perception', self.dcs['watch'], action, revision, f'watch round {number}')
            caught = result['success']
            if caught:
                reveals.append(self.config['cheat']['reveals_fact'])
                lines.append(self.config['cheat']['caught_text'])
            else:
                lines.append('Nothing about the deal looks wrong to you.')
        public['round'] = {'number': number, 'mode': public['mode'], 'stake': stake, 'toll': toll,
                           'phase': 'play', 'cards': [], 'dealer_shows': None, 'cheat_seen': caught}
        private['cheat_log'].append({'round': number, 'mode': public['mode'], 'watched': bool(watched),
                                     'caught': caught, 'detection': self.trace[-1] if watched else None})
        private['cheat_log'] = private['cheat_log'][-8:]
        stake_text = (f'the toll, {stake} gp, rides on it' if toll else f'{stake} gp a side')
        if self.toll_note:
            lines.insert(0, self.toll_note)
        if public['mode'] == 'check':
            return self._check_round(action, revision, public, private, lines, stake_text, caught), reveals
        return self._deal(action, revision, public, private, lines, stake_text), reveals

    def _round_skill(self, action):
        """The skill that settles a one-check round: the player's own relevant choice, else
        the table's. A stated roll in a skill that can win a hand counts as the choice
        (Avrae's "makes a Sleight of Hand check!"); otherwise the words do (palming or
        cheating is Sleight of Hand, reading the dealer is Insight, a bluff is Deception)."""
        from .kit_rolls import stated_skill
        default = self.config['check']['skill']
        stated = stated_skill(action)
        if stated in ROUND_SKILLS or stated == default:
            return stated
        spoken = action.casefold().replace('\u2019', "'")
        for skill, words in ROUND_SKILLS.items():
            if words.search(spoken):
                return skill
        return default

    def _check_round(self, action, revision, public, private, lines, stake_text, caught):
        check = self.config['check']
        skill = self._round_skill(action)
        if skill != check['skill']:
            self.trace.append(f'round skill: player chose {skill} (table default {check["skill"]})')
        # The marks tell him what you hold: an edge on his number unless you caught it.
        edge = 0 if caught else self.config['cheat']['check_edge']
        private['cheated'] = not caught
        dc = 10 + check['npc_bonus'] + edge
        result = self._roll(skill, dc, action, revision, f'round {public["round"]["number"]} check',
                            passive_counts=False)
        if edge:
            self.trace.append(f'marked deck: dealer number includes +{edge}')
        name = skill.replace('_', ' ').title().replace(' Of ', ' of ')
        lines.append(f'One round, {stake_text}, settled on {name}.')
        lines.append(self._settle(public, private, 'win' if result['success'] else 'lose'))
        return ' '.join(lines)

    def _fresh_deck(self, private, number):
        deck = [[rank, suit] for suit in SUITS for rank in RANKS]
        _rng(self.seed, 'twenty_one', number).shuffle(deck)
        private['deck'] = deck

    def _draw(self, private, number, for_dealer=False):
        if len(private['deck'] or []) < 2:
            self._fresh_deck(private, f'{number}:reshuffle')
        deck = private['deck']
        if for_dealer and len(deck) > 1:
            # Dealing seconds: he reads the marks and takes the second card when it helps him.
            hand = private['dealer_cards']
            if _better(hand + [deck[0]], hand + [deck[1]]):
                private['cheated'] = True
                return deck.pop(1)
        return deck.pop(0)

    def _deal(self, action, revision, public, private, lines, stake_text):
        number = public['round']['number']
        self._fresh_deck(private, number)
        private['cheated'] = False
        private['dealer_cards'] = []
        cards = []
        for _ in range(2):
            cards.append(self._draw(private, number))
            private['dealer_cards'].append(self._draw(private, number, for_dealer=True))
        round_ = public['round']
        round_['cards'] = [card_name(c) for c in cards]
        round_['dealer_shows'] = card_name(private['dealer_cards'][0])
        private['player_cards'] = cards
        lines.append(f'Twenty-one, {stake_text}. Your cards: {" and ".join(round_["cards"])}, '
                     f'{hand_value(cards)}. The dealer shows the {round_["dealer_shows"]}.')
        if hand_value(cards) == 21:
            dealer = hand_value(private['dealer_cards'])
            lines.append('Twenty-one on the deal.')
            lines.append(self._settle(public, private, 'push' if dealer == 21 else 'win'))
        else:
            lines.append('Hit or stand?')
        return ' '.join(lines)

    def _hit(self, action, revision, public, private):
        round_ = public['round']
        cards = private['player_cards']
        cards.append(self._draw(private, round_['number']))
        round_['cards'] = [card_name(c) for c in cards]
        total = hand_value(cards)
        text = f'You take the {round_["cards"][-1]}: {total}.'
        if total > 21:
            return f'{text} Bust. {self._settle(public, private, "lose")}', []
        if total == 21:
            return f'{text} {self._dealer_plays(public, private)}', []
        return f'{text} Hit or stand?', []

    def _stand(self, action, revision, public, private):
        total = hand_value(private['player_cards'])
        return f'You stand on {total}. {self._dealer_plays(public, private)}', []

    def _dealer_plays(self, public, private):
        number = public['round']['number']
        while hand_value(private['dealer_cards']) < DEALER_STANDS:
            private['dealer_cards'].append(self._draw(private, number, for_dealer=True))
        dealer = hand_value(private['dealer_cards'])
        mine = hand_value(private['player_cards'])
        shown = ', '.join(card_name(c) for c in private['dealer_cards'])
        public['round']['dealer_cards'] = [card_name(c) for c in private['dealer_cards']]
        if dealer > 21:
            outcome, line = 'win', f'The dealer turns up {shown} and busts.'
        elif dealer > mine:
            outcome, line = 'lose', f'The dealer turns up {shown}: {dealer} beats your {mine}.'
        elif dealer < mine:
            outcome, line = 'win', f'The dealer turns up {shown}: your {mine} beats his {dealer}.'
        else:
            outcome, line = 'push', f'The dealer turns up {shown}: {dealer} each, a push.'
        return f'{line} {self._settle(public, private, outcome)}'

    def _settle(self, public, private, outcome):
        round_ = public['round']
        stake = round_['stake']
        player = public['player']
        if round_['toll']:
            # The toll rode on it: a win waives it, a loss pays it out of the stake.
            self.toll_outcome = 'won' if outcome == 'win' else 'lost' if outcome == 'lose' else None
            if outcome == 'lose':
                public['stacks'][self.dealer] += stake
                player['net'] -= stake
            if outcome != 'push':
                public['toll_stake'] = None
        elif outcome == 'win':
            public['stacks'][self.dealer] -= stake
            player['net'] += stake
        elif outcome == 'lose':
            public['stacks'][self.dealer] += stake
            player['net'] -= stake
        round_['phase'] = 'done'
        public['rounds_played'] = round_['number']
        # Someone at the table reacts; the performer turns this into a short vignette.
        others = [seat for seat in self.config['seats'] if seat != self.dealer]
        reactor = others[round_['number'] % len(others)] if others else self.dealer
        public['last_result'] = {'round': round_['number'], 'mode': round_['mode'], 'stake': stake,
                                 'outcome': outcome, 'toll': round_['toll'], 'your_net': player['net'],
                                 'table_beat': {'who': self.labels.get(reactor, reactor),
                                                'dealer': self.labels.get(self.dealer, self.dealer),
                                                'cue': 'a reaction, a tell, or a remark at the table, '
                                                       'not a ledger line'}}
        if round_['toll']:
            return {'win': 'You take the round, and the toll is off the table.',
                    'lose': f'The round goes to the house: the toll, {stake} gp, is paid.',
                    'push': 'A push: the toll still rides on the next round.'}[outcome]
        return {'win': f'You win {stake} gp.', 'lose': f'You lose {stake} gp to the house.',
                'push': 'Nobody wins; the bets go back.'}[outcome]

    # -- watching, accusing, leaving -----------------------------------------------
    def _watch(self, action, revision, public, private):
        public['watch_next_deal'] = True
        text = action.casefold().replace('\u2019', "'")
        if public['player'] is None and (PLAY_REQUEST.search(text) or (_BET.search(text) and player_amount(text))):
            # "I sit, put down ten gold, and say I'll play. I watch the dealer's hands": joining
            # and watching in one breath. The seat and the offer happen; the watch waits for the deal.
            offer, _ = self._offer(action, revision, public, private)
            return f'{offer} Your eyes will be on the dealer\'s hands when he deals.', []
        if public['player'] is None:
            return 'You settle your eyes on the dealer\'s hands for the next deal.', []
        if public['round'] and public['round']['phase'] == 'play':
            return 'You settle your eyes on the dealer\'s hands for the next deal.', []
        if public['mode']:
            return self._round(action, revision, public, private)
        return 'You settle your eyes on the dealer\'s hands for the next deal.', []

    def _accuse(self, action, revision, public, private):
        round_ = public['round']
        record = public.setdefault('accusations', [])
        seen = bool(round_ and round_.get('cheat_seen'))
        if seen and round_['phase'] == 'play':
            round_['phase'] = 'void'
            public['table_mood'] = 'tense: accused with proof'
            record.append({'round': round_['number'], 'backed': True})
            return ('The round is void and every coin stays where it was. You saw the deal, and the whole '
                    'table knows you saw it. The dealer does not confess.'), []
        public['table_mood'] = 'tense: accused without proof'
        record.append({'round': round_['number'] if round_ else None, 'backed': False})
        return 'Nothing on the table proves it. The game stops while every face at the table turns to you.', []

    def _leave(self, action, revision, public, private):
        player = public['player']
        lead = ''
        if public['round'] and public['round']['phase'] == 'play':
            lead = self._settle(public, private, 'lose') + ' '
        if public.get('toll_stake'):
            # Leaving before the round it rode on: the toll is owed again, never stranded.
            public['toll_stake'] = None
            self.toll_outcome = 'unstaked'
            lead += 'The toll you meant to play for is still owed. '
        net = player['net']
        public['last_result'] = {**(public['last_result'] or {}), 'left_table': True, 'your_net': net}
        public['player'] = None
        return (f'{lead}You leave the game {"up" if net >= 0 else "down"} {abs(net)} gp.'), []


def table_gold(public):
    return sum(public["stacks"].values()) + (public["player"]["net"] if public["player"] else 0)


def public_view(config, public):
    labels = config.get('labels', {})
    view = copy.deepcopy(public)
    view['rules'] = list(RULES)
    view['stacks'] = {labels.get(seat, seat): gp for seat, gp in view.get('stacks', {}).items()}
    return view


# -- narration must match the table (live 6c, 2026-10-03: "one prick on your four" when the
# marks give a four three) -------------------------------------------------------------
_RANK_WORDS = {'ace': 'ace', 'aces': 'ace', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6',
               'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'jack': 'jack', 'queen': 'queen',
               'king': 'king', 'deuce': '2', 'trey': '3'}
_RANK_WORDS.update({str(n): str(n) for n in range(2, 11)})
_COUNT_WORDS = {'no': 0, 'zero': 0, 'a single': 1, 'one': 1, 'a lone': 1, 'one lonely': 1, 'a lonely': 1,
                'single': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                'nine': 9, 'ten': 10, 'eleven': 11}
_RANK_RE = r'(ace|two|three|four|five|six|seven|eight|nine|ten|jack|queen|king|deuce|trey|10|[2-9])'
_SUIT_RE = r'(spades|hearts|clubs|diamonds)'


def card_value(rank):
    return 11 if rank == 'ace' else 10 if rank in ('jack', 'queen', 'king') else int(rank)


def mark_count(config, rank):
    """How many marks the fixed scheme puts on a card of ``rank``, or None (no scheme)."""
    marks = ((config or {}).get('cheat') or {}).get('marks') or {}
    if marks.get('count') == 'value_minus_one':
        return card_value(rank) - 1
    return None


def _visible_cards(public):
    round_ = (public or {}).get('round') or {}
    names = list(round_.get('cards') or []) + list(round_.get('dealer_cards') or [])
    if round_.get('dealer_shows'):
        names.append(round_['dealer_shows'])
    return names


def check_narration(text, public, config):
    """Problems (strings) where the narration contradicts the table: a mark count on a named
    card that is not the scheme's count, a named card ("the four of clubs") that is not on
    the table, or "your <rank>" when the player holds none. Cards the state does not show
    (the deck's next card, the dealer's hidden one) are never checked against it."""
    problems = []
    lowered = (text or '').casefold().replace('\u2019', "'")
    visible = [name.casefold() for name in _visible_cards(public)]
    mine = [name.split(' of ')[0] for name in ((public or {}).get('round') or {}).get('cards') or []]
    units = (((config or {}).get('cheat') or {}).get('marks') or {}).get('units') or ()
    if units:
        unit_re = '|'.join(sorted((re.escape(u) for u in units), key=len, reverse=True))
        count_re = r'(\d{1,2}|' + '|'.join(sorted((re.escape(w) for w in _COUNT_WORDS), key=len, reverse=True)) + r')'
        pattern = re.compile(count_re + r'\s+(?:[a-z]+\s+){0,2}?(?:' + unit_re + r')\b[^.;:!?]{0,40}?\bon (?:your|the|his|my) '
                             + _RANK_RE + r'\b(?:\s+of\s+' + _SUIT_RE + r')?')
        # "...tiny pinpricks near one corner, one on your four": the unit named earlier in the sentence.
        elliptic = re.compile(r'(?<![a-z])' + count_re + r'\s+on (?:your|the|his|my) ' + _RANK_RE +
                              r'\b(?:\s+of\s+' + _SUIT_RE + r')?')
        found = list(pattern.finditer(lowered))
        for sentence in re.split(r'(?<=[.!?])\s+', lowered):
            if re.search(r'\b(?:' + unit_re + r')\b', sentence):
                found += list(elliptic.finditer(sentence))
        seen = set()
        for match in found:
            if (match.group(1), match.group(2)) in seen:
                continue
            seen.add((match.group(1), match.group(2)))
            said = match.group(1)
            count = int(said) if said.isdigit() else _COUNT_WORDS[said]
            rank = _RANK_WORDS[match.group(2)]
            expected = mark_count(config, rank)
            if expected is not None and count != expected:
                problems.append(f'Narration counts {count} mark(s) on a {rank}; the marks give a {rank} {expected}.')
    for match in re.finditer(r'\b' + _RANK_RE + r' of ' + _SUIT_RE + r'\b', lowered):
        name = f'{_RANK_WORDS[match.group(1)]} of {match.group(2)}'
        if visible and name not in visible:
            problems.append(f'Narration names the {name}, which is not on the table.')
    if mine:
        for match in re.finditer(r'\byour ' + _RANK_RE + r'\b(?!\s+(?:gold|gp|coins?|pieces|of (?:them|those)))', lowered):
            rank = _RANK_WORDS[match.group(1)]
            if rank not in mine and not re.match(r'\s*(?:hand|cards?)', lowered[match.end():]):
                # "your fourteen" is a total, not a card: totals are spelled past ten.
                problems.append(f'Narration gives the player a {rank}; the player holds {", ".join(mine)}.')
    return problems


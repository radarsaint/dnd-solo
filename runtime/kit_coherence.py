"""Coherence guards: Kit's asides must follow from something real, and invented
details must be declared (branch kit-coherence-gambling).

Brendon, 2026-09-29: "Nonsensical is not entertaining. That's a fiction we need to burn."

The playtest in tests/playtests/2026-09-29-area-06c-voice-spec-nik.md showed two
failures the earlier guards could not see:

1. The dealer gave a full welcome, and then Kit said "He could have said hello."
   The aside was built to sound quippy and ignored the line it was commenting on.
2. The private plan made up "high card, a matching coin" and the performance spoke
   it as room canon. Neither the source nor the saved state said anything like it.

What this module does, and what it cannot do:

- ``reacts_to`` (every Kit segment). A short exact quote of the public line or beat
  the aside answers: the player's words this turn, the accepted event, an earlier
  segment of this same turn, or a line from the previous turn. A missing or made-up
  anchor is rejected. That proves the aside points at something real. It cannot
  prove the aside follows from it; the host answers that in the self-check.
- A lexical contradiction guard. An aside (or narration) that says someone did not
  greet, did not speak, or did not ask, when the lines it can see show they did, is
  rejected. It catches only those phrasings.
- ``inventions`` (the private decision). Any detail the DM makes up that the source
  and state do not supply is declared here, and the spoken ones are saved to world
  state so later turns stay consistent. A brief that asks for stakes or rules that
  neither the table game nor a declared invention supplies is rejected.
- Other game names. Only the table's own game (kit_table_game) can be offered.

Coherence is judged by the host. These checks stop the recognizable shapes of the
failure; a model can still write an aside that has a real anchor and still makes no
sense. That is why prepare and decide hand the host a self-check every turn.
"""
import re

from .state_context import require

ANCHOR_MAX_CHARS = 160
ANCHOR_MIN_WORDS = 2
INVENTION_KINDS = ('name', 'object', 'history', 'custom', 'stake', 'rule')
INVENTION_LIMIT = 3            # per decision
INVENTION_MAX_CHARS = 160
DM_INVENTION_LIMIT = 24        # kept in world state
SUBSTANTIAL_LINE_WORDS = 8     # an NPC line this long is speech, not silence

HOST_SELF_CHECK = {
    'answer_in': 'performance.self_check (both fields are required before commit)',
    'questions': {
        'contradiction': ('Read every line against what was said and done this turn and earlier: '
                          'who spoke, who greeted or asked, what was offered, what is on the table, '
                          'and the rules and amounts in table_game. Does any line contradict it? If '
                          'so, rewrite that line first. Answer exactly: none.'),
        'aside_follows': ('For each Kit segment, say in a few words how the aside follows from its '
                          'reacts_to anchor (what it answers and why it is true of that line). A '
                          'quip that could sit under any line, or that says the opposite of its '
                          'anchor, fails: cut or rewrite it. Answer exactly: no aside, when there is '
                          'no Kit segment.'),
    },
    'rule': ('Nonsensical is not entertaining. An aside counts as entertaining only when it is '
             'coherent with what was just said and done. Contradicting the scene, a non sequitur '
             'quip, or an invented fact presented as canon is a failure, never a style choice.'),
}
SELF_CHECK_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'contradiction': {'type': 'string'}, 'aside_follows': {'type': 'string'}},
    'required': ['contradiction', 'aside_follows'],
}
INVENTIONS_SCHEMA = {
    'type': 'array',
    'items': {'type': 'object', 'additionalProperties': False,
              'properties': {'kind': {'type': 'string', 'enum': list(INVENTION_KINDS)},
                             'detail': {'type': 'string'}},
              'required': ['kind', 'detail']},
}

_TYPO = str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"'})
NPC_LABELS = ('Dealer', 'Door-side player', 'Fresco-side player', 'Fourth player', 'Card player')


def _norm(text):
    return ' '.join((text or '').translate(_TYPO).casefold().split())


def _excerpt(text):
    return _norm(text).strip(' .,!?;:"\'')


def _words(text):
    return re.findall(r"[a-z0-9']+", _norm(text))


def _sentences(text):
    return [part.strip() for part in re.split(r'(?<=[.!?\u2026])\s+|\n+', text or '') if part.strip()]


def _spoken_lines(spoken):
    """(speaker, text) for each 'Speaker: text' line of a committed turn."""
    lines = []
    for line in (spoken or '').splitlines():
        speaker, sep, text = line.partition(': ')
        if sep:
            lines.append((speaker.strip(), text.strip()))
        elif line.strip():
            lines.append(('', line.strip()))
    return lines


def anchor_sources(segments, index, player_action, public_event, previous_turn, action_kind):
    """Public lines a Kit segment at `index` may react to: this turn's player words
    and accepted event, earlier segments of this turn, and the previous turn."""
    sources = []
    if action_kind != 'opening' and player_action and player_action != '[scene entry]':
        sources.append(('Player', player_action))
    # A social event only restates the player's words (already a source); its fixed
    # prefix is not something an aside can react to.
    if public_event and action_kind not in ('opening', 'social'):
        sources.append(('Event', public_event))
    for segment in segments[:index]:
        sources.append((segment['speaker'], segment['text']))
    if previous_turn:
        if previous_turn.get('player_input') and previous_turn['player_input'] != '[scene entry]':
            sources.append(('Player', previous_turn['player_input']))
        sources.extend(_spoken_lines(previous_turn.get('spoken')))
    return sources


def anchor_line(anchor, sources):
    excerpt = _excerpt(anchor)
    for speaker, text in sources:
        if excerpt and excerpt in _norm(text):
            return speaker, text
    return None


def check_kit_anchors(segments, player_action, public_event, public_history=(), action_kind=None):
    """HARD. Every Kit segment names, in reacts_to, the public line it answers."""
    previous = (list(public_history) or [None])[-1]
    for index, segment in enumerate(segments):
        anchor = segment.get('reacts_to')
        if segment['speaker'] != 'Kit':
            require(anchor is None or (isinstance(anchor, str) and anchor.strip().casefold() == 'none'),
                    'reacts_to belongs to Kit segments only; use none for other speakers')
            continue
        require(isinstance(anchor, str) and anchor.strip() and anchor.strip().casefold() != 'none',
                'Every Kit segment needs reacts_to: a short exact quote of the public line or beat it '
                'answers (the player\'s words, the accepted event, an earlier line this turn, or a line '
                'from the previous turn). An aside with no anchor is a non sequitur.')
        require(len(anchor.strip()) <= ANCHOR_MAX_CHARS and len(_words(anchor)) >= ANCHOR_MIN_WORDS,
                f'reacts_to quotes {ANCHOR_MIN_WORDS} or more words, at most {ANCHOR_MAX_CHARS} characters')
        sources = anchor_sources(segments, index, player_action, public_event, previous, action_kind)
        require(anchor_line(anchor, sources) is not None,
                'Kit\'s reacts_to does not quote anything said or shown this turn (before the aside) or '
                'on the previous turn. Anchor the aside to a real line, or cut it.')


# Claims an aside or narration makes about what someone did NOT do.
CLAIM_NO_GREETING = re.compile(
    r"\b(could|should|might|would)(n't| not)?( have|'ve) (said|offered|tried) (a )?(hello|hi|good evening|"
    r"greeting|welcome)\b|\b(could|should|might)( have|'ve) (greeted|welcomed|introduced)\b|"
    r"\b(no|not (even )?a|without (a|any|so much as a)) (hello|greeting|welcome|introduction)\b|"
    r"\b(didn't|did not|never|doesn't|does not|won't|hasn't|has not) (even )?(say (hello|hi)|greet|"
    r"welcome|introduce)")
CLAIM_SILENT = re.compile(
    r"\b(didn't|did not|hasn't|has not|never|won't) (even )?(say|said|spoken|speak) a (single )?word\b|"
    r"\bnot a (single )?word\b|\bwithout a word\b|\b(said|says) nothing\b|\b(hasn't|has not|never) "
    r"(spoken|spoke)\b")
CLAIM_NO_ASK = re.compile(
    r"\b(didn't|did not|never|hasn't|has not|won't) (even )?(ask|asked|bother(ed)? to ask)\b|"
    r"\bwithout (even )?asking\b")
GREETING_EVIDENCE = re.compile(
    r"\b(hello|hi|hey|welcome\w*|greetings?|guest|well met|good (evening|day|morning)|a pleasure|"
    r"come in|join us|pull up)\b")
ADDRESS = re.compile(r"\b(you|your|you're|you've|traveler|traveller|stranger|visitor|guest)\b")


def check_claims_against_lines(segments, player_action, public_history=()):
    """HARD, lexical. An aside or narration may not say someone failed to greet, speak,
    or ask when the lines it can see show they did (the "could have said hello" failure)."""
    previous = (list(public_history) or [None])[-1]
    context = [(speaker, text) for speaker, text in _spoken_lines((previous or {}).get('spoken'))]
    for segment in segments:
        if segment['speaker'] in ('Kit', 'Narrator'):
            for sentence in _sentences(segment['text']):
                norm = _norm(sentence)
                npc_lines = [text for speaker, text in context if speaker in NPC_LABELS]
                if CLAIM_NO_GREETING.search(norm):
                    welcomed = [text for text in npc_lines if GREETING_EVIDENCE.search(_norm(text)) or
                                (ADDRESS.search(_norm(text)) and len(_words(text)) >= SUBSTANTIAL_LINE_WORDS)]
                    if welcomed:
                        raise_invalid(
                            f'Contradiction: the {segment["speaker"]} says nobody greeted or welcomed ("'
                            f'{sentence[:80]}"), but an NPC already addressed the visitor ("'
                            f'{welcomed[0][:80]}"). React to what was actually said.')
                if CLAIM_SILENT.search(norm):
                    spoke = [text for text in npc_lines if len(_words(text)) >= SUBSTANTIAL_LINE_WORDS]
                    if spoke:
                        raise_invalid(
                            f'Contradiction: the {segment["speaker"]} says someone stayed silent ("'
                            f'{sentence[:80]}"), but an NPC just spoke ("{spoke[0][:80]}").')
                if CLAIM_NO_ASK.search(norm):
                    asked = [text for text in npc_lines if '?' in text]
                    if asked:
                        raise_invalid(
                            f'Contradiction: the {segment["speaker"]} says someone did not ask ("'
                            f'{sentence[:80]}"), but an NPC asked ("{asked[0][:80]}").')
        context.append((segment['speaker'], segment['text']))


def check_self_check(self_check, segments):
    """HARD when the bridge requires it: the host's own answers, given before commit."""
    require(isinstance(self_check, dict) and set(self_check) == {'contradiction', 'aside_follows'} and
            all(isinstance(value, str) for value in self_check.values()),
            'Answer the host self-check in performance.self_check: {"contradiction": "none", '
            '"aside_follows": "<how each Kit aside follows from its anchor, or no aside>"}. The '
            'questions are in host_self_check.')
    found = _excerpt(self_check['contradiction'])
    require(found == 'none',
            f'The self-check found a contradiction ({self_check["contradiction"][:120]}). Rewrite the line '
            'that contradicts the scene, then answer none.')
    has_aside = any(segment['speaker'] == 'Kit' for segment in segments)
    follows = _excerpt(self_check['aside_follows'])
    if has_aside:
        require(len(_words(follows)) >= 4 and follows not in ('yes', 'no', 'none', 'n/a', 'no aside'),
                'self_check.aside_follows: say in a few words how each Kit aside follows from its '
                'reacts_to anchor. If you cannot, the aside is a non sequitur: cut or rewrite it.')
    else:
        require(follows == 'no aside', 'self_check.aside_follows is "no aside" when there is no Kit segment')


# ---------------------------------------------------------------------------
# Inventions: details the DM makes up must be declared and then kept.
# ---------------------------------------------------------------------------
CARD_GAME_WORDS = re.compile(
    r"\b(card|cards|deck|deal|dealt|dealing|hand|hands|pot|ante|antes|bet|bets|betting|wager|wagers|"
    r"stake|stakes|game|games|high card|payout|payouts|fold|raise|call)\b")
# Nouns that ask someone to state terms. "bet" as a verb ("ready to bet big") is a
# read on a person, not a request for stakes, so it is not listed.
STAKE_RULE_TERMS = re.compile(
    r"\b(stakes?|wagers?|ante|antes|pot|payouts?|buy-?in|house rules?|rules of (the|this) "
    r"game|game'?s rules|high card|matching coins?|winner takes|winner-takes|per hand|odds)\b")
BRIEF_DIRECTION_FIELDS = ('objective', 'tactic', 'visible_cue', 'player_opening', 'kit_focus', 'npc_notice')
OTHER_GAMES = re.compile(
    r"\b(high card|high-card|poker|blackjack|twenty-one|three-dragon ante|three dragon ante|baccarat|"
    r"cribbage|whist|rummy|faro|dragonchess)\b")
_STOP = frozenset('the a an and or of to in on at for with from this that his her their your you '
                  'it is are be one each'.split())


def _content(text):
    return {word for word in _words(text) if len(word) >= 4 and word not in _STOP}


def check_inventions(inventions, table_game_name=None):
    """The private decision lists what the DM invents this turn. At a table whose card
    game is run by a procedure, the game's rules and stakes come from that procedure."""
    require(isinstance(inventions, list) and len(inventions) <= INVENTION_LIMIT,
            f'inventions is a list of at most {INVENTION_LIMIT} declared DM inventions')
    for item in inventions:
        require(isinstance(item, dict) and set(item) == {'kind', 'detail'} and
                item['kind'] in INVENTION_KINDS and isinstance(item['detail'], str) and
                0 < len(item['detail'].strip()) <= INVENTION_MAX_CHARS,
                f'Each invention is {{kind: {"|".join(INVENTION_KINDS)}, detail: 1-{INVENTION_MAX_CHARS} '
                'characters}')
        if table_game_name and item['kind'] in ('stake', 'rule') and CARD_GAME_WORDS.search(_norm(item['detail'])):
            raise_invalid(f'The card game at this table is {table_game_name}, run by the table game '
                          f'procedure; its rules and stakes come from table_game, not from an invention. '
                          f'Offer {table_game_name} on its own terms.')


def raise_invalid(message):
    require(False, message)


def check_brief_supported(brief, inventions, established=(), table_game_name=None, player_action=None):
    """A brief may ask for stakes or rules only when the table game or a declared (or
    earlier spoken) invention supplies them. The Nik failure: "the simple stakes of the
    current hand", with no game and no stakes anywhere in the source or state."""
    supported_words = set()
    for item in list(inventions) + list(established):
        if item.get('kind') in ('stake', 'rule'):
            supported_words |= _content(item.get('detail', ''))
    for field in BRIEF_DIRECTION_FIELDS:
        text = _norm(brief.get(field, ''))
        term = STAKE_RULE_TERMS.search(text)
        if not term:
            continue
        if table_game_name and (table_game_name.casefold() in text or 'table game' in text):
            continue
        if supported_words & _content(text):
            continue
        if term.group(0) in _norm(player_action):
            continue  # the player named these stakes themselves
        require(False,
                f'public_brief {field} asks for stakes or rules ("{term.group(0)}") that neither the '
                'source nor saved state supplies.'
                + (f' The card game here is {table_game_name} (table_game): name it and use its terms.'
                   if table_game_name else '')
                + ' Anything else the DM makes up must be declared in inventions first.')


def check_other_games(segments, player_action, table_game_name):
    """HARD. The only card game the table can actually run is its own."""
    said = _norm(player_action)
    for segment in segments:
        for found in OTHER_GAMES.finditer(_norm(segment['text'])):
            require(found.group(0) in said,
                    f'The {segment["speaker"]} named "{found.group(0)}", but the only card game this '
                    f'table can run is {table_game_name}. Never promise play the procedure cannot carry out.')


WAGER_WORDS = re.compile(r"\b(ante|antes|pot|bet|bets|raise|raises|wager|wagers|stake|stakes|buy-?in|call|calls|hand)\b")
_UNITS = r'gp|gold pieces|gold coins|gold coin|gold'
_NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20,
                 'thirty': 30, 'forty': 40, 'fifty': 50, 'hundred': 100, 'a hundred': 100}


def _amounts(sentence):
    text = ' '.join(_words(sentence))
    number = r'\d+|' + '|'.join(sorted(_NUMBER_WORDS, key=len, reverse=True))
    return [int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
            for raw in re.findall(rf'\b({number})(?: more)? (?:{_UNITS})\b', text)]


def is_wager_sentence(sentence):
    return bool(WAGER_WORDS.search(_norm(sentence)))


def check_wager_amounts(segments, allowed, player_action, table_game_name):
    """HARD. A gold amount spoken in a wager sentence is one the table game allows
    (ante, a legal bet, the current pot, purse, or amount to call), or the player's own."""
    declared = {amount for sentence in _sentences(player_action or '') for amount in _amounts(sentence)}
    for segment in segments:
        for sentence in _sentences(segment['text']):
            if not is_wager_sentence(sentence):
                continue
            for amount in _amounts(sentence):
                require(amount in allowed or amount in declared,
                        f'The {segment["speaker"]} named a {amount} gp wager; {table_game_name} allows '
                        f'{", ".join(str(a) for a in sorted(allowed))} gp right now. Stakes come from the '
                        'table game procedure, not from the performance.')


def inventions_spoken(inventions, spoken):
    """The declared inventions the performance actually said (they become canon)."""
    said = _content(spoken)
    spoken_items = []
    for item in inventions or ():
        words = _content(item.get('detail', ''))
        # Two shared content words (or all of a one-word detail) count as said aloud.
        if words and len(words & said) >= min(2, len(words)):
            spoken_items.append(item)
    return spoken_items

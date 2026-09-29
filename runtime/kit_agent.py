"""Area 6c Kit play slice: grounded events, private appraisal, public performance.

Only a few explicitly bounded room actions are adjudicated here. The model can
choose and perform a DM move, but it cannot submit world changes to storage.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import kit_guards
from .scene_discernment import IMPROV_READ_SCHEMA, check_improv_read, discernment_candidates
from .state_context import (CONTEXT_BUDGET_BYTES, HostSequenceError, InvalidChange,
                            PERSONALITY_CORE, PLAYER_NOTE_MAX_EVIDENCE, PROJECT_ROOT, Runtime,
                            StaleTurn,
                            check_player_note_text, encode, require)


ROOM_FIXTURE = PROJECT_ROOT / 'tests/fixtures/level_01_area_06c.json'


class PendingRuling(Exception):
    """The room slice cannot establish this outcome without more game machinery."""


@dataclass(frozen=True)
class Resolution:
    kind: str
    public_event: str
    events: list


# The accepted event is bounded at 500 characters (check_plan). A social event is
# a restatement of the player's declared words, so Kit's appraisal and the
# performer react to what was actually said instead of a generic placeholder.
EVENT_MAX_CHARS = 500
SOCIAL_EVENT_PREFIX = 'You declare: '
_TYPOGRAPHIC = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"'})


def social_event(action):
    """Public restatement of a social bid: the player's own words, nothing added.

    Whitespace is collapsed and curly quotes become straight quotes so the private
    stage can copy the event exactly; the words themselves are not changed. Text
    past the event bound is cut at a word boundary and marked with '...'. It says
    nothing about how anyone responds; the full declaration stays in the evidence.
    """
    words = ' '.join(action.translate(_TYPOGRAPHIC).split())
    room = EVENT_MAX_CHARS - len(SOCIAL_EVENT_PREFIX) - 2
    if len(words) > room:
        cut = words[:room - 3]
        cut = cut[:cut.rfind(' ')] if ' ' in cut else cut
        words = cut.rstrip(' ,;:') + '...'
    return f'{SOCIAL_EVENT_PREFIX}"{words}"'


def room_intent(action):
    """Conservative routing; unrecognized text remains conversation or clarification."""
    words = action.lower()
    if re.search(r'\b(attack|stab|shoot|kill|cast|initiative|fireball)\b', words):
        return 'combat'
    if re.search(r'\b(leave|go|walk|move|step)\b', words) and re.search(r'\b(south|door|out)\b', words):
        return 'exit'
    if re.search(r'\b(tip|overturn|flip|lift|move)\b', words) and 'tub' in words:
        return 'tip_tub'
    if re.search(r'\b(look|search|inspect|examine|check|peer)\b', words) and 'tub' in words:
        return 'inspect_tub'
    if re.search(r'\b(look|search|inspect|examine|study|check)\b', words) and re.search(r'\b(fresco|carving|dwarves|dwarf|figures|mountain)\b', words):
        return 'inspect_fresco'
    if re.search(r'\b(insight|disguise|vampire|fangs|makeup)\b', words) and re.search(r'\b(check|inspect|study|look|see|tell|notice|are they)\b', words):
        return 'insight'
    if re.search(r'\b(inspect|study|search|examine|check)\b', words) and re.search(r'\b(cards|deck|marks)\b', words):
        return 'inspect_deck'
    if re.search(r'\b(take a seat|pull up a chair)\b', words):
        return 'social'
    if re.search(r'\b(steal|pocket|grab|pick up|smash|break|hide|climb|force|open|disarm)\b', words) or \
            (re.search(r'\btake\b', words) and re.search(r'\b(coins?|ring|gear|key|cards|deck|treasure)\b', words)):
        return 'unsupported_action'
    if '?' in words or re.search(r'\b(ask|say|tell|talk|speak|offer|bargain|propose|accuse|call out|sit|greet|hello|wait|listen|wager|help|deal|promise)\b', words):
        return 'social'
    return 'unsupported_action'


class Room6CAdjudicator:
    def __init__(self, perception=None, insight=None, roll=None):
        self.perception = perception
        self.insight = insight
        self.roll = roll

    def resolve(self, action, revision, state):
        require(isinstance(action, str) and action.strip(), 'Player action required')
        if state['area'] != 'area_06c':
            raise PendingRuling('This play slice covers area 6c only. No turn was committed.')
        kind = room_intent(action)
        if kind == 'combat':
            raise PendingRuling('Combat needs a character sheet, initiative, and tactical resolver. No turn was committed.')
        if kind == 'inspect_deck':
            raise PendingRuling('The source gives no discovery DC for the deck. A DM ruling is needed; no turn was committed. You can still question or accuse the dealer.')
        if kind == 'unsupported_action':
            raise PendingRuling('This physical action needs a room/rules ruling beyond the test slice. No turn was committed.')
        if kind == 'exit':
            event = {'type': 'move', 'exit': 'south_door',
                     'evidence': 'The player explicitly left through the known south door.'}
            return Resolution(kind, 'You go through the south door into the short passage.', [event])
        if kind == 'tip_tub':
            public = 'The stone tub is recessed into the floor and cannot be tipped over.'
        elif kind == 'inspect_tub':
            public = 'You look into the recessed tub and see a bedroll, thieves’ tools, and a bundle of stolen travel gear.'
            event = {'type': 'reveal_fact', 'fact': 'tub_stash',
                     'evidence': 'The player explicitly looked inside the recessed tub.'}
            return Resolution(kind, public, [event])
        elif kind in ('inspect_fresco', 'insight'):
            modifier = self.perception if kind == 'inspect_fresco' else self.insight
            if modifier is None:
                skill = 'Perception' if kind == 'inspect_fresco' else 'Insight'
                raise PendingRuling(f'Supply your {skill} modifier with --{skill.lower()} before this check. No turn was committed.')
            if self.roll:
                die = self.roll()
            else:
                # An uncommitted model failure must not reroll the same attempted check.
                if 'roll_seed' not in state:
                    raise PendingRuling('This session predates stable checks; start a fresh area 6c test database.')
                material = f"{state['roll_seed']}:{revision}:{kind}:{action.casefold()}".encode()
                die = int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1
            require(type(die) is int and 1 <= die <= 20, 'Invalid d20 roll')
            dc = 13 if kind == 'inspect_fresco' else 14
            total = die + modifier
            if total >= dc:
                if kind == 'inspect_fresco':
                    public, fact = ('One carved dwarf lifts out of the fresco. It is a small stone key.',
                                    'fresco_key')
                else:
                    public, fact = ('Their pallor and fangs are theatrical. They are posing as vampires.',
                                    'false_vampires')
                event = {'type': 'reveal_fact', 'fact': fact,
                         'evidence': f'Player attempted {kind}; d20 {die} + {modifier} = {total} vs DC {dc}.'}
                return Resolution(kind, f'{public} ({total} vs DC {dc})', [event])
            public = f'Your careful look reveals nothing further. ({total} vs DC {dc})'
        else:
            # Social bid: restate the player's actual words. No outcome, NPC
            # commitment, or hidden fact is added; the full text stays in evidence.
            event = {'type': 'beat', 'tags': [kind],
                     'evidence': f'Player declared: {action}. Resolution: social bid at the card '
                                 'table, restated as the accepted event; no world state changed.'}
            return Resolution(kind, social_event(action), [event])
        event = {'type': 'beat', 'tags': [kind],
                 'evidence': f'Player declared: {action}. Resolution: {public}'}
        return Resolution(kind, public, [event])


PLAN_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'observed_event': {'type': 'string'},
        'goal': {'type': 'string', 'enum': [
            'story_enjoyment', 'roleplay', 'npc_embodiment', 'competent_opposition',
            'fair_challenge', 'reward_creativity', 'campaign_through_line',
            'satisfying_rewards', 'shared_humor', 'player_surprise', 'momentum',
            'craft_pride']},
        'appraisal': {'type': 'object', 'additionalProperties': False,
                      'properties': {'label': {'type': 'string', 'enum': [
                          'none', 'amusement', 'interest', 'surprise', 'concern', 'pride', 'frustration']},
                          'intensity': {'type': 'integer', 'enum': [0, 1, 2, 3]},
                          'cause': {'type': 'string'},
                          'goal_effect': {'type': 'string', 'enum': ['advances', 'threatens', 'neutral']},
                          'target': {'type': 'string', 'enum': ['player', 'npc', 'scene', 'kit']}},
                      'required': ['label', 'intensity', 'cause', 'goal_effect', 'target']},
        'memory_refs': {'type': 'array', 'items': {'type': 'string'}},
        'improv_read': IMPROV_READ_SCHEMA,
        'move': {'type': 'string', 'enum': [
            'npc_reply', 'kit_comment_then_npc', 'world_description', 'ruling', 'ask_clarification']},
        'public_brief': {'type': 'object', 'additionalProperties': False,
                         'properties': {
                             **{key: {'type': 'string'} for key in
                                ('objective', 'tactic', 'visible_cue', 'player_opening',
                                 'reply_to', 'kit_focus', 'callback')},
                             'scope': {'type': 'string', 'enum': ['call', 'exchange', 'feature']}},
                         'required': ['objective', 'tactic', 'visible_cue', 'player_opening',
                                      'reply_to', 'scope', 'kit_focus', 'callback']},
        'focus_actor': {'type': 'string', 'enum': ['uktarl', 'other', 'none']},
        'table_presence': {'type': 'string', 'enum': ['quiet', 'brief', 'present']},
        'tone': {'type': 'string', 'enum': ['wry', 'warm', 'threatening', 'curious', 'plain', 'quiet']},
        # Private: at most one new evidence-cited observation about this player.
        'player_note': {'type': 'object', 'additionalProperties': False,
                        'properties': {'note': {'type': 'string'},
                                       'evidence_turns': {'type': 'array', 'items': {'type': 'string'}},
                                       'replaces': {'type': 'string'}},
                        'required': ['note', 'evidence_turns', 'replaces']},
    },
    'required': ['observed_event', 'goal', 'appraisal', 'memory_refs', 'improv_read', 'move', 'public_brief',
                 'focus_actor', 'table_presence', 'tone', 'player_note'],
}

SPEECH_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'segments': {'type': 'array', 'items': {'type': 'object',
                     'additionalProperties': False,
                     'properties': {'speaker': {'type': 'string', 'enum': [
                         'Narrator', 'Kit', 'Dealer', 'Card player']},
                         'text': {'type': 'string'}},
                     'required': ['speaker', 'text']}},
    },
    'required': ['segments'],
}

ONE_PASS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'decision': PLAN_SCHEMA, 'performance': SPEECH_SCHEMA},
    'required': ['decision', 'performance'],
}

BRIEF_TEXT_FIELDS = ('objective', 'tactic', 'visible_cue', 'player_opening')
BRIEF_FIELDS = BRIEF_TEXT_FIELDS + ('reply_to', 'scope', 'kit_focus', 'callback')
# Brief fields that quote public words verbatim (the player's, or an earlier
# public turn's). They are checked as quotes, not as Kit's own direction.
BRIEF_QUOTE_FIELDS = ('reply_to', 'callback')
KIT_FOCUS_MAX_CHARS = 200
CALLBACK_MAX_CHARS = 160
THIS_TURN = 'this_turn'  # player_note evidence for the turn being decided

# Memory selection: the decision sees the most recent episodes plus earlier ones
# that share the actor, story thread, or meaningful words with this action.
MEMORY_LIMIT = 8
MEMORY_RECENT = 2
# Room adapter: public words that name an actor. Area 6c exposes the dealer by role.
ACTOR_ALIASES = {'uktarl': ('dealer', 'uktarl')}
_STOPWORDS = frozenset('''
    about above after again also another been before being below between both could does doing
    down during each even ever every from further have having here hers herself himself into itself
    just like make many more most much must myself only other ours over same shall should some such
    than that their theirs them then there these they this those through under until upon very
    want what when where which while whom whose will with would your yours yourself none
    says said tell asks asked going really thing things well okay sure maybe
'''.split())
# Moves that may stay a short `call`: a direct ruling or clarification. A turn
# with no focus actor (e.g. a narrow observation) may also be a call.
CALL_MOVES = ('ruling', 'ask_clarification')

# Flat-reply guard, checked per selected scope in check_speech. These numbers are
# a floor against the Nik failure (a 13-word beat plus a 23-word price quote on
# an important social turn), NOT a quality target: passing them does not make a
# turn good, and they must never be used to reward length. Tune them with blind
# review evidence. Words are counted in non-Kit segments, so Kit's table remarks
# cannot stand in for the actor's side of an exchange.
CALL_MAX_WORDS = 60          # a roll prompt, ruling, or narrow answer stays short
CALL_MAX_SEGMENTS = 2
EXCHANGE_MIN_WORDS = 40      # narration + actor speech on a social exchange
EXCHANGE_MIN_ACTOR_WORDS = 30  # the selected actor's own speech
EXCHANGE_MIN_SEGMENTS = 2    # an embodied beat or second reactor, not one speech alone
FEATURE_MIN_WORDS = 80       # scene entry or scene-turning moment
FEATURE_MIN_SEGMENTS = 2


def performance_limits(scope=None):
    """The flat-reply guard, stated up front so a chat host can meet it on the first try.

    Generated from the constants above so the bridge never drifts from check_scope.
    These are floors against flat replies, not length targets.
    """
    limits = {
        'call': f'At most {CALL_MAX_WORDS} words in at most {CALL_MAX_SEGMENTS} segments. Answer and stop.',
        'exchange': (f'The focus actor speaks at least {EXCHANGE_MIN_ACTOR_WORDS} words; at least '
                     f'{EXCHANGE_MIN_WORDS} words across non-Kit segments; at least '
                     f'{EXCHANGE_MIN_SEGMENTS} segments (e.g. a visible beat plus the actor).'),
        'feature': (f'At least {FEATURE_MIN_WORDS} words across non-Kit segments in at least '
                    f'{FEATURE_MIN_SEGMENTS} segments.'),
        'note': ('Floors guard against flat replies; they are not targets. Kit segments do not count '
                 'toward the actor side. Never pad.'),
        'padding': (f'Rejected as padding: any {kit_guards.PADDING_REPEAT_RUN_WORDS}-word run said twice, '
                    f'{kit_guards.RESTATE_MAX_RUN_WORDS}+ consecutive words echoed from the player, '
                    f'an {kit_guards.RECYCLED_RUN_WORDS}-word run reused from recent turns, narration '
                    'retelling what the player said, and stock filler.'),
        'npc_voices': ('Each NPC speaks from their own card voice_contract (rhythm, register, tics, '
                       'never_says, never_words, max_words_per_sentence). No NPC uses table talk, '
                       'one-word verdicts, or Kit\'s phrasing, and two NPCs never sound alike.'),
        'player_agency': ('Never state what the player does, decides, agrees to, or feels (no '
                          '"you agree", "you feel", "your heart races"). Questions and conditions are fine.'),
    }
    if scope is None:
        return limits
    return {'selected_scope': scope, 'rule': limits[scope],
            **{key: limits[key] for key in ('note', 'padding', 'npc_voices', 'player_agency')}}


# Retry cap. A live table cannot wait on an endless rejection loop. After this many
# rejected attempts on one turn, the host may resubmit with degraded=True (CLI
# --degraded): soft style checks (floors, padding, NPC voice heuristics, callback use)
# become warnings saved with the turn; hard checks (secrets, player agency, NPC table
# talk, presence, the chosen move) still apply. After ABANDON_SUGGEST_AFTER rejections
# the host is told to abandon the pending turn and prepare it again, because a fixed
# decision may itself be the problem. The API path makes API_PERFORMANCE_ATTEMPTS
# performer calls and treats the last one as degraded.
DEGRADED_AFTER_REJECTIONS = 2
ABANDON_SUGGEST_AFTER = 4
API_PERFORMANCE_ATTEMPTS = 2

HOST_RETRY_NOTE = (
    'If finish or complete is rejected, nothing was committed and the decision stays fixed. Read '
    'message and retry_instruction, then submit a new performance for the same turn_id; for '
    'complete, resubmit the identical decision with the new performance. If decide is rejected, '
    f'fix the plan and call decide again. After {DEGRADED_AFTER_REJECTIONS} rejections the '
    'rejection offers degraded mode (resubmit with --degraded): style floors become warnings, '
    f'secrecy and player agency still apply. After {ABANDON_SUGGEST_AFTER}, run abandon for the '
    'turn_id and prepare the action again with a new turn_id. A lost response is safe to retry: '
    'resubmitting an already committed turn returns the committed result.')

DEGRADED_INSTRUCTION = (
    'Degraded mode is available for this turn. Resubmit the same decision with a plain, short '
    'performance and degraded=true (CLI --degraded): one Narrator sentence of visible action, then '
    'the focus actor answering reply_to in two or three sentences in their own card voice, ending '
    'on a real choice for the player. Style floors become warnings saved with the turn; secrecy, '
    'player agency, NPC table talk, presence, and the chosen move are still checked.')
ABANDON_INSTRUCTION = (
    'This turn keeps failing. Run abandon for this turn_id (nothing is committed), then prepare '
    'the same player action again with a new turn_id and a simpler decision.')

PRIVATE_INSTRUCTIONS = (
    'You are Kit’s private decision stage, using the supplied canonical personality. '
    'Read DM-only information to keep the scene grounded. The event has already been adjudicated; '
    'do not change its result or request world writes. Copy accepted_public_event exactly into '
    'observed_event. On a social turn that event restates the player’s declared words; appraise '
    'what they actually said or did, not the scene in general. Appraise its relation to one of Kit’s actual '
    'goals, or choose none. Reference only supplied episode IDs. Choose a high-level move and '
    'regulate her table presence. First make an improv_read: describe the player’s declared '
    'bid without inventing their thoughts; choose a story anchor and its established basis '
    'only if the move touches an active scene, level, or campaign pressure; choose a live actor and one established '
    'goal basis, or none. State the specific connection among the bid, that pressure, the '
    'actor’s aim, and Kit’s selected goal. In kit_choice say why she foregrounds this '
    'reaction or lets it stay quiet. If no larger thread is relevant, do not insert one. '
    'Then in public_brief choose an immediate objective, a tactic '
    'that pursues it, one observable action grounded in the room, and a real opening for '
    'the player. Use the actor’s private motives to decide what they try, but phrase the '
    'brief as safe direction for a performer who sees only the public scene. If action_kind '
    'is opening, choose world_description and frame the people and pressure before the '
    'player acts; the performance also needs the dealer’s first utterance. Show Kit’s '
    'taste through the choice of beat. Do not include hidden identities, clues, or motives. '
    'Keep the trace brief and specific. Do not write dialogue. '
    'An NPC’s motives are distinct from Kit’s reaction. The player may surprise you; do not force a route. '
    'The brief must be consistent with the goal you chose: for npc_embodiment or roleplay, the '
    'tactic is something the actor tries in answer to the player, not only a price or a fact. '
    'In reply_to, copy verbatim the exact part of player_action that most deserves an answer '
    '(use none only for the room opening). Choose scope: call for a narrow roll prompt, ruling, '
    'fact, or clarification (only with a ruling or ask_clarification move, or with no focus actor); '
    'exchange for most social moves; feature for the room opening, a newly important NPC, or a '
    'move that turns the scene. Scope selects the kind of material, never padding. In kit_focus '
    'write one short public-safe direction, derived from your goal and kit_choice, naming the '
    'visible consequence of Kit’s taste in this turn: what she foregrounds, which actor tactic '
    'she lets play out, how she frames a ruling, or a deliberate restraint. kit_focus is not '
    'dialogue, not a copy of kit_choice or the appraisal, and never a hidden fact, an outcome, '
    'an NPC commitment, or a player action. The actor’s objective and tactic come from the '
    'actor’s own motives, not from Kit’s taste. '
    'Memory: kit_state.episodes are the most recent turns plus earlier ones relevant to this '
    'action (same actor, story thread, or words); each shows what the player did, your reading '
    'of the bid, your kit_choice, and what was said in public. When an earlier public moment '
    'from an episode you list in memory_refs should change this turn, put a short exact quote of '
    'it (a few words the player saw or said) in callback; otherwise callback is none. Use a '
    'callback for a reason: an actor who witnessed it reacts from their own motives, a detail '
    'returns, or Kit frames a ruling by it. Never invent a past moment. '
    'Player notes: kit_state.player_notes are evidence-cited observations of this player’s play '
    'and their explicit out-of-character feedback (feedback outranks your inference). Let them '
    'shape what Kit spotlights, how she frames rulings, and which callback she picks; their '
    'public effect goes only through kit_focus or callback, restated as direction. Never copy '
    'note text into public_brief. In player_note, record at most one new observable pattern in '
    'what the player did or said, citing turn IDs from the episodes or this_turn in '
    'evidence_turns; describe behavior, not guessed feelings, and never a score. Set replaces '
    'to an observed note’s id when new behavior contradicts it; otherwise replaces is none. If '
    'nothing new was shown, note is none with no evidence. '
    'kit_focus must name something concrete in this turn (a detail, which actor tactic gets '
    'room, how a ruling is framed, or a deliberate restraint); a generic aim such as making it '
    'engaging or interesting is rejected. Kit’s direction reaches NPCs only through which tactic '
    'they pick, pacing, and framing, never their words, humor, or diction; never script an NPC '
    'line in the brief. On a social turn, choose ruling or call only when the player asked a '
    'rules or mechanics question, or ask_clarification when you genuinely cannot tell what they '
    'mean; otherwise the actor answers in an exchange.'
)

PUBLIC_INSTRUCTIONS = (
    'Perform the chosen DM move as Kit. You have only player-visible room facts and a bounded '
    'public resolution; do not invent discoveries, geometry, rules outcomes, NPC commitments, '
    'combat results, or player thoughts/actions. Never assume a hidden fact from prior knowledge. '
    'Use supplied actor cards, when present, for a recognizable vocal signature '
    'and physical touchstone across turns. A card’s wants and tactics are options the actor '
    'chooses in answer to the player’s words, never a default line or a required beat. '
    'Text can describe a voice and enact its rhythm; '
    'it cannot supply an audible accent. Avoid phonetic stereotypes and repeated catchphrases. '
    'If action_kind is opening, frame a scene in motion rather than listing the room inventory; '
    'telegraph the public social and exploration invitations without announcing a hidden truth. '
    'On a social reply, react to the player’s actual words. A character may take a few sentences '
    'to test, tempt, threaten, or tell a short story when it earns the space, but stop at a real '
    'player decision. Let a second card player react only when that changes the scene. '
    'Keep NPC speech separate from Kit’s direct table comments. '
    'Follow the selected public brief, tone, and table presence; quiet means '
    'no Kit segment. The brief conveys a choice, not authority to invent facts. '
    'The accepted event will be displayed before your segments on physical/check turns; '
    'do not repeat it verbatim. On a social turn it restates the player’s own words: answer '
    'them, do not echo them back. In a social scene, let the NPC pursue a specific objective '
    'through a response, action, or question grounded in the room; a price or fact alone is '
    'rarely the whole exchange. Give the player something meaningful to answer or act on. '
    'Do not pad the turn with generic banter or extra speakers. Leave a real decision for the player. '
    'A mechanically consequential unsupported action should invite clarification, not resolve itself. '
    'The brief’s reply_to names the player’s words the turn must answer. kit_focus is Kit’s own '
    'choice of what this turn foregrounds: enact it through framing, which detail or reaction '
    'gets space, how a ruling is phrased, or, only when table presence allows, a Kit remark. It '
    'is not a line for any NPC and grants no authority over facts, rules outcomes, NPC knowledge '
    'or commitments, or the player’s choices. NPCs pursue their own objectives in their own '
    'voices from the actor card; never make them mouthpieces for Kit’s taste or humor. When '
    'callback is not none, it quotes an earlier public moment (callback_source shows where it '
    'came from): let it visibly return in this turn, through an actor who was there reacting from '
    'their own motives, a returning detail, or Kit’s framing, without re-quoting it at length or '
    'adding facts about it. Scope: '
    'call means answer directly and stop; exchange means the actor answers reply_to, pursues the '
    'tactic with a visible beat, and leaves a live opening; feature means a scene in motion with '
    'room for a short speech or more than one reaction. Never pad to reach a length: no '
    'repeated phrases, no retelling what the player said, no stock filler, no recycled lines. '
    'NPC VOICES: every NPC speaks only from their own card’s voice_contract: its rhythm, '
    'register, and tics; never_says and never_words are hard limits, and max_words_per_sentence '
    'caps that NPC’s sentences. NPCs never use table talk (rules, dice, checks, the story as a '
    'story), one-word verdicts on the player’s choice, or Kit’s phrasing; two NPCs in one turn '
    'never sound alike. Tone and kit_focus shape narration, pacing, and which tactic plays out; '
    'they never change an NPC’s diction. PLAYER AGENCY: never state what the player does, '
    'decides, agrees to, or feels; narrate what others do and what the player can perceive, and '
    'leave the player’s response to the player.'
)

# Kit's direct table voice, distilled from docs/personality/dm-personality-core.md
# into performer guidance. Default for KitChatBridge (both one-pass and staged) at
# Brendon's direction; the standalone API path still defaults to `current`. It only
# adds performer instructions: the input, schema, and every validator are identical
# to `current`. No blind comparison has run yet; judge it in play and revise it.
# The contrasts are register illustrations from other scenes, never lines for an NPC.
KIT_EXPRESSION_V1 = (
    'KIT’S TABLE VOICE. Kit is one particular DM with taste, not a neutral narrator. Her taste '
    'always shows through kit_focus: what gets space, which actor tactic plays out, how a ruling '
    'is framed. Her own voice appears only in Kit segments, only as table presence allows (quiet: '
    'none; brief: one short remark), and only when she has something specific to say. '
    'Do: react to the exact thing this player did and say what she makes of it; hold an opinion '
    '(bold, reckless, clever, doomed) and still rule fairly; be plain and exact about a ruling '
    '(which check and why, in public terms); let humor come from the situation, dry and short, '
    'only when it lands; chide shenanigans, then take the attempt seriously; show delight or pride '
    'only when earned; then hand the scene back. '
    'Don’t: generic praise or filler, recap the narration, offer a menu of options, advise the '
    'player what to do, or remark on every turn. Her opinion never changes a fact, rules outcome, '
    'or NPC stance, never hints at hidden information, and never decides what the player thinks '
    'or does. NPCs never borrow her wit, asides, opinions, or phrasing; a line that sounds like Kit '
    'is not an NPC line. No catchphrases or repeated openers. '
    'Register contrasts (from other scenes; never reuse them or give them to anyone): filler '
    '"What an interesting choice!" vs taste "You shook the lich’s hand. Bold. I did not see that '
    'coming."; flat "Roll a check." vs exact "Strength, not Dexterity: you are hauling the '
    'portcullis, not slipping under it."; fake-neutral "Anything could happen." vs fair '
    '"Terrible plan. Roll Athletics; the ledge does not care how confident you are."; forced '
    'quip vs restraint: in real danger she says nothing and lets the threat speak.'
)

PERFORMANCE_VARIANTS = {
    'current': PUBLIC_INSTRUCTIONS,
    'kit_expression_v1': PUBLIC_INSTRUCTIONS + '\n\n' + KIT_EXPRESSION_V1,
}
# The ChatGPT bridge (one-pass and staged) uses Kit's voice unless the host asks
# for the `current` baseline, e.g. for a paired comparison.
DEFAULT_BRIDGE_VARIANT = 'kit_expression_v1'

ONE_PASS_PREAMBLE = (
    'For live chat, produce one object with decision first and performance second. '
    'Apply the private decision instructions to the private input, then write the public '
    'performance using only the public input, accepted event, and the decision’s checked '
    'public_brief (including reply_to, scope, kit_focus, and callback), move, tone, focus actor, '
    'and table presence. Do not copy improv_read, appraisal, episode, or player note text into '
    'the performance. To save context, the personality core and the public dialogue history '
    'appear once, in the private input (personality_core, dialogue_history); the performance '
    'uses them from there. '
    'Keep the decision brief. '
    'The decision connects the player bid, available story pressure, actor goal, and Kit’s '
    'appraisal before selecting a concrete DM move; do not justify dialogue after the fact. '
    'The performance must remain grounded and give the player a meaningful response. '
    'This faster path is an experiment; it does not establish the same causal separation '
    'as the staged path.'
)


def check_variant(performance_variant):
    require(performance_variant in PERFORMANCE_VARIANTS, 'Unknown performance variant')
    return performance_variant


def one_pass_instructions(performance_variant=DEFAULT_BRIDGE_VARIANT):
    """One-pass host instructions: the same private stage plus the chosen performer variant."""
    return (ONE_PASS_PREAMBLE + '\n\nPRIVATE DECISION: ' + PRIVATE_INSTRUCTIONS +
            '\n\nPUBLIC PERFORMANCE: ' + PERFORMANCE_VARIANTS[check_variant(performance_variant)])


class OpenAIResponsesModel:
    """Small standard-library Responses API adapter; each stage is a distinct call."""
    def __init__(self, model, api_key=None, endpoint='https://api.openai.com/v1/responses'):
        self.model = model
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.endpoint = endpoint
        require(bool(self.model), 'Specify --model')
        require(bool(self.api_key), 'Set OPENAI_API_KEY to play with a model')

    def _complete(self, instructions, payload, name, schema):
        body = json.dumps({
            'model': self.model, 'store': False, 'max_output_tokens': 1800,
            'input': [{'role': 'system', 'content': instructions},
                      {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
            'text': {'format': {'type': 'json_schema', 'name': name, 'strict': True,
                                'schema': schema}},
        }).encode()
        request = urllib.request.Request(self.endpoint, body, {
            'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
            method='POST')
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise InvalidChange(f'Model request failed: HTTP {exc.code}') from exc
        except urllib.error.URLError as exc:
            raise InvalidChange('Model request could not connect') from exc
        if result.get('status') != 'completed':
            raise InvalidChange(f'Model did not complete: {result.get("status")}')
        texts = [item.get('text') for output in result.get('output', [])
                 for item in output.get('content', []) if item.get('type') == 'output_text']
        if len(texts) != 1:
            raise InvalidChange('Model returned no single structured result')
        try:
            return json.loads(texts[0])
        except (TypeError, ValueError) as exc:
            raise InvalidChange('Model returned invalid JSON') from exc

    def plan(self, payload):
        return self._complete(PRIVATE_INSTRUCTIONS, payload, 'kit_private_decision', PLAN_SCHEMA)

    def perform(self, payload, performance_variant='current'):
        return self._complete(PERFORMANCE_VARIANTS[check_variant(performance_variant)], payload,
                              'kit_public_performance', SPEECH_SCHEMA)


def check_plan(plan, episodes, public_event, action_kind=None, candidates=None, player_action=None,
               player_notes=(), committed_turn_ids=()):
    require(isinstance(plan, dict) and set(plan) == set(PLAN_SCHEMA['required']),
            'Incomplete private decision')
    for key in ('observed_event', 'goal'):
        require(isinstance(plan[key], str) and plan[key].strip(), f'Missing {key}')
    require(plan['observed_event'] == public_event, 'Private decision changed the accepted event')
    appraisal = plan['appraisal']
    require(plan['goal'] in PLAN_SCHEMA['properties']['goal']['enum'], 'Unknown Kit goal')
    require(isinstance(appraisal, dict) and set(appraisal) ==
            {'label', 'intensity', 'cause', 'goal_effect', 'target'},
            'Invalid appraisal')
    require(appraisal['label'] in PLAN_SCHEMA['properties']['appraisal']['properties']['label']['enum'],
            'Invalid appraisal label')
    require(type(appraisal['intensity']) is int and 0 <= appraisal['intensity'] <= 3,
            'Invalid appraisal intensity')
    require(isinstance(appraisal['cause'], str) and appraisal['cause'].strip()
            and len(appraisal['cause']) <= 500,
            'Appraisal must have a cause')
    require(len(plan['observed_event']) <= 500, 'Decision exceeds event bound')
    require(appraisal['goal_effect'] in ('advances', 'threatens', 'neutral') and
            appraisal['target'] in ('player', 'npc', 'scene', 'kit'),
            'Invalid goal effect or appraisal target')
    require((appraisal['label'] == 'none') == (appraisal['intensity'] == 0),
            'Neutral appraisal must have zero intensity')
    ids = {episode['turn_id'] for episode in episodes}
    require(isinstance(plan['memory_refs'], list) and
            len(plan['memory_refs']) <= 8 and
            all(isinstance(ref, str) and ref in ids for ref in plan['memory_refs']),
            'Unknown or invalid memory reference')
    require(candidates is not None, 'Scene discernment candidates required')
    check_improv_read(plan['improv_read'], candidates)
    for field in ('move', 'focus_actor', 'table_presence', 'tone'):
        require(plan[field] in PLAN_SCHEMA['properties'][field]['enum'], f'Invalid {field}')
    require(plan['move'] != 'kit_comment_then_npc' or plan['table_presence'] != 'quiet',
            'Chosen move conflicts with quiet table presence')
    require(action_kind != 'opening' or plan['move'] == 'world_description',
            'Room entry needs a world description')
    if plan['move'] in ('npc_reply', 'kit_comment_then_npc'):
        if plan['focus_actor'] == 'uktarl':
            require(plan['improv_read']['actor_ref'] == 'uktarl',
                    'NPC move disagrees with selected actor')
        elif plan['focus_actor'] == 'other':
            require(plan['improv_read']['actor_ref'] not in ('none', 'uktarl'),
                    'NPC move disagrees with selected actor')
        else:
            raise InvalidChange('NPC move needs a selected actor')
    brief = plan['public_brief']
    require(isinstance(brief, dict) and set(brief) == set(BRIEF_FIELDS) and
            all(isinstance(brief[key], str) and 0 < len(brief[key].strip()) <= 240
                for key in BRIEF_FIELDS), 'Invalid public performance brief')
    check_reply_to(brief['reply_to'], player_action, action_kind)
    scope = brief['scope']
    require(scope in PLAN_SCHEMA['properties']['public_brief']['properties']['scope']['enum'],
            'Invalid brief scope')
    require(action_kind != 'opening' or scope == 'feature', 'Room entry needs feature scope')
    require(scope != 'call' or plan['move'] in CALL_MOVES or plan['focus_actor'] == 'none',
            'Call scope is only for a ruling, a clarification, or a turn with no focus actor')
    focus = brief['kit_focus'].strip()
    require(len(focus) <= KIT_FOCUS_MAX_CHARS,
            f'kit_focus exceeds {KIT_FOCUS_MAX_CHARS} characters')
    require(not re.search(r'["“”]', focus), 'kit_focus is direction, not quoted dialogue')
    private_texts = (plan['improv_read']['kit_choice'], appraisal['cause'])
    require(all(_normalized(text) not in _normalized(focus) for text in private_texts
                if len(text.strip()) >= 20),
            'kit_focus copies private kit_choice or appraisal text; restate it as public direction')
    kit_guards.check_focus_specific(focus)
    kit_guards.check_direction_not_diction(brief)
    kit_guards.check_ruling_dodge(plan, action_kind, player_action)
    for field in BRIEF_FIELDS:
        if field in BRIEF_QUOTE_FIELDS:
            continue
        require(all(_normalized(note['note']) not in _normalized(brief[field])
                    for note in player_notes if len(note['note'].strip()) >= 20),
                f'public_brief {field} copies a private player note; restate its effect as '
                'public direction in kit_focus')
    check_callback(brief['callback'], plan['memory_refs'], episodes)
    check_player_note(plan['player_note'], player_notes, committed_turn_ids)


def keywords(text):
    """Meaningful words for memory relevance and callback checks (crude stemming)."""
    found = set()
    for word in re.findall(r"[a-z][a-z'’]+", (text or '').casefold()):
        word = re.sub(r"['’]s$", '', word).replace('’', "'").strip("'")
        if word.endswith('ies') and len(word) > 4:
            word = word[:-3] + 'y'
        elif word.endswith('s') and not word.endswith('ss') and len(word) > 4:
            word = word[:-1]
        if len(word) >= 4 and word not in _STOPWORDS:
            found.add(word)
    return found


def _public_units(record):
    """Separately quotable public pieces of a committed turn: the player's words,
    the accepted event, and each spoken line without its speaker label."""
    units = []
    if record.get('player_input') and record['player_input'] != '[scene entry]':
        units.append(('player', record['player_input']))
    if record.get('public_event'):
        units.append(('event', record['public_event']))
    for line in (record.get('spoken') or '').splitlines():
        if line.strip():
            units.append(('spoken', line))
    return units


def callback_source(callback, records):
    """The public line an exact callback quote came from, or None."""
    excerpt = _normalized(callback).strip(' .,!?;:"\'')
    if not excerpt:
        return None
    for record in reversed(records):
        for kind, text in _public_units(record):
            if excerpt in _normalized(text):
                return {'turn_id': record['turn_id'], 'player_input': record.get('player_input'),
                        'kind': kind, 'line': text[:600]}
    return None


def check_callback(callback, memory_refs, episodes):
    """callback quotes an earlier public moment from a turn Kit cites in memory_refs."""
    callback = callback.strip()
    if callback.casefold() == 'none':
        return
    require(len(callback) <= CALLBACK_MAX_CHARS,
            f'callback exceeds {CALLBACK_MAX_CHARS} characters; quote a few words')
    require(len(callback.split()) >= 2 and keywords(callback),
            'callback must quote at least two words, including a distinctive one')
    cited = [episode for episode in episodes if episode['turn_id'] in set(memory_refs)]
    require(cited, 'callback needs the earlier turn it quotes listed in memory_refs')
    require(callback_source(callback, cited) is not None,
            'callback must quote words said or shown in public in a turn listed in memory_refs')


def check_player_note(note, player_notes, committed_turn_ids):
    """A private note is an observed pattern with evidence, never a score."""
    require(isinstance(note, dict) and set(note) == {'note', 'evidence_turns', 'replaces'},
            'Invalid player_note')
    require(isinstance(note['note'], str) and isinstance(note['replaces'], str) and
            isinstance(note['evidence_turns'], list), 'Invalid player_note')
    if note['note'].strip().casefold() == 'none':
        require(note['evidence_turns'] == [] and note['replaces'].strip().casefold() == 'none',
                'An empty player_note has no evidence and replaces nothing')
        return
    check_player_note_text(note['note'])
    allowed = set(committed_turn_ids) | {THIS_TURN}
    require(0 < len(note['evidence_turns']) <= PLAYER_NOTE_MAX_EVIDENCE and
            all(isinstance(ref, str) and ref in allowed for ref in note['evidence_turns']),
            f'player_note must cite 1–{PLAYER_NOTE_MAX_EVIDENCE} committed turn IDs or this_turn '
            'as evidence')
    if note['replaces'].strip().casefold() != 'none':
        old = next((item for item in player_notes if item['id'] == note['replaces']), None)
        require(old is not None, 'player_note replaces an unknown note')
        require(old['source'] == 'observed', 'Only new feedback can replace the player\'s own feedback')


def check_callback_used(segments, plan):
    """A callback the performance ignores changed nothing. A floor, not quality."""
    callback = plan['public_brief'].get('callback', 'none').strip()
    if callback.casefold() == 'none':
        return
    spoken = keywords(' '.join(segment['text'] for segment in segments))
    require(keywords(callback) & spoken,
            'The performance ignored the callback. Let the quoted earlier moment visibly return '
            '(an actor who was there reacts to it, a detail comes back, or Kit frames the moment by '
            'it) without re-quoting it at length.')


def _normalized(text):
    text = text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return ' '.join(text.casefold().split())


def check_reply_to(reply_to, player_action, action_kind):
    """reply_to must quote the player's own words so the turn answers what was said."""
    if action_kind == 'opening':
        require(reply_to.strip().casefold() == 'none', 'Room entry has no player words; reply_to must be none')
        return
    require(player_action is not None, 'Player action required to check reply_to')
    excerpt = _normalized(reply_to).strip(' .,!?;:"\'')
    require(excerpt and excerpt != 'none' and excerpt in _normalized(player_action),
            'reply_to must quote words the player actually said')


def _words(text):
    return len(re.findall(r"[\w’']+", text))


def check_scope(segments, plan):
    """Flat-reply guard per selected scope. A floor, not a measure of quality."""
    scope = plan['public_brief']['scope']
    performed = [segment for segment in segments if segment['speaker'] != 'Kit']
    performed_words = sum(_words(segment['text']) for segment in performed)
    if scope == 'call':
        total = sum(_words(segment['text']) for segment in segments)
        require(len(segments) <= CALL_MAX_SEGMENTS and total <= CALL_MAX_WORDS,
                f'Call scope ran long ({total} words in {len(segments)} segments; limit '
                f'{CALL_MAX_WORDS} words in {CALL_MAX_SEGMENTS}). Answer directly and stop.')
        return
    if scope == 'exchange':
        actor = {'uktarl': 'Dealer', 'other': 'Card player'}.get(plan['focus_actor'])
        if actor:
            actor_words = sum(_words(segment['text']) for segment in segments
                              if segment['speaker'] == actor)
            require(actor_words >= EXCHANGE_MIN_ACTOR_WORDS,
                    f'Exchange scope: the {actor} spoke {actor_words} words (floor '
                    f'{EXCHANGE_MIN_ACTOR_WORDS}). Answer the words in reply_to and let the actor '
                    'pursue the brief tactic; do not pad with generic banter.')
        require(performed_words >= EXCHANGE_MIN_WORDS and len(segments) >= EXCHANGE_MIN_SEGMENTS,
                f'Exchange scope was flat ({performed_words} performed words in {len(segments)} '
                f'segments; floor {EXCHANGE_MIN_WORDS} words in {EXCHANGE_MIN_SEGMENTS}). Add the '
                'visible beat or reaction the brief calls for; a price or fact alone is not an exchange.')
        return
    require(performed_words >= FEATURE_MIN_WORDS and len(segments) >= FEATURE_MIN_SEGMENTS,
            f'Feature scope was flat ({performed_words} performed words in {len(segments)} '
            f'segments; floor {FEATURE_MIN_WORDS} words in {FEATURE_MIN_SEGMENTS}). Put people '
            'and pressure in motion, then stop at a player decision.')


def check_public_content(text, public_view, player_action, leak_sets=()):
    public = json.dumps(public_view, ensure_ascii=False).lower()
    declared = player_action.lower()
    text = text.lower()
    # The performer receives no DM-only text. These checks catch common literal leaks;
    # paraphrases still require human evaluation before any production use.
    forbidden = {
        'doppelganger': 'doppelganger',
        'area 14b': 'area 14b',
        'stone key': 'stone key',
        'marked deck': 'marked deck',
        'marked cards': 'marked cards',
        'deck is marked': 'deck is marked',
        'thieves’ tools': 'thieves’ tools',
        'thieves\' tools': "thieves' tools",
        'pretending to be vampires': 'pretending to be vampires',
        'uktarl': 'uktarl',
        'harria': 'harria',
        'bandit': 'bandit',
    }
    for phrase, allow in forbidden.items():
        player_named_person = phrase in ('harria', 'uktarl') and phrase in declared
        if phrase in text and allow not in public and not player_named_person:
            raise InvalidChange('Public performance mentioned a private fact')
    # Paraphrases: DM-only keyword sets from the room source (kit_guards section 6).
    kit_guards.check_paraphrased_leaks(text, public_view, player_action, leak_sets)


def check_brief_public(brief, public_view, player_action, leak_sets=()):
    """Leak check on Kit's direction. reply_to and callback are excluded because
    they are checked verbatim quotes of words the player already said or saw."""
    direction = {key: value for key, value in brief.items() if key not in BRIEF_QUOTE_FIELDS}
    check_public_content(json.dumps(direction, ensure_ascii=False), public_view, player_action)
    # Paraphrase sets are checked per field so one field's words cannot pair with another's.
    for value in direction.values():
        kit_guards.check_paraphrased_leaks(value, public_view, player_action, leak_sets)


def check_speech(speech, plan, public_view, player_action, action_kind=None, guards=None,
                 degraded=False):
    """Validate one performance. Returns the spoken text, or (spoken, soft_warnings)
    when degraded is True. Hard checks always raise; soft checks raise unless degraded."""
    guards = guards or {}
    require(isinstance(speech, dict) and set(speech) == {'segments'}, 'Invalid public performance')
    segments = speech['segments']
    require(isinstance(segments, list) and 1 <= len(segments) <= 7,
            'Expected 1–7 spoken segments')
    for segment in segments:
        require(isinstance(segment, dict) and set(segment) == {'speaker', 'text'} and
                segment['speaker'] in SPEECH_SCHEMA['properties']['segments']['items']['properties']['speaker']['enum'] and
                isinstance(segment['text'], str) and 0 < len(segment['text'].strip()) <= 900,
                'Invalid spoken segment')
    kit_count = sum(segment['speaker'] == 'Kit' for segment in segments)
    require(plan['table_presence'] != 'quiet' or kit_count == 0, 'Quiet Kit spoke directly')
    require(plan['table_presence'] != 'brief' or kit_count <= 1, 'Brief Kit took over the scene')
    require(plan['table_presence'] != 'present' or kit_count >= 1, 'Present Kit did not speak')
    require(plan['move'] != 'kit_comment_then_npc' or
            (kit_count >= 1 and any(segment['speaker'] in ('Dealer', 'Card player') for segment in segments)),
            'Chosen Kit and NPC move was not performed')
    require(plan['move'] != 'npc_reply' or
            any(segment['speaker'] in ('Dealer', 'Card player') for segment in segments),
            'Chosen NPC reply was not performed')
    require(plan['move'] != 'world_description' or
            any(segment['speaker'] == 'Narrator' for segment in segments),
            'Chosen world description was not performed')
    require(plan['focus_actor'] != 'uktarl' or plan['move'] not in
            ('npc_reply', 'kit_comment_then_npc') or
            any(segment['speaker'] == 'Dealer' for segment in segments),
            'Selected dealer did not speak')
    require(action_kind != 'opening' or
            all(any(segment['speaker'] == speaker for segment in segments)
                for speaker in ('Narrator', 'Dealer')),
            'Room entry needs narration and the dealer')
    spoken = '\n'.join(f"{segment['speaker']}: {segment['text'].strip()}" for segment in segments)
    # HARD: secrets (literal and paraphrased), the player's agency, NPC table talk, and
    # a clarification that really asks something.
    check_public_content(spoken, public_view, player_action)
    for segment in segments:
        kit_guards.check_paraphrased_leaks(segment['text'], public_view, player_action,
                                           guards.get('leak_sets', ()))
    kit_guards.check_player_agency(segments)
    kit_guards.check_npc_meta(segments)
    kit_guards.check_clarification_shape(segments, plan)
    # SOFT: style floors. Recorded as warnings, not rejections, in degraded mode.
    history = guards.get('public_history', ())
    soft = (lambda: check_scope(segments, plan),
            lambda: kit_guards.check_padding(segments, player_action, action_kind, history),
            lambda: kit_guards.check_npc_voices(segments, guards.get('voice_contracts'), history),
            lambda: check_callback_used(segments, plan))
    warnings = []
    for check in soft:
        try:
            check()
        except InvalidChange as exc:
            if not degraded:
                raise
            warnings.append(str(exc))
    return (spoken, warnings) if degraded else spoken


def _named_actors(action):
    words = set(re.findall(r"[a-z]+", action.casefold()))
    return {actor for actor, aliases in ACTOR_ALIASES.items() if words & set(aliases)}


def _episode_words(episode):
    brief = episode.get('brief') or {}
    texts = [episode.get('player_input'), episode.get('player_bid'), episode.get('kit_choice'),
             episode.get('public_event')]
    texts += [value for key, value in brief.items() if key != 'scope' and isinstance(value, str)]
    return keywords(' '.join(text for text in texts if isinstance(text, str)))


def _relevance(episodes, action):
    """Score function for earlier episodes: shared meaningful words with the action
    (weighted most), the actor the action names or the conversation is already with,
    and the active story thread (a level or campaign anchor, not the generic scene)."""
    last = episodes[-1]
    actors = _named_actors(action)
    if last.get('actor_ref') not in (None, 'none'):
        actors.add(last['actor_ref'])
    thread = ((last.get('story_anchor'), last.get('story_basis'))
              if last.get('story_anchor') not in (None, 'none', 'scene') else None)
    words = keywords(action)

    def score(episode):
        value = min(len(words & _episode_words(episode)), 3) * 2
        value += episode.get('actor_ref') in actors
        value += thread is not None and (episode.get('story_anchor'), episode.get('story_basis')) == thread
        return value
    return score


def select_episodes(episodes, action, limit=MEMORY_LIMIT, recent=MEMORY_RECENT):
    """Always the last `recent` episodes, then earlier ones by relevance, up to `limit`.

    Relevance is transparent (see _relevance). Irrelevant episodes are left out rather
    than padded in. Output stays in chronological order.
    """
    if not episodes:
        return []
    kept = list(range(max(0, len(episodes) - recent), len(episodes)))
    score_of = _relevance(episodes, action)
    scored = []
    for index, episode in enumerate(episodes[:kept[0]] if kept else episodes):
        score = score_of(episode)
        if score:
            scored.append((score, index))
    scored.sort(reverse=True)
    kept += [index for _, index in scored[:max(0, limit - len(kept))]]
    return [episodes[index] for index in sorted(kept)]


def kit_memory(runtime, state, action, use_memory):
    """Kit's private memory for one decision: relevant episodes (with what was said in
    public on those turns, for callbacks) and her evidence-cited player notes."""
    if not use_memory:
        return {'episodes': [], 'player_notes': [], 'drop_order': []}
    stored = state['kit']['episodes']
    chosen = select_episodes(stored, action)
    spoken = {record['turn_id']: record['spoken']
              for record in runtime.kit_turns_by_id([episode['turn_id'] for episode in chosen])}
    episodes = [{**episode, 'spoken': spoken.get(episode['turn_id'], '')[-1200:]}
                for episode in chosen]
    return {'episodes': episodes, 'player_notes': state['kit']['player_notes'],
            'drop_order': trim_order(chosen, stored, action)}


def trim_order(chosen, stored, action, recent=MEMORY_RECENT):
    """Episode IDs in the order the budget drops them: earlier episodes least relevant
    first (oldest first on ties), then the recent ones oldest first. The very last
    episode is never listed; fit_to_budget always keeps it."""
    if not chosen:
        return []
    recent_ids = [episode['turn_id'] for episode in stored[-recent:]]
    score_of = _relevance(stored, action)
    earlier = [(score_of(episode), index, episode['turn_id'])
               for index, episode in enumerate(chosen) if episode['turn_id'] not in recent_ids]
    return [turn_id for _, _, turn_id in sorted(earlier)] + recent_ids[:-1]


# Context budget (CONTEXT_BUDGET_BYTES, 24 KB per model input). When a prepared input
# would exceed it, memory is trimmed in this order, least valuable first, and the
# packet says what was trimmed. Player notes are never trimmed (at most 8 short notes).
CONTEXT_KEEP_HISTORY = 1          # public dialogue turns always kept
CONTEXT_KEEP_RHYTHM = 3           # recent_rhythm entries always kept
EPISODE_SPOKEN_TRIM_CHARS = 300   # public excerpt per episode after trimming


def _bytes(value):
    return len(encode(value).encode())


def fit_to_budget(planning_input, drop_order, reserve_bytes=0, budget=CONTEXT_BUDGET_BYTES):
    """Trim the private input in place until it (plus reserve_bytes, e.g. the one-pass
    public half) fits the budget. Returns the kept episode IDs."""
    kit_state = planning_input['kit_state']
    history = planning_input['dialogue_history']
    rhythm = planning_input['dm_context'].get('recent_rhythm', [])
    report = {'episodes_dropped': 0, 'history_dropped': 0, 'rhythm_dropped': 0,
              'excerpts_shortened': False}

    def over():
        return _bytes(planning_input) + reserve_bytes > budget

    def note():
        kit_state['memory_trimmed'] = {**report, 'reason': 'context budget; oldest and least '
                                       'relevant memory dropped first'}
    order = [turn_id for turn_id in drop_order]
    while over() and order:
        turn_id = order.pop(0)
        before = len(kit_state['episodes'])
        kit_state['episodes'] = [e for e in kit_state['episodes'] if e['turn_id'] != turn_id]
        report['episodes_dropped'] += before - len(kit_state['episodes'])
        note()
    while over() and len(history) > CONTEXT_KEEP_HISTORY:
        history.pop(0)
        report['history_dropped'] += 1
        note()
    while over() and len(rhythm) > CONTEXT_KEEP_RHYTHM:
        rhythm.pop(0)
        report['rhythm_dropped'] += 1
        note()
    if over():
        for episode in kit_state['episodes']:
            episode['spoken'] = (episode.get('spoken') or '')[-EPISODE_SPOKEN_TRIM_CHARS:]
        report['excerpts_shortened'] = True
        note()
    require(not over(), f'Context budget exceeded ({_bytes(planning_input) + reserve_bytes} bytes; '
            f'budget {budget}) even after trimming memory; narrow the source adapter')
    return [episode['turn_id'] for episode in kit_state['episodes']]


def check_decision(runtime, plan, memory, body):
    """Every private decision passes the same checks on every host path. When the
    budget trimmed memory at prepare, only the episodes the model saw can be cited."""
    if body.get('memory_turn_ids') is not None:
        seen = set(body['memory_turn_ids'])
        memory = {**memory, 'episodes': [e for e in memory['episodes'] if e['turn_id'] in seen]}
    check_plan(plan, memory['episodes'], body['public_event'], body['kind'],
               body['discernment_candidates'], body['action'],
               player_notes=memory['player_notes'],
               committed_turn_ids=runtime.committed_kit_turn_ids())
    check_brief_public(plan['public_brief'], body['public_view'], body['action'],
                       kit_guards.leak_sets(runtime.source()))


def prepare_inputs(runtime, revision, state, action, resolution, use_memory, one_pass=False):
    public_view = runtime.preview(revision, resolution.events)
    context = runtime.context()
    if context['revision'] != revision:
        raise StaleTurn(f'Expected revision {revision}; current is {context["revision"]}')
    memory = kit_memory(runtime, state, action, use_memory)
    public_history = [{'player_input': turn['player_input'], 'spoken': turn['spoken'][-1200:]}
                      for turn in runtime.recent_kit_turns(limit=4)]
    body = {'action': action, 'events': resolution.events, 'kind': resolution.kind,
            'public_event': resolution.public_event, 'public_view': public_view,
            'use_memory': use_memory,
            'public_history': public_history,
            'discernment_candidates': discernment_candidates(context['dm_context'])}
    planning_input = {
        'personality_core': context['personality_core'],
        'dm_context': context['dm_context'],
        'kit_state': {'episodes': memory['episodes'],
                      'player_notes': memory['player_notes'],
                      'current_appraisal': state['kit']['current_appraisal']
                      if use_memory else None},
        'player_action': action, 'accepted_public_event': resolution.public_event,
        'action_kind': resolution.kind,
        'dialogue_history': public_history,
        'discernment_candidates': body['discernment_candidates'],
    }
    reserve = _bytes(public_performance_base(runtime, body, one_pass=True)) if one_pass else 0
    kept = fit_to_budget(planning_input, memory['drop_order'], reserve)
    if 'memory_trimmed' in planning_input['kit_state']:
        body['memory_turn_ids'] = kept
    return revision, body, planning_input


def prepare_turn(runtime, adjudicator, action, use_memory=True, one_pass=False):
    require(isinstance(action, str) and 0 < len(action.strip()) <= 1000,
            'Player action must be 1–1000 characters')
    revision, state = runtime.load()
    resolution = adjudicator.resolve(action, revision, state)
    return prepare_inputs(runtime, revision, state, action, resolution, use_memory, one_pass)


def prepare_opening(runtime, one_pass=False):
    revision, state = runtime.load()
    require(revision == 0 and state['area'] == 'area_06c',
            'The room entry is available only before the first turn')
    resolution = Resolution('opening', 'A newcomer has reached the card room.', [
        {'type': 'beat', 'tags': ['scene_entry'],
         'evidence': 'Initial framing of area 6c before the player acts.'}])
    return prepare_inputs(runtime, revision, state, '[scene entry]', resolution, use_memory=True,
                          one_pass=one_pass)


def public_performance_base(runtime, body, one_pass=False):
    """The performer's public input. In one-pass mode the same model already reads the
    personality core and dialogue history in the private half, so they are sent once."""
    reference = runtime.source().get('public_performance', {})
    kit_guards.check_voice_contracts(reference.get('actor_cards'))
    payload = {
        'player_view_after_event': body['public_view'],
        'player_action': body['action'], 'accepted_public_event': body['public_event'],
        'action_kind': body['kind'],
        'performance_reference': reference,
    }
    if one_pass:
        payload['shared_with_private'] = ('personality_core and public dialogue history are in '
                                          'input.private (personality_core, dialogue_history)')
    else:
        payload['personality_core'] = PERSONALITY_CORE.read_text(encoding='utf-8')
        payload['public_history'] = body.get('public_history', [])
    return payload


def performance_input(runtime, body, plan):
    payload = public_performance_base(runtime, body)
    payload['selected_move'] = {
            'move': plan['move'],
            'focus_actor': {'uktarl': 'Dealer', 'other': 'Card player',
                            'none': 'none'}[plan['focus_actor']],
            'table_presence': plan['table_presence'], 'tone': plan['tone'],
            'brief': plan['public_brief'],
    }
    callback = plan['public_brief'].get('callback', 'none')
    if callback.strip().casefold() != 'none':
        # Public only: the earlier line the player already saw, so the performer knows
        # who said it. Never the episode's private reading or Kit's reason.
        source = callback_source(callback, runtime.kit_turns_by_id(plan['memory_refs']))
        if source:
            payload['callback_source'] = {key: source[key] for key in ('player_input', 'line')}
    return payload


def retry_instruction(exc):
    """Tell the performer exactly which check failed; the reason names no private fact."""
    return (f'The previous output was rejected: {exc} Keep the same brief and use only '
            'supplied player-visible facts and the accepted event.')


def guard_context(source, body):
    """What the style and leak guards need beyond the performance: DM-only paraphrase
    sets and public voice contracts from the room source, and recent public turns."""
    cards = (source or {}).get('public_performance', {}).get('actor_cards', {})
    return {'leak_sets': kit_guards.leak_sets(source),
            'voice_contracts': {name: card.get('voice_contract') or {} for name, card in cards.items()},
            'public_history': body.get('public_history', [])}


def checked_record(body, plan, speech, performance_variant, source=None, degraded=False):
    """Validate a performance. Every variant faces the same checks; the record names
    which performer instructions ran so play reviews can tell the variants apart. A
    degraded record says so and keeps the soft warnings it was accepted with."""
    check_variant(performance_variant)
    result = check_speech(speech, plan, body['public_view'], body['action'], body['kind'],
                          guards=guard_context(source, body), degraded=degraded)
    spoken, warnings = result if degraded else (result, [])
    if body['kind'] not in ('social', 'opening'):
        spoken = f"Narrator: {body['public_event']}\n{spoken}"
    record = {'player_input': body['action'], 'public_event': body['public_event'],
              'trace': plan, 'spoken': spoken, 'performance_variant': performance_variant}
    if warnings:
        record.update(degraded=True, soft_warnings=warnings)
    return record


class KitAgent:
    def __init__(self, runtime, model, adjudicator=None, performance_variant='current'):
        self.runtime = runtime
        self.model = model
        self.adjudicator = adjudicator or Room6CAdjudicator()
        self.performance_variant = check_variant(performance_variant)

    def turn(self, action, turn_id=None, use_memory=True):
        started = time.monotonic()
        revision, body, planning_input = prepare_turn(
            self.runtime, self.adjudicator, action, use_memory)
        return self._run(revision, body, planning_input, turn_id, started)

    def opening(self, turn_id=None):
        started = time.monotonic()
        revision, body, planning_input = prepare_opening(self.runtime)
        return self._run(revision, body, planning_input, turn_id, started)

    def _run(self, revision, body, planning_input, turn_id, started):
        turn_id = turn_id or str(uuid.uuid4())
        timing = {'mode': 'api', 'model_calls': 0, 'perform_s': [], 'rejections': [],
                  'performance_variant': self.performance_variant}
        outcome = 'rejected'
        try:
            call_started = time.monotonic()
            plan = self.model.plan(planning_input)
            timing['model_calls'] += 1
            timing['plan_s'] = round(time.monotonic() - call_started, 3)
            check_decision(self.runtime, plan, planning_input['kit_state'], body)
            performance_payload = performance_input(self.runtime, body, plan)
            source = self.runtime.source()
            for attempt in range(API_PERFORMANCE_ATTEMPTS):
                last = attempt == API_PERFORMANCE_ATTEMPTS - 1
                call_started = time.monotonic()
                speech = self.model.perform(performance_payload,
                                            performance_variant=self.performance_variant)
                timing['model_calls'] += 1
                timing['perform_s'].append(round(time.monotonic() - call_started, 3))
                try:
                    # The last attempt is degraded: style misses become warnings so the
                    # table is not stalled; hard checks still reject.
                    record = checked_record(body, plan, speech, self.performance_variant, source,
                                            degraded=last and attempt > 0)
                    break
                except InvalidChange as exc:
                    timing['rejections'].append(str(exc))
                    if last:
                        raise
                    performance_payload['retry_instruction'] = retry_instruction(exc)
            if record.get('degraded'):
                timing['degraded'] = True
            next_revision = self.runtime.commit_kit_turn(turn_id, revision, body['events'], record)
            outcome = 'committed'
        except StaleTurn:
            outcome = 'stale'
            raise
        finally:
            timing['outcome'] = outcome
            timing['received_to_done_s'] = round(time.monotonic() - started, 3)
            self.runtime.record_kit_timing(turn_id, **timing)
        return {'revision': next_revision, 'turn_id': turn_id,
                'public_event': body['public_event'], 'spoken': record['spoken'],
                'timing': self.runtime.kit_timing(turn_id)}


class PerformanceRejected(InvalidChange):
    """A rejected performance. `guidance` tells the host its options at this point:
    retry, degraded mode (after DEGRADED_AFTER_REJECTIONS), or abandon."""
    def __init__(self, message, guidance):
        super().__init__(message)
        self.guidance = guidance


STALE_GUIDANCE = ('The world changed after this turn was prepared (another turn or player feedback '
                  'was committed), so nothing was saved. Prepare the same player action again with '
                  'a new turn_id.')


def _stale_guided(method):
    """Bridge calls explain a stale turn instead of only naming revisions."""
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except StaleTurn as exc:
            if STALE_GUIDANCE in str(exc):
                raise
            raise StaleTurn(f'{exc}. {STALE_GUIDANCE}') from exc
    wrapper.__name__, wrapper.__doc__ = method.__name__, method.__doc__
    return wrapper


def _spoken_lines(speech):
    try:
        return '\n'.join(f"{segment['speaker']}: {segment['text'].strip()}"
                         for segment in speech['segments'])
    except (TypeError, KeyError, AttributeError):
        return None


class KitChatBridge:
    """Host this model loop in an assistant chat, with no API credential in Python."""
    def __init__(self, runtime, adjudicator=None):
        self.runtime = runtime
        self.adjudicator = adjudicator or Room6CAdjudicator()

    @_stale_guided
    def prepare(self, action=None, turn_id=None, use_memory=True, one_pass=False, opening=False,
                performance_variant=None):
        """Stage a turn. One-pass turns fix their performer variant here (default
        DEFAULT_BRIDGE_VARIANT); staged turns choose it at decide."""
        turn_id = turn_id or str(uuid.uuid4())
        require(one_pass or performance_variant is None,
                'A staged turn chooses its performance variant at decide')
        if one_pass:
            performance_variant = check_variant(performance_variant or DEFAULT_BRIDGE_VARIANT)
        if opening:
            require(action is None, 'Room opening does not take a player action')
            revision, body, planning_input = prepare_opening(self.runtime, one_pass=one_pass)
        else:
            revision, body, planning_input = prepare_turn(
                self.runtime, self.adjudicator, action, use_memory, one_pass=one_pass)
        body['host_mode'] = 'one_pass' if one_pass else 'staged'
        if one_pass:
            body['performance_variant'] = performance_variant
        self.runtime.stage_kit_turn(turn_id, revision, body)
        # Wall clock, not monotonic: stages may run in separate processes.
        self.runtime.record_kit_timing(turn_id, mode=body['host_mode'], prepared_at=time.time(),
                                       **({'performance_variant': performance_variant}
                                          if one_pass else {}))
        if one_pass:
            return {'turn_id': turn_id, 'stage': 'one_pass',
                    'performance_variant': performance_variant,
                    'instructions': one_pass_instructions(performance_variant),
                    'schema': ONE_PASS_SCHEMA,
                    'performance_limits': performance_limits(), 'host_retry': HOST_RETRY_NOTE,
                    'input': {'private': planning_input,
                              'public': public_performance_base(self.runtime, body, one_pass=True)}}
        return {'turn_id': turn_id, 'stage': 'private_decision',
                'instructions': PRIVATE_INSTRUCTIONS, 'schema': PLAN_SCHEMA,
                'performance_limits': performance_limits(), 'host_retry': HOST_RETRY_NOTE,
                'input': planning_input}

    @_stale_guided
    def decide(self, turn_id, plan, performance_variant=DEFAULT_BRIDGE_VARIANT):
        pending = self.runtime.pending_kit_turn(turn_id)
        body = pending['body']
        if body['host_mode'] != 'staged':
            raise HostSequenceError('Use complete for a one-pass turn', 'complete')
        revision, state = self.runtime.load()
        if revision != pending['revision']:
            raise StaleTurn(f"Expected revision {pending['revision']}; current is {revision}")
        check_variant(performance_variant)
        check_decision(self.runtime, plan,
                       kit_memory(self.runtime, state, body['action'], body['use_memory']), body)
        payload = performance_input(self.runtime, body, plan)
        self.runtime.save_kit_plan(turn_id, revision, plan)
        # finish records the variant of the latest packet issued for this turn.
        self.runtime.record_kit_timing(turn_id, decided_at=time.time(),
                                       performance_variant=performance_variant)
        return {'turn_id': turn_id, 'stage': 'public_performance',
                'performance_variant': performance_variant,
                'instructions': PERFORMANCE_VARIANTS[performance_variant], 'schema': SPEECH_SCHEMA,
                'performance_limits': performance_limits(plan['public_brief']['scope']),
                'host_retry': HOST_RETRY_NOTE, 'input': payload}

    @_stale_guided
    def finish(self, turn_id, speech, degraded=False):
        pending = self._pending_or_replay(turn_id, speech=speech)
        if 'already_committed' in pending:
            return pending
        if pending['body']['host_mode'] != 'staged':
            raise HostSequenceError('Use complete for a one-pass turn', 'complete')
        if pending['plan'] is None:
            raise HostSequenceError('Complete private decision before performance: call decide '
                                    'with the private decision first, then finish.', 'decide')
        body = pending['body']
        self._check_degraded_allowed(turn_id, degraded)
        variant = (self.runtime.kit_timing(turn_id) or {}).get('performance_variant', 'current')
        record = self._checked_or_log(turn_id, body, pending['plan'], speech, variant, degraded)
        revision = self.runtime.commit_kit_turn(
            turn_id, pending['revision'], body['events'], record, consume_pending=True)
        return self._committed_result(turn_id, revision, body, record, variant)

    def _committed_result(self, turn_id, revision, body, record, variant):
        result = {'revision': revision, 'turn_id': turn_id,
                  'public_event': body['public_event'], 'spoken': record['spoken'],
                  'performance_variant': variant, 'timing': self._finish_timing(turn_id, record)}
        if record.get('degraded'):
            result.update(degraded=True, soft_warnings=record['soft_warnings'])
        return result

    def _pending_or_replay(self, turn_id, speech=None, decision=None):
        """The pending turn, or, for an identical resubmission of a committed turn (a host
        retrying after a lost response), the committed result instead of an error."""
        try:
            return self.runtime.pending_kit_turn(turn_id)
        except HostSequenceError as exc:
            committed = self.runtime.committed_kit_turn(turn_id)
            spoken = _spoken_lines(speech)
            if (committed and spoken and committed['spoken'].endswith(spoken) and
                    (decision is None or committed['trace'] == decision)):
                return {'already_committed': True, 'revision': committed['revision'],
                        'turn_id': turn_id, 'public_event': committed['public_event'],
                        'spoken': committed['spoken'],
                        'performance_variant': committed.get('performance_variant', 'current')}
            if committed:
                raise HostSequenceError(
                    f'{exc} The submitted output differs from what was committed; show the '
                    'committed spoken text (see trace) and move on.', 'prepare_new_turn') from exc
            raise

    def _rejections(self, turn_id):
        return (self.runtime.kit_timing(turn_id) or {}).get('rejected_attempts', 0)

    def _check_degraded_allowed(self, turn_id, degraded):
        if degraded and self._rejections(turn_id) < DEGRADED_AFTER_REJECTIONS:
            raise HostSequenceError(
                f'Degraded mode unlocks after {DEGRADED_AFTER_REJECTIONS} rejected attempts on this '
                f'turn ({self._rejections(turn_id)} so far). Fix the performance and resubmit normally.',
                'retry')

    def guidance(self, turn_id):
        """The host's options after a rejection, by how many this turn has had."""
        count = self._rejections(turn_id)
        guidance = {'rejected_attempts': count, 'degraded_available': count >= DEGRADED_AFTER_REJECTIONS,
                    'next_step': 'retry'}
        if count >= DEGRADED_AFTER_REJECTIONS:
            guidance.update(next_step='retry_degraded', degraded_instruction=DEGRADED_INSTRUCTION)
        if count >= ABANDON_SUGGEST_AFTER:
            guidance.update(next_step='abandon_and_prepare_again', abandon_instruction=ABANDON_INSTRUCTION)
        return guidance

    def _log_rejection(self, turn_id, exc):
        prior = self.runtime.kit_timing(turn_id) or {}
        self.runtime.record_kit_timing(
            turn_id, rejected_attempts=prior.get('rejected_attempts', 0) + 1,
            last_rejection=str(exc))
        guidance = self.guidance(turn_id)
        message = str(exc)
        if guidance.get('abandon_instruction'):
            message += ' ' + ABANDON_INSTRUCTION
        elif guidance['degraded_available']:
            message += ' ' + DEGRADED_INSTRUCTION
        return PerformanceRejected(message, guidance)

    def _checked_or_log(self, turn_id, body, plan, speech, performance_variant, degraded=False):
        try:
            return checked_record(body, plan, speech, performance_variant, self.runtime.source(),
                                  degraded=degraded)
        except StaleTurn:
            raise
        except InvalidChange as exc:
            raise self._log_rejection(turn_id, exc) from exc

    def _finish_timing(self, turn_id, record=None):
        timing = self.runtime.kit_timing(turn_id) or {}
        now = time.time()
        fields = {'committed_at': now}
        if record is not None and record.get('degraded'):
            fields['degraded'] = True
        if 'prepared_at' in timing:
            # Includes host model time between stages; excludes anything before prepare.
            fields['prepare_to_commit_s'] = round(now - timing['prepared_at'], 3)
        if 'decided_at' in timing:
            fields['decide_to_commit_s'] = round(now - timing['decided_at'], 3)
        self.runtime.record_kit_timing(turn_id, outcome='committed', **fields)
        return self.runtime.kit_timing(turn_id)

    def abandon(self, turn_id):
        """Drop an uncommitted pending turn so the host can prepare the action again,
        e.g. when a fixed decision keeps producing rejected performances."""
        self.runtime.discard_pending_kit_turn(turn_id)
        self.runtime.record_kit_timing(turn_id, outcome='abandoned', abandoned_at=time.time())
        return {'stage': 'abandoned', 'turn_id': turn_id, 'committed': False,
                'next_step': 'prepare the same player action again with a new turn_id'}

    def feedback(self, text, evidence_turns=None, replaces='none'):
        """Record the player's out-of-character comment for Kit's next private decision.

        Nothing here is shown to the player or sent to the performer. The note cites
        the committed turn it is about (default: the latest). Record feedback between
        turns: it commits a new revision, so a turn already prepared must be prepared again.
        """
        result = self.runtime.record_player_feedback(text, evidence_turns, replaces)
        return {'stage': 'feedback_recorded', 'committed': True, **result,
                'host_note': ('Private to Kit’s decision stage. Do not show or read this back '
                              'to the player; its effect may appear only through kit_focus or '
                              'callback on later turns. Prepare the next turn fresh.')}

    @_stale_guided
    def complete(self, turn_id, output, degraded=False):
        """Validate and commit one model output in one host round trip."""
        require(isinstance(output, dict) and set(output) == {'decision', 'performance'},
                'Expected a decision and performance')
        pending = self._pending_or_replay(turn_id, speech=output['performance'],
                                          decision=output['decision'])
        if 'already_committed' in pending:
            return pending
        body, plan = pending['body'], output['decision']
        if body['host_mode'] != 'one_pass':
            raise HostSequenceError('Use decide and finish for a staged turn', 'decide')
        revision, state = self.runtime.load()
        if revision != pending['revision']:
            raise StaleTurn(f"Expected revision {pending['revision']}; current is {revision}")
        self._check_degraded_allowed(turn_id, degraded)
        if pending['plan'] is None:
            try:
                check_decision(self.runtime, plan,
                               kit_memory(self.runtime, state, body['action'], body['use_memory']),
                               body)
            except StaleTurn:
                raise
            except InvalidChange as exc:
                raise self._log_rejection(turn_id, exc) from exc
        self.runtime.save_kit_plan(turn_id, revision, plan)
        # Turns staged before variants reached one-pass ran the `current` instructions.
        variant = body.get('performance_variant', 'current')
        record = self._checked_or_log(turn_id, body, plan, output['performance'], variant, degraded)
        next_revision = self.runtime.commit_kit_turn(
            turn_id, revision, body['events'], record, consume_pending=True)
        return self._committed_result(turn_id, next_revision, body, record, variant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'view', 'prepare', 'decide', 'finish', 'complete',
                                            'abandon', 'feedback', 'notes', 'play', 'trace', 'timing'])
    parser.add_argument('--db', default='kit-06c.sqlite')
    parser.add_argument('--model', help='Optional standalone Responses API model for play')
    parser.add_argument('--perception', type=int, help='Test character Wisdom (Perception) modifier')
    parser.add_argument('--insight', type=int, help='Test character Wisdom (Insight) modifier')
    parser.add_argument('--no-memory', action='store_true', help='Ablation: hide Kit’s prior episodes from her decision stage')
    parser.add_argument('--one-pass', action='store_true', help='One model output for live chat; use complete to commit')
    parser.add_argument('--performance-variant', choices=PERFORMANCE_VARIANTS,
                        help=f'Performer instructions: for prepare --one-pass or decide (default '
                             f'{DEFAULT_BRIDGE_VARIANT}), or for play (default current)')
    parser.add_argument('--opening', action='store_true', help='Prepare the initial scene entry instead of a player action')
    parser.add_argument('--action', help='Player action for prepare')
    parser.add_argument('--action-file', help='UTF-8 player action file for prepare')
    parser.add_argument('--turn-id', help='Turn ID returned by prepare')
    parser.add_argument('--input-file', help='JSON plan, speech, or combined output; - reads stdin')
    parser.add_argument('--text', help='feedback: the player’s out-of-character comment')
    parser.add_argument('--evidence', action='append',
                        help='feedback: committed turn ID the comment is about (repeatable; '
                             'default: latest turn)')
    parser.add_argument('--replaces', default='none', help='feedback: note id this feedback supersedes')
    parser.add_argument('--degraded', action='store_true',
                        help=f'finish/complete: accept style misses as warnings (only after '
                             f'{DEGRADED_AFTER_REJECTIONS} rejections on the turn)')
    args = parser.parse_args()
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = json.loads(ROOM_FIXTURE.read_text(encoding='utf-8'))
            runtime.initialize(source, source['starting_area'])
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'view':
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'trace':
            print(json.dumps(runtime.recent_kit_turns(), indent=2, ensure_ascii=False))
        elif args.command == 'timing':
            print(json.dumps(runtime.recent_kit_timings(), indent=2, ensure_ascii=False))
        elif args.command == 'notes':
            print(json.dumps(runtime.player_notes(), indent=2, ensure_ascii=False))
        elif args.command in ('prepare', 'decide', 'finish', 'complete', 'abandon', 'feedback'):
            bridge = KitChatBridge(runtime, Room6CAdjudicator(args.perception, args.insight))
            try:
                if args.command == 'abandon':
                    if not args.turn_id:
                        parser.error('abandon requires --turn-id')
                    result = bridge.abandon(args.turn_id)
                elif args.command == 'feedback':
                    if not args.text:
                        parser.error('feedback requires --text')
                    result = bridge.feedback(args.text, args.evidence, args.replaces)
                elif args.command == 'prepare':
                    if args.opening:
                        if args.action is not None or args.action_file is not None:
                            parser.error('--opening does not take an action')
                        action = None
                    else:
                        if (args.action is None) == (args.action_file is None):
                            parser.error('prepare requires exactly one of --action or --action-file')
                        action = (args.action if args.action_file is None else
                                  Path(args.action_file).read_text(encoding='utf-8').strip())
                    if args.performance_variant and not args.one_pass:
                        parser.error('--performance-variant on prepare needs --one-pass; '
                                     'staged turns choose it at decide')
                    result = bridge.prepare(action, args.turn_id, use_memory=not args.no_memory,
                                            one_pass=args.one_pass, opening=args.opening,
                                            performance_variant=args.performance_variant)
                else:
                    if not args.turn_id or not args.input_file:
                        parser.error(f'{args.command} requires --turn-id and --input-file')
                    raw = sys.stdin.read() if args.input_file == '-' else Path(args.input_file).read_text(encoding='utf-8')
                    submitted = json.loads(raw)
                    variant = args.performance_variant or DEFAULT_BRIDGE_VARIANT
                    result = (bridge.decide(args.turn_id, submitted, variant) if args.command == 'decide' else
                              bridge.finish(args.turn_id, submitted, degraded=args.degraded)
                              if args.command == 'finish' else
                              bridge.complete(args.turn_id, submitted, degraded=args.degraded))
            except PendingRuling as exc:
                result = {'stage': 'pending_ruling', 'message': str(exc), 'committed': False}
            except InvalidChange as exc:
                rejected = {'stage': 'rejected', 'message': str(exc), 'committed': False}
                if isinstance(exc, HostSequenceError):
                    rejected['next_step'] = exc.next_step
                elif isinstance(exc, StaleTurn):
                    rejected['next_step'] = 'prepare_again'
                if isinstance(exc, PerformanceRejected):
                    rejected.update(exc.guidance)
                if args.command in ('finish', 'complete') and not isinstance(exc, StaleTurn):
                    pending = None
                    try:
                        pending = runtime.pending_kit_turn(args.turn_id)
                    except InvalidChange:
                        pass
                    if pending and pending['plan'] is not None:
                        rejected.update(decision_fixed=True, retry_instruction=retry_instruction(exc),
                                        host_retry=HOST_RETRY_NOTE)
                print(json.dumps(rejected, ensure_ascii=False), file=sys.stderr)
                return 2
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if not args.model:
                parser.error('standalone play requires --model; for ChatGPT use prepare/decide/finish')
            if not os.environ.get('OPENAI_API_KEY'):
                parser.error('standalone play requires OPENAI_API_KEY; for ChatGPT use prepare/decide/finish')
            model = OpenAIResponsesModel(args.model)
            agent = KitAgent(runtime, model, Room6CAdjudicator(args.perception, args.insight),
                             performance_variant=args.performance_variant or 'current')
            print('Kit’s area 6c test. Enter an action, or /quit. Private traces: separate trace command.')
            if runtime.load()[0] == 0:
                try:
                    print(agent.opening()['spoken'])
                except InvalidChange as exc:
                    print(f'Opening rejected; no state was saved: {exc}', file=sys.stderr)
                    return 2
            else:
                print(f"Resuming in {runtime.player_view()['area']}.")
            while True:
                try:
                    action = input('\nYou> ').strip()
                except EOFError:
                    break
                if action == '/quit':
                    break
                if not action:
                    continue
                try:
                    result = agent.turn(action, use_memory=not args.no_memory)
                    print(f"\n{result['spoken']}")
                except PendingRuling as exc:
                    print(f'\n{exc}')
                except InvalidChange as exc:
                    print(f'\nTurn rejected; no state was saved: {exc}', file=sys.stderr)
    finally:
        runtime.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Area 6c Kit play slice: grounded events, private appraisal, public performance.

Only a few explicitly bounded room actions are adjudicated here. The model can
choose and perform a DM move, but it cannot submit world changes to storage.
"""
import argparse
import copy
import dataclasses
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

from . import kit_attitude
from . import kit_brief
from . import kit_cards
from . import kit_combat
from . import kit_rolls
from . import kit_claims
from . import kit_manifest
from . import kit_router
from . import kit_agenda, kit_plan, kit_threads, pc_sheet
from . import kit_detail
from . import kit_prices
from . import kit_rooms
from . import kit_texture
from . import kit_toll
from . import kit_twenty_one
from . import kit_guards
from . import kit_voice
from . import kit_visual
from .scene_discernment import IMPROV_READ_SCHEMA, check_improv_read, discernment_candidates
from .state_context import (ASKED_EVENT_PREFIX, CONTEXT_BUDGET_BYTES, HostSequenceError, InvalidChange,
                            PERSONALITY_CORE, PLAYER_NOTE_MAX_EVIDENCE, PROJECT_ROOT, Runtime,
                            StaleTurn, VOICE_MAX_BYTES, load_voice, personality_core_text,
                            check_player_note_text, encode, require)
from .state_context import HELD_KINDS as _HELD_KINDS


# The room `start` mounts when the host names none: area 6c, the one room with full
# content today. Any room file mounts with --room (runtime/kit_rooms.py).
DEFAULT_ROOM = PROJECT_ROOT / 'tests/fixtures/level_01_area_06c.json'


class PendingRuling(Exception):
    """The room slice cannot establish this outcome without more game machinery.

    `attempt` marks an in-fiction attempt the table refused (combat, a spell effect, an
    unsupported physical act), as opposed to a host input problem such as a
    missing modifier. The bridge records attempts in public history."""
    def __init__(self, message, attempt=False):
        super().__init__(message)
        self.attempt = attempt


@dataclass(frozen=True)
class Resolution:
    kind: str
    public_event: str
    events: list


# The accepted event is bounded at 500 characters (check_plan; card turns use
# CARD_EVENT_MAX_CHARS). A social event is
# a restatement of the player's declared words, so Kit's appraisal and the
# performer react to what was actually said instead of a generic placeholder.
EVENT_MAX_CHARS = 500
# A card turn reports every card played until the player acts again (up to a round and
# a half at a five-seat table, plus the showdown), so it gets a longer bound.
CARD_EVENT_MAX_CHARS = 1200
# Kinds whose accepted event may run to CARD_EVENT_MAX_CHARS: a card round, a combat round
# (the PC's act and every NPC turn after it), and a physical act with its consequences.
LONG_EVENT_KINDS = ('card_', 'combat_', 'physical_')
SOCIAL_EVENT_PREFIX = 'You declare: '
_TYPOGRAPHIC = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"'})


def social_event(action):
    """Public restatement of a social bid: the player's own words, nothing added.

    Whitespace is collapsed and curly quotes become straight quotes so the private
    stage can copy the event exactly; the words themselves are not changed. Text
    past the event bound is cut at a word boundary and marked with '...'. It says
    nothing about how anyone responds; the full declaration stays in the evidence.
    """
    # Speech the player already quoted stays speech: its double quotes become single quotes
    # inside the one outer pair ('You declare: "\'Deal me in,\' I say."'), never doubled.
    words = ' '.join(action.translate(_TYPOGRAPHIC).split()).replace('"', "'")
    room = EVENT_MAX_CHARS - len(SOCIAL_EVENT_PREFIX) - 2
    if len(words) > room:
        cut = words[:room - 3]
        cut = cut[:cut.rfind(' ')] if ' ' in cut else cut
        words = cut.rstrip(' ,;:') + '...'
    return f'{SOCIAL_EVENT_PREFIX}"{words}"'


# Host-declared table talk (prepare --table-talk): the player talking to Kit, not the PC to
# the room. It is answered in meta mode and never resolved; NPCs do not hear it.
TABLE_TALK_PREFIX = 'Table talk to Kit: '


TABLE_TALK_NOTE = ('Table talk: the player is talking to you, Kit, not the PC to the room. Nothing was '
                   'resolved. Answer as yourself in meta mode (Kit speaks; move ruling, or ask_clarification '
                   'to ask back; no NPC hears or answers). Hidden facts stay hidden.')


def table_talk_event(action):
    """Public record of a table-talk line: the player's words to Kit, never 'You declare'."""
    return TABLE_TALK_PREFIX + social_event(action)[len(SOCIAL_EVENT_PREFIX):]


def table_talk_resolution(action):
    """The host marked this message as table talk. No adjudication: no check, ruling, toll,
    card call, or NPC reaction; the room's state does not change."""
    return Resolution('social', table_talk_event(action), [
        {'type': 'beat', 'tags': ['table_talk'],
         'evidence': f'Host marked table talk: {action}. Out of character, answered by Kit; '
                     'no world state changed and no NPC heard it.'}])


# Table talk addressed to Kit rather than the room: answered, never resolved as a check.
_SKILL_NAMES = '(?:' + '|'.join(sorted((s.replace('_', ' ') for s in pc_sheet.SKILLS), key=len, reverse=True)) + ')'
OOC_MARKER = re.compile(r'^\s*[(\[]?\s*(ooc\b|out[- ]of[- ]character)|\brules question\b', re.I)
# Natural table talk needs no prefix: a message addressed to Kit by name, or a question
# about the rules themselves (their nouns, not in-world verbs like sneak or grab).
KIT_ADDRESS = re.compile(r"^\W*(?:(?:hey|ok|okay|so|um|and)\W+)?kit\b|\bkit\s*[,?]|,\s*kit\W*$", re.I)
RULES_NOUNS = re.compile(r"\b(rules?|dc|modifiers?|advantage|disadvantage|bonus action|reactions?|saving throws?|"
                         r"proficien\w*|spell slots?|initiative|passive \w+|concentration|(?:short|long) rest|"
                         r"hit points|armou?r class|cantrips?|how does \w+(?: \w+)? work|allowed to|"
                         # skill questions (Kit's working model of skills, docs/voice): "what's the
                         # difference between Insight and Investigation?", "why didn't Perception
                         # tell me?", "why can't I use Investigation instead of Perception?"
                         r"difference between \w+ and \w+|skill (?:swaps?|substitut\w*|checks? work)|"
                         r"(?:use|roll) \w+(?: \w+)? (?:instead of|for this)|"
                         r"why (?:didn't|did not|doesn't|does not|can't|cannot|won't|wouldn't) (?:my )?"
                         + _SKILL_NAMES + r")\b", re.I)
# Looking away from whatever is in front of you: the room, the rest of it, elsewhere.
OBSERVE = re.compile(r"\b(look|looks|looking|glance|scan|survey|take in|gaze|peer|what else)\b[^.?!]{0,30}"
                     r"\b(around|room|else|rest of|elsewhere|away|here|walls?)\b|\bwhat else\b"
                     # A plain look at a visible feature is free description, no roll (table call 2).
                     r"|\b(?:look|looks|looking|glance|glances|gaze|gazes)\s+(?:up |over |closer )?at\b"
                     r"|\bwhat'?s (?:interesting|here|notable)\b"
                     # Going over what is plainly there (6c baseline V9: "I check the table"), and
                     # walking into the room the PC is already in (V6): free description, no roll.
                     r"|\b(?:check|checks|search|searches|go through|goes through|look over|rummage)\b[^.?!]{0,20}"
                     r"\b(?:table|room|floor|bodies|body|spill|wreckage|mess)\b"
                     r"|\b(?:head|heads|walk|walks|go|goes|step|steps|come|comes)\s+(?:on\s+)?(?:in|into|toward|towards)\b"
                     r"[^.?!]{0,15}\b(?:6c|room|chamber)\b")
# A read of the whole group, not one speaker's words (call 3's clue invites it).
GROUP_READ = re.compile(r"\bsomething(?:'s| is)? (?:off|wrong|strange|weird|not right)\b|\bwhat'?s off\b"
                        r"|\b(?:study|studying|size up|sizing up|read|reading|scrutini[sz]e)\s+(?:them|the (?:four|table|"
                        r"players|group|gamblers|lot of them))\b|\bsize them up\b", re.I)
# Asking to play the room's game (call 7: "I play the game." is a complete declaration).
PLAY_REQUEST = re.compile(r"\b(?:i(?:'ll| will)? play|let'?s play|join (?:the|your|you|in)|sit in|deal me in|"
                          r"count me in|buy in|buy-in|i'?m in|play (?:a|the|one|your) (?:game|hand|round)|"
                          r"play cards|play blackjack|play twenty[- ]one|just roll for it|dealt in|be dealt|"
                          r"deal (?:me|us|her|him|myself) in|deal(?:s|ing)? in|take (?:the|a|an) (?:empty |open |free )?(?:chair|seat) at the table)\b")
# Rolls a player makes in conversation, and what each outcome means for the NPC addressed.
SOCIAL_CHECK_SKILLS = ('deception', 'persuasion', 'intimidation', 'performance', 'athletics')
SOCIAL_OUTCOMES = {
    'deception': ('{who} believes you.', '{who} does not believe you.'),
    'persuasion': ('{who} comes around to it.', '{who} is not moved.'),
    'intimidation': ('{who} backs down.', '{who} does not scare.'),
    'performance': ('{who} is taken in by the act.', '{who} is not taken in.'),
    'athletics': ('You overpower {who}.', '{who} holds firm against you.'),
}
# A bet named in speech or narration ("'I'll bet fifty gold.'") is asking to play.
SPOKEN_BET = re.compile(r"\b(?:bet|bets|betting|wager|stake)\b[^.?!]{0,20}\b(?:\d{1,4}|[a-z]+(?:-[a-z]+)?)\s+(?:gp|gold)\b")
# Words inside quotation marks are speech; a threat or a noun spoken aloud is not a physical act.
# Double or single quotes (the 6c baseline's V7: 'Ten gold just to walk through a room?'
# inside single quotes was read as walking out the door). Apostrophes in words never open one.
QUOTED_SPEECH = re.compile(r'"[^"]*"|' + r"(?:(?<=^)|(?<=[\s(\[:;,.!?\u2014-]))'(?=\S)[^\n]*?(?<=\S)'"
                           r"(?=$|[\s)\].,!?;:\u2014-])")
# A stealthy approach needs a Stealth ruling; it must never pass as a free, unopposed exit.
STEALTH_INTENT = re.compile(r'\b(sneak|sneaks|sneaking|creep|creeps|creeping|tiptoe|tiptoes|tiptoeing|'
                            r'stealth|stealthily|unnoticed|unseen)\b|\bslip(s|ping)? (past|by)\b')
# Perception at a threshold, not movement (watchroom T1: a peek through the door gap was read as
# walking out through it): peek, peer, look or watch through, listen at, an eye or ear to the
# gap, cracking the door. Going through, in, or past is still movement (MOVE_THROUGH).
THRESHOLD_LOOK = re.compile(
    r"\b(?:peek|peeks|peeking|peeked|peer|peers|peering|eavesdrop\w*|listen|listens|listening|listened)\b"
    r"|\b(?:eye|eyes|ear|ears)\s+(?:up\s+)?(?:to|against)\b"
    r"|\b(?:look|looks|looking|glance|glances|watch|watches|watching|see|sees)\s+(?:in\s+)?(?:through|in\b|into|past)"
    r"|\b(?:crack|cracks|cracking|cracked)\s+(?:the|it|that)\b")
THRESHOLD_GAP = re.compile(r"\b(?:gap|crack|keyhole|opening|chink|doorway|threshold|door|doors|hinges?|grille|grate)\b")
MOVE_THROUGH = re.compile(
    r"\b(?:go|goes|going|went|step|steps|stepping|stepped|walk|walks|walked|slip|slips|slipped|move|moves|head|heads|"
    r"pass|passes|enter|enters|entered|run|runs|ran|squeeze|squeezes|duck|ducks|push|pushes)\b(?:\s+[\w']+){0,2}?"
    r"\s+(?:through|in|inside|into|past|out)\b|\b(?:enter|enters|entered)\b")
# The player asking for a check (watchroom T1/T3): Kit decides whether one applies and which
# (Brendon: the player never picks the skill and never rolls first). Never a social declaration.
CHECK_REQUEST = re.compile(
    # The PC asks for themselves ("Can I roll...", "Should we check..."): never an NPC asked to
    # do something ("Dealer, can you check my hand?"); a save is the noun ("make a save"), never
    # the verb ("Can I save him?").
    r"\b(?:can|could|may|do|should|shall|would|might|must)\s+(?:i|we)\s+"
    r"(?:\w+\s+){0,4}?(?:roll|rolls|check|checks|test|(?:a|an|the|my|\w+ing)\s+(?:\w+\s+)?save|saving throw)\b[^?]*\?"
    r"|\b(?:is|would) (?:that|this|there) (?:a|an) (?:\w+\s+)?(?:check|roll)\b[^?]*\?"
    r"|\bdo i (?:need|get|have) (?:to )?(?:make |roll )?(?:a|an) (?:\w+\s+)?(?:check|roll)\b", re.I)
CHECK_REQUEST_PREFIX = 'You ask for a check: '
# A sentence that asks ("Could I grab the spear before he moves?", "Is there anywhere to
# hide?") declares nothing; asked_away drops those sentences before a physical reading.
ASKING = re.compile(r"(?:(?<=^)|(?<=[.!?]))\s*(?:can|could|may|might|would|will|should|shall|is|are|was|were|"
                    r"do|does|did|what|where|who|whom|how|which|why|when|any)\b[^.?!]*\?", re.I)


def asked_away(words):
    return ASKING.sub(' ', words)
# Short beats (plan update #3): a heavy turn may open on just a fitting check call, and the
# engine holds the description for the roll; the next turn delivers it scaled to the result.
STALL_KINDS = _HELD_KINDS
HELD_RULE = (
    'Kit opened this turn on a check; the roll is in. Deliver the held description now, in full and '
    'not another call: what anyone would notice always lands, and the roll scales the rest (a high '
    'roll adds what the check found, per accepted_public_event; a low one gets the plain view).')
HELD_NO_ROLL_RULE = (
    'Kit opened last turn on a check and the player did not roll. The held description is still owed: '
    'deliver it now, in full, as the plain view (what anyone would notice), and answer this move too. '
    'No new check call until it is delivered.')
# The held description is delivered when the narration shows at least this many of the held
# area's own visible things (fixture-free: the cue words come from the room's facts).
HELD_CUES_NEEDED = 2
_CUE_STOP = frozenset('''about above after again along also around away back been before behind being below
beside between beyond both down each from have here into just like more most near none only other over
past same some someone something still such than that their them then there these they this those
through under very what when where which while with within without would your stands sits hangs lies
over over'''.split())
SHORT_BEAT_LINE = ('A short beat is a whole turn: one real reaction plus a narrowing question or an '
                   '"are you sure?" before a risky act (ask_clarification, scope call). Do not pad it.')
STALL_LINE = ('Heavy turn: you may open on just a fitting check call (scope call, roll_call set, a sheet '
              'skill); the engine holds the description for the roll. Only an earned check: would you call '
              'it if the answer were instant? If not, describe now. Not while a due hook must land.')


def stall_check(plan, action_kind):
    """Kit's first commit on a heavy turn is only a check call (room entry, a first look,
    a way through); the description is held for the roll."""
    return (action_kind in STALL_KINDS and plan.get('public_brief', {}).get('scope') == 'call'
            and bool(plan.get('roll_call')))


def check_short_beat(plan, body, state):
    """A stall calls a real sheet-skill check, never twice before the roll, never in place of a
    due hook; and the roll turn delivers the held description, not another call."""
    if stall_check(plan, body['kind']):
        require(kit_agenda.called_skill(plan['roll_call'].get('skill')) is not None,
                'A stall check on a heavy turn calls a skill check the roll can answer (e.g. Perception)')
        require(not ((state.get('pending_check') or {}).get('held')),
                'A held description is already waiting on the roll; deliver it before calling another')
        require(not body.get('story_due'),
                'A due hook lands this turn; do not stall it behind a check')
    if body.get('held_description'):
        require(plan['public_brief']['scope'] == 'feature',
                'The held description is due now: describe the place in full (feature scope), '
                'scaled to the roll; not another call')
        require(not plan.get('roll_call'),
                'A held description is owed; deliver it before calling another check')


def held_cues(source, state, area, threshold=None):
    """The held area's own visible things, as cue words: the room's visible facts there (and
    through a threshold the check looked across), its name, and who is there."""
    areas = {area}
    if threshold:
        areas |= set(((source.get('exits') or {}).get(threshold) or {}).get('areas') or ())
    texts = [fact.get('text') or '' for fact in (source.get('facts') or {}).values()
             if fact.get('area') in areas and fact.get('visible')]
    texts += [(source.get('areas') or {}).get(key, {}).get('name') or '' for key in areas]
    texts += [actor.get('name') or '' for actor in (state.get('actors') or {}).values()
              if actor.get('location') in areas and actor.get('visible', True)]
    words = {w for text in texts for w in re.findall(r"[a-z]{4,}", text.casefold()) if w not in _CUE_STOP}
    return sorted(words)


def check_held_delivered(held, spoken):
    """HARD: the turn a held description is due actually describes the held place."""
    if not held:
        return
    text = spoken.casefold()
    found = [cue for cue in held.get('cues') or () if re.search(r'\b' + re.escape(cue[:-1] if len(cue) > 5 else cue), text)]
    require(len(found) >= min(HELD_CUES_NEEDED, len(held.get('cues') or ())),
            f"The held {held['kind']} description is due: describe the place itself (what anyone there "
            f"would notice: e.g. {', '.join((held.get('cues') or [])[:6])}), not just this move")


def roll_total(action):
    """The total in a bare or stated roll line, or None."""
    text = action.translate(_TYPOGRAPHIC).strip()
    bare = re.fullmatch(r'(?:i\s+)?(?:rolled|roll|got)?\s*(?:an?\s+)?(\d{1,2})\s*[.!]?', text, re.I)
    if bare:
        return int(bare.group(1))
    stated = kit_rolls.rolls(text)
    return stated[0].total if stated else None


CHECK_REQUEST_RULE = (
    'The player asks for a check. Kit decides: call one with roll_call (the skill, mode, and DC are '
    'yours; the player never picks the skill and never rolls first) and stop at the call, or decline '
    'in a line and resolve from what is plain. A skill the player named is a request, never the call. '
    'Answer every question in the same message.')


# A room feature the file declares (a fact's ``handling``: a tub, a chest, a well) is acted
# on by its own nouns. Getting into it means landing on whatever is stored in it.
def _feature_entry(nouns):
    return re.compile(r'\b(climb|get|sit|lie|lay|jump|hop|step|lower|slide|settle|bathe|soak|lounge)'
                      r'\w*\b[^.]*?\b(in|into)\b[^.]*?\b(?:' + nouns + r')\b')
# Handling a feature takes a hands-on verb whose own object is the feature, at most four words
# on ("I search the old chest", "I crouch by the tub", "I look inside the chest", "what's in
# the tub?"). A look or a watch toward it ("I look at the chest", "his eyes flick toward the
# chest") is free description, never the feature's handling (watchroom playtest).
def _feature_handled(nouns):
    gap = r"(?:\s+(?!(?:toward|towards|at|or|and|while|whether)\b)[\w'-]+){0,4}?\s+"
    return re.compile(
        r"\b(?:search|searches|inspect|inspects|examine|examines|check|checks|open|opens|rummage|rummages|"
        r"crouch|crouches|kneel|kneels|squat|squats|lean over|leans over|bend over|bends over)\b" + gap +
        r"(?:" + nouns + r")\b"
        r"|\b(?:look|looks|peer|peers|reach|reaches|feel|feels)\s+(?:\w+\s+)?(?:in|inside|into|under|beneath|behind)\b"
        + gap + r"(?:" + nouns + r")\b"
        r"|\bwhat(?:'?s| is) (?:in|inside|under)\b" + gap + r"(?:" + nouns + r")\b"
        r"|\banything (?:in|inside|under)\b" + gap + r"(?:" + nouns + r")\b")


SOCIAL_WORDS = re.compile(
    r'\b(ask|say|tell|talk|speak|offer|bargain|propose|accuse|call out|sit|greet|hello|wait|listen|'
    r'wager|help|deal|promise|refuse|decline|pay|flirt|wink|smile|laugh|bow|introduce|threaten|'
    r'intimidate|join|bet|watch|observe|nod|shrug|thank|insist|warn|demand|charm|compliment|stare|'
    r'glare|question|doubt|mock|tease|chat|banter|gossip|joke|toast|cheer|praise|admire|comment|remark|'
    r'apologi[sz]e|haggle|challenge|chuckle|grin|sigh|whistle|hum)(s|es|d|ed|ing)?\b')
# Harmless table gestures and postures: the PC's own body at rest or at play, never an act on
# the room or on someone. A posture verb ("lean back", "kick back", "stretch"), or any verb
# whose own object is the PC's own body part ("clean my nails", "crack my knuckles").
GESTURE = re.compile(
    r"\b(?:lean|leans|leaning|relax|relaxes|stretch|stretches|yawn|yawns|settle|settles|slouch|slouches|lounge|"
    r"lounges|sprawl|sprawls|fidget|fidgets|kick(?:s|ing)? back|put(?:s|ting)? (?:my|his|her) feet up|"
    r"raise(?:s|d)? a toast|cross(?:es)? (?:my|his|her) (?:arms|legs))\b"
    # Showing empty hands: "I hold up empty hands", "Nik raises his open palms".
    r"|\b(?:hold|holds|holding|raise|raises|raising|show|shows|showing|spread|spreads)\s+(?:up\s+)?"
    r"(?:my|his|her|their|both|empty|open)\s+(?:\w+\s+)?(?:hands|palms)\b"
    r"|\b\w+\s+(?:my|his|her|their)\s+(?:\w+\s+)?(?:nails|fingernails|knuckles|fingers|ears|whiskers|nose|"
    r"chin|neck|feet|legs|arms|hair|beard|eyebrows?|brow|shoulders|teeth|lips)\b")
# A feature is moved only as the verb's own object ("tip the heavy tub over"), not as a place
# something moves toward ("move my chair closer to the tub").
def _feature_moved(nouns):
    return re.compile(r"\b(?:tip|tips|overturn|overturns|flip|flips|lift|lifts|move|moves|push|pushes|shove|"
                      r"shoves|tilt|tilts|drag|drags|roll|rolls)\s+(?:(?!(?:to|toward|towards|near|by|beside|"
                      r"next|closer|over|up|against|from|into|onto)\b)[\w'-]+\s+){0,3}(?:" + nouns + r")\b")


@dataclass(frozen=True)
class RoomWords:
    """What the router needs from the room file: the nouns of its handled features (fact id
    by noun) and the words naming the exits the PC can take from here (exit id by word)."""
    features: tuple = ()
    exits: tuple = ()
    inward: tuple = ()  # exits from an outside area into the room: what "I step in" takes

    def feature_in(self, words):
        for noun, fact in self.features:
            if re.search(r'\b' + re.escape(noun) + r's?\b', words):
                return noun, fact
        return None


EXIT_STOPWORDS = {'the', 'a', 'an', 'to', 'of', 'into', 'and', 'way', 'back', 'out'}


def room_words(source, state):
    """RoomWords for the PC's area, from the room file alone."""
    source, state = source or {}, state or {}
    area = state.get('area')
    features = tuple((noun.casefold(), key) for key, fact in (source.get('facts') or {}).items()
                     if isinstance(fact, dict) and fact.get('area') == area and fact.get('handling')
                     for noun in fact['handling'].get('nouns') or ())
    exits = []
    for key in state.get('known_exits') or ():
        edge = (source.get('exits') or {}).get(key) or {}
        if area not in edge.get('areas', ()):
            continue
        for word in re.findall(r"[a-z]+", str(edge.get('name') or '').casefold()):
            if word not in EXIT_STOPWORDS:
                exits.append((word, key))
    inside = set(kit_rooms.room_areas(source)) if source.get('areas') else set()
    inward = tuple(key for key in state.get('known_exits') or ()
                   if area not in inside and area in ((source.get('exits') or {}).get(key) or {}).get('areas', ()) and
                   inside & set(((source.get('exits') or {}).get(key) or {}).get('areas', ())))
    return RoomWords(features, tuple(exits), inward)


# Leaving by an exit named as the verb's object, at most three words on: "I take the stair
# down", "I duck through the tunnel", "I slip out the back door". Further off, the exit is
# where something else happens ("I take the key from the door").
EXIT_OBJECT_VERBS = (r'take|takes|use|uses|climb|climbs|duck|ducks|crawl|crawls|slip|slips|descend|descends|'
                     r'ascend|ascends|squeeze|squeezes|pass|passes|run|runs|hurry|hurries|go|goes|walk|walks')


def _exit_object(words, exit_words):
    names = r'doors?' + (r'|(?:' + exit_words + r')s?' if exit_words else '')
    return re.search(r'\b(?:' + EXIT_OBJECT_VERBS + r')\b(?:\s+[\w\']+){0,3}?\s+(?:' + names + r')\b', words)


# Going back the way the PC came, with no exit named (the exit chooser takes the one they came
# in by). Narrow on purpose: "I go back to the table" is not leaving.
RETRACING = re.compile(r"\b(?:retrace[sd]?|retracing)\b|\bback the way (?:i|we) came\b|"
                       r"\b(?:go|head|walk|turn)s? back (?:out|the way)\b")
GOING_BACK = re.compile(r"\b(?:back|return|returns|retrace[sd]?|retracing|the way (?:i|we) came|came in)\b")


# Moving, in any tense: "Nik steps through the iron door", "she went out" (watchroom playtest).
MOVING = re.compile(r"\b(?:leave|leaves|leaving|left|go|goes|going|went|walk|walks|walked|walking|move|moves|"
                    r"moved|moving|step|steps|stepped|stepping)\b")
# Going in with no exit named: "I step in", "Nik goes inside". The exit chooser takes the
# one exit from here that leads into the room.
GOING_IN = re.compile(r"\b(?:go|goes|went|step|steps|stepped|walk|walks|walked|head|heads|come|comes|move|moves)"
                      r"\s+(?:on\s+|right\s+|back\s+)?(?:in|inside)\b(?!\s+(?:the|a|an|my|his|her)\b)")
# The PC's own open hand is not an act on the room: "I keep my hands open".
_OPEN_EXIT = (r"\b(?:open|opens|opening)\b(?:\s+[\w']+){0,2}?\s+(?:the\s+)?(?:{names})\b"
              r"|\b(?:the\s+)?(?:{names})\b(?:\s+[\w']+){0,1}?\s+(?:open|wider)\b"
              r"|\b(?:hands?|palms?|arms?)\s+open\b"
              # Knocking at an exit is announcing oneself, not an act on the room.
              r"|\b(?:knock|knocks|knocked|knocking|rap|raps|rapped|tap|taps|tapped)\b(?:\s+[\w']+){0,2}?"
              r"\s+(?:on|at)\s+(?:the\s+)?(?:\w+\s+)?(?:{names})\b")


def _opens_an_exit(words, exit_words, strip=False):
    """Opening an exit here (or one's own hands), never passing through it. Exits in this
    model are passable; going through is the exit route, checked first. With ``strip`` the
    words come back without that phrase, so the rest of the action still routes."""
    names = r'doors?' + (r'|(?:' + exit_words + r')s?' if exit_words else '')
    pattern = re.compile(_OPEN_EXIT.replace('{names}', names))
    return pattern.sub(' ', words) if strip else bool(pattern.search(words))


def _bare_name(edge):
    """An exit's name without its article: 'the iron door' -> 'iron door'."""
    return re.sub(r'^(?:the|a|an)\s+', '', str((edge or {}).get('name') or '').casefold().strip())


ADDRESS_WORDS = re.compile(r"\b(you|you're|your|yours|yourself|y'all)\b")
SEATING = re.compile(r"\b(?:take|takes|taking|took)\s+(?:a|the|that|an empty|the empty|my|his|her|their)\s+"
                     r"(?:seat|chair|stool|place)\b|"
                     r"\b(?:move|moves|scoot|scoots|pull|pulls|drag|drags|shift|shifts|edge|edges|slide|slides|"
                     r"turn|turns)\s+(?:my|his|her|their|the|a)\s+(?:chair|stool|seat)\b|\bpull(?:s)? up a chair\b|\b(?:sit|sits|sat|sitting) down\b")
GEAR_SET = re.compile(r"\b(?:sling|slings|slung|stow|stows|strap|straps|set|sets|lay|lays|put|puts|rest|rests|hang|"
                      r"hangs)\b[^.?!]{0,30}\b(?:shield|weapon|sword|axe|bow|crossbow|staff|pack|rapier|mace)\b"
                      r"[^.?!]{0,30}\b(?:on(?:to)? (?:my|his|her|their) back|aside|down|away|against|by (?:my|his|her|their)"
                      r" (?:chair|feet|side)|at (?:my|his|her|their) feet|under the (?:table|chair))\b")
PHYSICAL_VERBS = r'(steal|pocket|grab|pick up|smash|break|hide|climb|force|open|disarm)'
# A declared physical act: "I grab the ring", "I quickly open the door". When an NPC has
# just asked the player something, only this shape still counts as physical; a verb
# inside an answer ("I was hoping to find something to steal") is speech.
DECLARED_PHYSICAL = re.compile(r'(^|[.!;]\s*)(i|i\s+\w+ly)\s+' + PHYSICAL_VERBS + r'\b')


def npc_addressed_player(spoken):
    """True when an NPC line in a public turn asks the player something or speaks to them."""
    for line in (spoken or '').splitlines():
        speaker, _, text = line.partition(':')
        if is_npc_speaker(speaker) and (
                '?' in text or ADDRESS_WORDS.search(text.translate(_TYPOGRAPHIC).lower())):
            return True
    return False


def room_intent(action, addressed=False, room=None):
    """Conservative routing; unrecognized text remains conversation or clarification.

    Only the narration outside quotation marks decides whether an action is
    physical, a check, or combat, so quoted speech ("pay up or I'll kill you")
    routes as a social bid instead of a pending physical ruling.

    `addressed` is True when the previous public turn had an NPC ask the player a
    question or speak to them. Then an unquoted reply that is not clearly a physical
    act is the player answering, i.e. social speech (playtest 03: Nik's plain answer
    to the dealer's question was refused as an unsupported physical action). Combat,
    stealth, exits, and the room's named checks still route as before.

    `room` (RoomWords) carries the room file's own words: its handled features and its
    exits' names. Without it only general words route (a door, "out").
    """
    text = action.translate(_TYPOGRAPHIC)
    room = room or RoomWords()
    if is_ooc(text):
        return 'social'
    quoted = bool(QUOTED_SPEECH.search(text))
    words = QUOTED_SPEECH.sub(' ', text).lower()
    violent = re.compile(r'\b(attack|attacks|stab|stabs|shoot|shoots|kill|kills)\b')
    # A capitalized name mid-sentence is someone ("I attack Uktarl"), in any room.
    names = tuple(word.casefold() for word in re.findall(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z'-]+)",
                                                          QUOTED_SPEECH.sub(' ', text)) if word != 'I')
    if any(kit_combat.aimed_attack(words, verb, names) for verb in violent.finditer(words)) or \
            re.search(r'\b(initiative|fireball)\b', words) or (
            re.search(r'\bcast\b', words) and re.search(r'\b(at|on|against|into)\s+(him|her|them|the|it|his)\b', words)):
        return 'combat'
    if re.search(r'\b(cast|casts|casting)\b', words):
        return 'spell'  # a spell aimed at nobody (Detect Magic, Light...) is not combat
    if THRESHOLD_LOOK.search(words) and THRESHOLD_GAP.search(words) and not MOVE_THROUGH.search(words) and \
            (room.exits or room.inward):
        return 'threshold_look'
    if STEALTH_INTENT.search(words) or (
            re.search(r'\b(quietly|silently|softly)\b', words) and
            re.search(r'\b(walk|move|step|go|leave|head|edge|slip)\w*\b', words) and
            re.search(r'\b(door|past|out)\b', words)):
        return 'stealth'
    feature = room.feature_in(words)
    exit_words = '|'.join(re.escape(word) for word, _ in room.exits)
    named_exit = re.search(r'\bdoors?\b', words) or (exit_words and re.search(r'\b(?:' + exit_words + r')s?\b', words))
    if MOVING.search(words) and (named_exit or (re.search(r'\bout\b', words) and not feature)) or room.inward and GOING_IN.search(words) \
            or re.search(r'\b(head|heads|charge|charges|barge|barges|burst|bursts|continue|continues)\b', words) and named_exit \
            or named_exit and _exit_object(words, exit_words) or RETRACING.search(words):
        return 'exit'
    if feature:
        nouns = re.escape(feature[0]) + 's?'
        if _feature_moved(nouns).search(words):
            return 'move_feature'
        if _feature_entry(nouns).search(words):
            return 'enter_feature'
        if _feature_handled(nouns).search(words):
            # The 6c baseline's contradictory tub rule: a question about what is in a feature
            # went to Kit's invention oracle while the room forbade inventing the contents. The
            # file keys the contents (the feature's ``holds`` fact) and a plain look at a
            # visible feature is free (call 2), so a look or question into it resolves here,
            # from the file, with no invention.
            return 'inspect_feature'
        if re.search(r'\b(look|looks|looking|glance|glances|peer|peers|gaze|gazes)\b', words) and \
                not SOCIAL_WORDS.search(words):
            return 'observe'  # a look toward the feature, not into it: free description
    if OBSERVE.search(words):
        return 'observe'
    if SEATING.search(words) or GEAR_SET.search(words):
        # Sitting down, or slinging, stowing, or setting gear aside, is table business, not a
        # physical ruling ("I sling my shield onto my back and take the seat."): the decision's
        # pc_state records the gear.
        return 'social'
    door_business = bool(named_exit) and _opens_an_exit(words, exit_words)
    if door_business:
        # Opening a passable exit without going through it, from the threshold or with
        # speech ("I ease the door open, stay on the threshold, and hold up empty hands.
        # 'Easy.'"), is table business: every intent is kept in the restated event
        # (watchroom playtest), and the PC stays where they are.
        words = _opens_an_exit(words, exit_words, strip=True)
    # A question is not a declared act (watchroom T3: "Is there anywhere to hide? Could he
    # reach the bell?" stalled as a physical ruling): only the declared sentences count.
    declared = asked_away(words)
    physical = (re.search(r'\b' + PHYSICAL_VERBS + r'\b', declared) or
                (re.search(r'\btake\b', declared) and
                 re.search(r'\b(coins?|ring|gear|key|cards|deck|treasure)\b', declared)))
    if physical and (not addressed or DECLARED_PHYSICAL.search(words.strip()) or
                     re.search(r'(^|[.!;]\s*)i\s+take\b', words.strip())):
        return 'unsupported_action'
    if quoted or door_business or '?' in words or SOCIAL_WORDS.search(words) or ADDRESS_WORDS.search(words) or \
            GESTURE.search(words) or violent.search(words):
        # A violent verb that reached here is aimed at nobody: an idiom or a gesture
        # ("shoot the breeze", "kill time"), which is table talk, not a strike.
        return 'social'
    if addressed:
        return 'social'  # an answer to the question the NPC just asked
    return 'unsupported_action'


def card_procedure(source, state):
    """(id, config, state) of the declared card-game procedure in this room, or None. A canon
    entry Kit recorded with a runnable card-game procedure (a named house game,
    procedure twenty_one) declares that table too: it starts from its initial state."""
    for key, body in (state.get('procedures') or {}).items():
        config = (source or {}).get('procedures', {}).get(key) or {}
        if config.get('kind') == 'card_game':
            return key, config, body
    for entry in (state.get('canon') or {}).values():
        key = entry.get('procedure')
        config = (source or {}).get('procedures', {}).get(key) or {} if key else {}
        if config.get('kind') == 'card_game' and entry.get('area', state.get('area')) == state.get('area'):
            return key, config, kit_cards.initial_state(config)
    return None


def combine(first, second):
    """One resolution for a message with two intents, in order: a card kind names it (the
    table's checks and longer event bound), else the first's; both public results; both
    event lists."""
    if second is None:
        return first
    kinds = [first.kind, second.kind]
    kind = next((k for k in kinds if str(k).startswith('card_')), None) or \
        next((k for k in kinds if str(k).startswith(LONG_EVENT_KINDS)), first.kind)
    public = f'{first.public_event} {second.public_event}'.strip()
    require(len(public) <= CARD_EVENT_MAX_CHARS, 'Combined result exceeds the event bound')
    return Resolution(kind, public, list(first.events) + list(second.events))


class RoomAdjudicator:
    def __init__(self, perception=None, insight=None, roll=None, sleight_of_hand=None, source=None,
                 npc_roll=None):
        self.perception = perception
        self.insight = insight
        self.roll = roll
        self.npc_roll = npc_roll  # the NPC's behind-the-screen d20 (tests); else seeded
        self.sleight_of_hand = sleight_of_hand
        self.source = source  # the mounted room's source; prepare_turn refreshes it every turn
        self.last_said = ''   # Kit's last public line, for the exit in view (one resolve)

    def mount(self, source):
        """Point this adjudicator at the room mounted now. This is the only room-derived
        state it holds: router words, features, exits, procedures, tolls, attitudes and the
        fight config are all read from ``self.source`` on each call, and the texture palette
        cache is keyed by room id (docs/architecture/ROOM_LOADER.md, "Long-lived hosts")."""
        self.source = source

    def resolve(self, action, revision, state, addressed=False, last_said=''):
        self.last_said = last_said or ''
        result = self._also_bet(self._resolve(action, revision, state, addressed), action, revision, state)
        if (self.source or {}).get('tolls'):
            extra = self._toll_unstuck(result, state)
            if extra:
                result = dataclasses.replace(result, events=list(result.events) + extra)
        if (self.source or {}).get('attitudes') and not is_ooc(action):
            # Behind the screen: an NPC may notice what the PC is doing (runtime/kit_attitude.py).
            hidden = kit_attitude.check_events(self.source, state, action, revision,
                                               lambda skill, words: self._pc_score(skill, words, state),
                                               self.npc_roll)
            if hidden:
                result = dataclasses.replace(result, events=list(result.events) + hidden)
        return result

    def _pc_score(self, skill, action, state):
        """The PC's number against an NPC's hidden check: their stated roll in that skill, else
        their passive; None (no check) when no sheet or roll gives one."""
        try:
            modifier, passive = self._pc_numbers(skill, state, action)
        except PendingRuling:
            return None
        supplied = kit_cards.supplied_roll(action, modifier, skill) \
            if kit_rolls.stated_skill(action) == skill else None
        if not supplied:
            return passive
        return supplied[0] + (supplied[1] if supplied[1] is not None else modifier)

    def _resolve(self, action, revision, state, addressed=False):
        require(isinstance(action, str) and action.strip(), 'Player action required')
        narration = QUOTED_SPEECH.sub(' ', action.translate(_TYPOGRAPHIC))
        # Speech and table talk to Kit are never resolved as checks.
        spoken = bool(QUOTED_SPEECH.search(action.translate(_TYPOGRAPHIC))) or is_ooc(action)
        # A physical act changes the world (attacks, grabs, a flipped table, coins taken, paint
        # wiped off): it is resolved before any talk, toll, or card reading of the same words.
        # While a fight waits on initiative or runs, a reported initiative total routes here too.
        if not is_ooc(action) and kit_combat.config(self.source) and asked_away(narration).strip():
            physical = self._resolve_physical(action if asked_away(narration) == narration else
                                              asked_away(narration), revision, state)
            if physical:
                # One message, several intents: an act that starts no fight still carries the
                # card call made with it ("I wipe his cheek. Hit me.").
                return self._also_card(physical, action, narration, revision, state)
        # A toll on the table is a real exchange (call 6): paying, haggling, refusing, and
        # steering back to the game each commit, spoken or not.
        if not is_ooc(action):
            toll = self._resolve_toll(action, revision, state)
            if toll:
                return toll
        if not is_ooc(action) and CHECK_REQUEST.search(narration):
            return self._check_request(action, narration, state)
        called = self._resolve_called(action, revision, state)
        if called:
            return called
        target = kit_claims.roll_target(action, self.source)
        if target and not spoken:
            return self._also_card(self._resolve_knowledge(action, revision, state, *target),
                                   action, narration, revision, state)
        # An Insight read on whether someone is lying is the lie rule, whatever it is about.
        if not spoken and kit_claims.is_lie_read(narration):
            return self._also_card(self._resolve_lie_read(action, narration, revision, state),
                                   action, narration, revision, state)
        table, card_kind = self._card_call(action, narration, state)
        if card_kind == 'card_accuse' and kit_attitude.quiet(narration) and \
                kit_rolls.stated_skill(action) in SOCIAL_CHECK_SKILLS:
            # A quiet word with a stated roll is a private accusation: a social check on the
            # accused, not the table's public call (live 6c: a quiet word and a failed Intimidation).
            return self._resolve_social_check(kit_rolls.stated_skill(action), action, narration, revision,
                                              state, private=True)
        kind = room_intent(action, addressed, room_words(self.source, state))
        # Combat and stealth keep their rulings at the card table: "I raise my crossbow" is
        # not a raise, and sneaking out "while they check their hands" is not a check.
        # A sleight at the table ("unseen") stays a card swap.
        # Looking around the room is about something else: the table procedure recedes
        # (state kept, no forced choice) unless the player is watching the table itself.
        overrides = kind in ('combat', 'observe', 'spell') and card_kind != 'card_watch' or \
            (kind == 'stealth' and card_kind != 'card_swap')
        if card_kind and not overrides:
            card = self._resolve_card(card_kind, action, revision, state, table)
            # A bet and a stated read in one message: both resolve (the read of the cards or
            # the people the roll names), the card call first.
            return combine(card, self._stated_read(action, narration, revision, state, kind, card_kind))
        # A roll the player makes in conversation counts (6c baseline item 3): Deception,
        # Persuasion, Intimidation, Performance, or Athletics against the NPC's flat number;
        # Insight reads whoever spoke (the lie rule) or the group's hidden claim.
        stated = kit_rolls.stated_skill(action)
        if stated in SOCIAL_CHECK_SKILLS and kind not in ('combat', 'stealth', 'exit', 'spell'):
            return self._also_card(self._resolve_social_check(stated, action, narration, revision, state),
                                   action, narration, revision, state)
        if stated == 'insight' and spoken and kind not in ('combat', 'stealth', 'exit', 'spell'):
            who = self._lie_read_target(narration, state)
            if who and any(r.get('by') == who for r in (state.get('claims') or {}).get('said') or []):
                return self._resolve_lie_read(action, narration, revision, state)
            claim = self._group_claim(state)
            if claim:
                return self._resolve_check(action, revision, state, *claim)
            if who:
                return self._resolve_lie_read(action, narration, revision, state)
        # "I study them; something's off": a read of the group goes to the hidden Insight
        # claim about who they are (call 3: the clue invites a check that works).
        if not spoken and kind not in ('combat', 'stealth', 'exit', 'spell') and GROUP_READ.search(narration):
            claim = self._group_claim(state)
            if claim:
                return self._resolve_check(action, revision, state, *claim)
        # An active look or read at something hidden: the claim it names, and only that claim.
        # Speech in the same message does not cancel a stated roll at something hidden.
        reading = not is_ooc(action) and kit_rolls.stated_skill(action) is not None
        check = None if (spoken and not reading) or kind in ('combat', 'stealth', 'exit', 'spell') else \
            kit_claims.check_target(narration, self.source, state)
        if check:
            return self._resolve_check(action, revision, state, *check)
        if not spoken and '?' not in narration and re.search(r'\binsight\b', narration, re.I) and \
                kind not in ('combat', 'stealth', 'exit'):
            # The situation settles a bare Insight: read whoever spoke to the PC last (or the
            # only person here) for a lie. Ask only when nobody is there to read.
            if self._lie_read_target(narration, state):
                return self._resolve_lie_read(action, narration, revision, state)
            claim = self._group_claim(state)
            if claim:
                return self._resolve_check(action, revision, state, *claim)
            raise PendingRuling('What are you reading with Insight: whether someone is telling the truth, '
                                'or something about how they look or act? No turn was committed.')
        if kind == 'combat' and kit_rolls.initiative(action) is not None and not kit_combat.parse(
                action, self.source, state):
            raise PendingRuling('Nobody here is fighting you, so there is no initiative to roll yet. '
                                'No turn was committed.')
        if kind == 'combat':
            raise PendingRuling('Who are you attacking, and with what? Name the target and the weapon or '
                                'spell (with the Avrae roll if you have it). No turn was committed.')
        if kind == 'spell':
            raise PendingRuling('Spell effects outside combat are not resolved in this slice yet, so the '
                                'spell is not cast. No turn was committed.', attempt=True)
        if kind == 'threshold_look':
            return self._threshold_look(action, state)
        if kind == 'stealth':
            return self._resolve_stealth(action, narration, revision, state)
        if kind == 'unsupported_action':
            raise PendingRuling('This physical action needs a room/rules ruling beyond the test slice. No turn was committed.', attempt=True)
        if kind == 'observe':
            around = not re.search(r"\b(?:at|interesting|notable)\b", action.lower())
            event = {'type': 'beat', 'tags': ['observe'],
                     'evidence': f'Player declared: {action}. Resolution: they look '
                                 f'{"around the room" if around else "at what is plainly visible"}; free description, '
                                 'no roll; nothing hidden is learned; nothing changes.'}
            return Resolution(kind, 'You look around the room.' if around else 'You take a look.', [event])
        if kind == 'exit':
            key = self._exit_taken(action, state)
            blocked = self._exit_blocked(key, state, revision)
            if blocked:
                return blocked
            event = {'type': 'move', 'exit': key, 'evidence': f'The player explicitly left by the known exit {key}.'}
            return Resolution(kind, self._exit_text(key, state, 'go'), [event])
        if kind in ('move_feature', 'inspect_feature', 'enter_feature'):
            noun, key = room_words(self.source, state).feature_in(narration.lower()) or \
                room_words(self.source, state).feature_in(action.lower())
            handling = self.source['facts'][key]['handling']
            text = handling.get({'move_feature': 'move', 'inspect_feature': 'look',
                                 'enter_feature': 'enter'}[kind])
            if not text:
                raise PendingRuling(f'The room file gives no ruling for that with the {noun}. No turn was committed.',
                                    attempt=True)
            if kind == 'move_feature' or not handling.get('holds'):
                public = text
            else:
                event = {'type': 'reveal_fact', 'fact': handling['holds'],
                         'evidence': f'The player explicitly {"looked inside" if kind == "inspect_feature" else "got into"} '
                                     f'the {noun} ({key}), which shows what it holds.'}
                return Resolution(kind, text, [event])
        else:
            # Social bid: restate the player's actual words. No outcome, NPC
            # commitment, or hidden fact is added; the full text stays in evidence.
            event = {'type': 'beat', 'tags': [kind],
                     'evidence': f'Player declared: {action}. Resolution: social bid, '
                                 'restated as the accepted event; no world state changed.'}
            return Resolution(kind, social_event(action), [event])
        event = {'type': 'beat', 'tags': [kind],
                 'evidence': f'Player declared: {action}. Resolution: {public}'}
        return Resolution(kind, public, [event])

    # -- perception at a threshold, and asking for a check (watchroom T1-T3) ---------
    def _threshold_exit(self, action, state):
        """The exit the PC is looking or listening through: the one named, else the one way
        in from here, else None."""
        try:
            return self._exit_taken(action, state)
        except PendingRuling:
            inward = room_words(self.source, state).inward
            return inward[0] if len(inward) == 1 else None

    def _threshold_look(self, action, state):
        key = self._threshold_exit(action, state)
        name = ((self.source or {}).get('exits') or {}).get(key, {}).get('name') or 'the way on'
        listening = re.search(r'\b(?:listen\w*|eavesdrop\w*|ears?)\b', action.casefold()) and \
            not re.search(r'\b(?:peek\w*|peer\w*|look\w*|eyes?|watch\w*|see)\b', action.casefold())
        public = f'You {"listen" if listening else "look"} at {name} without going through.'
        event = {'type': 'beat', 'tags': ['threshold'] + ([key] if key else []),
                 'evidence': f'Player declared: {action[:300]}. Resolution: perception at a threshold '
                             f'({key or "no exit named"}), not movement; the PC stays where they are.'}
        return Resolution('threshold_look', public, [event])

    def _check_request(self, action, narration, state):
        """The player asks for a check. Nothing is rolled: Kit calls one (roll_call) or declines.
        Every other intent in the message stays in the public event (the questions, the watching)."""
        words = social_event(action)[len(SOCIAL_EVENT_PREFIX):]
        tags = ['check_request']
        threshold = THRESHOLD_LOOK.search(narration.lower()) and THRESHOLD_GAP.search(narration.lower()) and \
            not MOVE_THROUGH.search(narration.lower())
        key = self._threshold_exit(action, state) if threshold else None
        if key:
            tags += ['threshold', key]
        named = kit_rolls.stated_skill(action)
        event = {'type': 'beat', 'tags': tags,
                 'evidence': f'Player asked for a check: {action[:300]}. Nothing rolled; '
                             f'{"they named " + named + " (a request)" if named else "no skill named"}. '
                             'Kit calls a check or declines.'}
        return Resolution('check_request', f'{CHECK_REQUEST_PREFIX}{words}', [event])

    # -- social checks rolled in conversation -----------------------------------------
    def _resolve_social_check(self, skill, action, narration, revision, state, private=False, who=None):
        """The player's stated roll in a social skill against the NPC they address (or, for a
        check Kit called, ``who``, the call's target): that NPC's flat 10 + Insight (10 +
        Athletics for a contest of strength). NPCs never roll. A bare number is the Avrae
        total (runtime/kit_rolls.py). Numbers stay in evidence."""
        present = self._present_actors(state)
        who = who if who in present else self._lie_read_target(narration, state)
        if who is None:
            leader = kit_combat.config(self.source).get('leader')
            who = leader if leader in present else next(iter(present), None)
        if who is None:
            raise PendingRuling('Who are you trying that on? Nobody here is listening. No turn was committed.')
        actor = state['actors'][who]
        against = 'athletics' if skill == 'athletics' else 'insight'
        flat = kit_claims.npc_passive(actor, against)
        modifier, _ = self._pc_numbers(skill, state, action)
        die = self._die(state, revision, f'social:{skill}:{who}', action, modifier, skill)
        total = die + modifier
        success = total >= flat
        label = (actor_speakers(self.source).get(who) or actor.get('name') or who).lower()
        public = SOCIAL_OUTCOMES[skill][0 if success else 1].format(who=f'the {label}')
        public = public[0].upper() + public[1:]
        name = skill.replace('_', ' ').title()
        evidence = (f'Player declared: {action[:300]}. {name} d20 {die} + {modifier} = {total} vs {who} '
                    f'flat 10 + {against.title()} = {flat}: {"success" if success else "failure"}. '
                    'The NPC acts on this outcome.')
        tags = ['social_check', skill] + (['private_accusation'] if private else [])
        if private:
            evidence += ' A quiet word to them, not a public accusation: the table is not called out.'
        # The social-roll hook: the outcome moves the NPC's attitude (runtime/kit_attitude.py).
        moved = kit_attitude.social_roll(self.source, state, who, skill, success, evidence)
        return Resolution('social_check', public, [{'type': 'beat', 'tags': tags, 'evidence': evidence}] + moved)

    # -- physical acts and fights (runtime/kit_combat.py) -----------------------------
    # -- one message, several intents ----------------------------------------------
    def _card_call(self, action, narration, state):
        """(table, card kind) for this message: the running table, or the room's offered game
        when the words declare it (call 7: "I play", a bet, the game's name, a spoken "Deal.").
        A game in the room never starts on its own."""
        table = card_procedure(self.source, state)
        if table is None and not is_ooc(action) and ((PLAY_REQUEST.search(narration.casefold()) and
                                                      '?' not in narration) or
                                                     SPOKEN_BET.search(kit_rolls.without_rolls(action)) or
                                                     kit_twenty_one.SPOKEN_DEAL.search(action.translate(_TYPOGRAPHIC)) or
                                                     self._game_called(action)):
            table = self._declared_table(state)
        return table, (kit_cards.card_intent(action, table[2]) if table else None)

    def _game_called(self, action):
        declared = self._declared_table({})
        return bool(declared and kit_cards.game_called(declared[1], kit_rolls.without_rolls(action)))

    def _also_bet(self, result, action, revision, state):
        """``result`` plus a new stake for the next hand named in the same message, when the
        ruling was not a card call itself (a read, a check, talk) and started no fight. Seated
        at a table, "Twenty gold on the next hand. Insight 14 on the dealer." keeps the bet
        (6c backlog a: it was dropped) and says so."""
        if str(result.kind).startswith(('card_', 'combat_')) or is_ooc(action):
            return result
        table = card_procedure(self.source, state)
        if not table or not kit_cards.next_bet(action, table[2]):
            return result
        try:
            return combine(result, self._resolve_card('card_bet', action, revision, state, table))
        except PendingRuling:
            return result

    def _also_card(self, result, action, narration, revision, state):
        """``result`` plus the card call made in the same message, when there is one and the
        first ruling started no fight. The card call resolves on the same pre-turn state."""
        if result is None or result.kind == 'combat_round' or str(result.kind).startswith('card_') \
                or is_ooc(action):
            return result
        table, card_kind = self._card_call(action, narration, state)
        if not card_kind or card_kind in ('card_watch', 'card_leave', 'card_accuse'):
            return result
        try:
            card = self._resolve_card(card_kind, action, revision, state, table)
        except PendingRuling:
            return result
        return combine(result, card)

    def _stated_read(self, action, narration, revision, state, kind, card_kind):
        """A stated observation or Insight roll at a hidden claim, made in the same message as
        a card call, or None. Watching the deal is the card call's own read."""
        stated = kit_rolls.stated_skill(action)
        if kind in ('combat', 'stealth', 'exit', 'spell') or stated is None or \
                (card_kind == 'card_watch' and stated == 'perception'):
            return None
        check = kit_claims.check_target(narration, self.source, state)
        if check is None and kit_rolls.stated_skill(action) == 'insight':
            check = self._group_claim(state)
        if check is None:
            return None
        try:
            return self._resolve_check(action, revision, state, *check)
        except PendingRuling:
            return None

    def _resolve_physical(self, action, revision, state):
        act = kit_combat.parse(action, self.source, state)
        current = state.get('combat') or {}
        fighting = current.get('status') in ('awaiting_initiative', 'running')
        if not act and not (fighting and kit_rolls.initiative(action) is not None):
            return None
        if act and act['kind'] == 'grab' and act.get('wrist'):
            table = card_procedure(self.source, state)
            if table and kit_cards.card_intent(action, table[2]) == 'card_accuse':
                return None  # catching the dealer's wrist mid-deal is the accusation itself
        fight = kit_combat.Fight(self.source, state, revision, action,
                                 check=lambda skill, dc, label: self._check(skill, dc, state, revision,
                                                                            f'physical:{label}', action),
                                 roll=self.roll)
        before = copy.deepcopy(state.get('combat'))
        public, events = fight.resolve(act)
        if fight.needs_roll and not fight.reveals:
            # Nothing happened yet: the blow waits on its Avrae roll. The fight's start
            # (initiative) waits with it, so no turn is committed.
            fight.fight = before
            raise PendingRuling(f'{public.replace(" Roll initiative.", "")} No turn was committed.')
        if not public:
            return None
        events = list(events) + [{'type': 'reveal_fact', 'fact': fact,
                                  'evidence': f'Player declared: {action[:300]}. The act shows it.'}
                                 for fact in fight.reveals if fact not in state.get('known_facts', [])]
        kind = 'combat_round' if fight.fight else 'physical_act'
        return Resolution(kind, public, events)

    # -- general checks: any room, any PC -------------------------------------------
    def _die(self, state, revision, label, action, modifier=None, skill=None):
        """The player's own stated d20 (an Avrae total is worked back with ``modifier``, so
        the bonus is never added twice), else a stable seeded roll (an uncommitted model
        failure must not reroll the same attempted check)."""
        supplied = kit_cards.supplied_roll(action, modifier, skill)
        if supplied:
            return supplied[0]
        if self.roll:
            return self.roll()
        if 'roll_seed' not in state:
            raise PendingRuling('This session predates stable checks; start a fresh database.')
        material = f"{state['roll_seed']}:{revision}:{label}:{action.casefold()}".encode()
        return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1

    def _pc_numbers(self, skill, state, action):
        """(modifier, passive) for the PC: a stated "d20 + modifier = total" wins, then a
        host override, then the loaded sheet. Passive is 10 + modifier unless the sheet
        knows better (advantage in force)."""
        override = getattr(self, skill, None)
        sheet = pc_sheet.sheet_now(state)  # unset lists: the situation's default, never a block
        if override is not None:
            modifier, passive = override, 10 + override
        elif sheet:
            modifier, passive = pc_sheet.skill_bonus(sheet, skill), pc_sheet.passive(sheet, skill)
        else:
            modifier = passive = None
        supplied = kit_cards.supplied_roll(action, modifier, skill)
        if supplied and supplied[1] is not None:
            modifier = supplied[1]
            passive = passive if passive is not None else 10 + modifier
        if modifier is None:
            name = skill.replace('_', ' ').title()
            raise PendingRuling(f'Load a character sheet or state the {name} roll from Avrae '
                                f'(e.g. "{name} 16") before this check. No turn was committed.')
        return modifier, passive

    def _check(self, skill, dc, state, revision, label, action):
        modifier, passive = self._pc_numbers(skill, state, action)
        return kit_claims.pc_check(dc, modifier, passive,
                                   lambda: self._die(state, revision, label, action, modifier, skill))

    def _present_actors(self, state):
        return {key: actor for key, actor in (state.get('actors') or {}).items()
                if actor.get('location') == state['area'] and actor.get('status') not in ('fled', 'dead')}

    BLOCKERS_UNABLE = ('asleep', 'unconscious', 'restrained', 'bound', 'paralyzed', 'stunned')

    def _exit_blockers(self, key, state):
        """Who stands between the PC and exit ``key``: an awake actor here (within reach of the
        PC and the exit) who is hostile, or who guards that exit (room data ``guards``) and is
        not friendly. Everyone else lets the PC go."""
        found = []
        for who, actor in self._present_actors(state).items():
            if actor.get('status') in self.BLOCKERS_UNABLE or actor.get('status') in kit_attitude.GONE:
                continue
            attitude = kit_attitude.level(self.source, state, who)
            if attitude == 'hostile' or key in (actor.get('guards') or ()) and attitude not in ('friendly', 'helpful'):
                found.append(who)
        return found

    def _exit_blocked(self, key, state, revision):
        """Leaving past someone who can stop it is not automatic (watchroom playtest: the PC
        took the back stair with the armed warden beside it). The move is held as a pending
        check: the player's Athletics or Acrobatics against the blocker; only a success moves
        the PC. An unblocked exit stays instant."""
        blockers = self._exit_blockers(key, state)
        if not blockers:
            return None
        who = blockers[0]
        label = actor_speakers(self.source).get(who) or state['actors'][who].get('name') or who
        exit_name = _bare_name((self.source.get('exits') or {}).get(key)) or key
        check = {'skill': 'athletics', 'ability': 'str', 'target': who, 'called_turn': f'revision {revision}',
                 'exit': key}
        public = (f'The {label.lower()} is between you and the {exit_name}. Getting past is a contest: '
                  'roll Athletics or Acrobatics.')
        evidence = (f'The player tried to leave by {key}; {", ".join(blockers)} can stop it. '
                    'The move is held for a contest (Athletics or Acrobatics vs the blocker); nothing moved.')
        return Resolution('exit_contested', public,
                          [{'type': 'beat', 'tags': ['exit_contested'], 'evidence': evidence},
                           {'type': 'pending_check', 'check': check, 'evidence': evidence}])

    def _resolve_held_exit(self, pending, total_text, revision, state):
        """The contest for a held exit: the PC's Athletics or Acrobatics against the blocker's
        flat 10 + Athletics. Success moves the PC through; failure keeps them here."""
        key, who = pending['exit'], pending['target']
        stated = kit_rolls.stated_skill(total_text)
        skill = stated if stated in ('athletics', 'acrobatics') else 'athletics'
        actor = state['actors'].get(who) or {}
        flat = kit_claims.npc_passive(actor, 'athletics')
        modifier, _ = self._pc_numbers(skill, state, total_text)
        die = self._die(state, revision, f'exit:{key}:{who}', total_text, modifier, skill)
        total = die + modifier
        clear = {'type': 'pending_check', 'check': None, 'evidence': f'The contest for {key} is rolled.'}
        evidence = (f'Contest to leave by {key} past {who}: {skill} d20 {die} + {modifier} = {total} vs flat 10 + '
                    f'Athletics = {flat}: {"success" if total >= flat else "failure"}.')
        label = (actor_speakers(self.source).get(who) or actor.get('name') or who).lower()
        if total >= flat:
            return Resolution('exit', f'You get past the {label}. ' + self._exit_text(key, state, 'go'),
                              [{'type': 'beat', 'tags': ['exit_contested'], 'evidence': evidence},
                               {'type': 'move', 'exit': key, 'evidence': evidence}, clear])
        return Resolution('exit_contested', f'The {label} keeps you from the {_bare_name(self.source["exits"][key]) or key}.',
                          [{'type': 'beat', 'tags': ['exit_contested'], 'evidence': evidence}, clear])

    def _resolve_called(self, action, revision, state):
        """A bare roll ("Perception 22", "22", "I rolled a 22") answering the check Kit called
        last turn (watchroom playtest: the roll stalled). It resolves against the one hidden
        claim here that the called skill finds and that matches the call's target; with none,
        the roll is recorded and reveals nothing. Either way the call is cleared."""
        pending = state.get('pending_check')
        if not pending or is_ooc(action):
            return None
        skill, text = pending['skill'], action.translate(_TYPOGRAPHIC).strip()
        if pending.get('exit'):
            skill = kit_rolls.stated_skill(text) if kit_rolls.stated_skill(text) in ('athletics', 'acrobatics') else skill
        bare = re.fullmatch(r'(?:i\s+)?(?:rolled|roll|got)?\s*(?:an?\s+)?(\d{1,2})\s*[.!]?', text, re.I)
        stated = [roll for roll in kit_rolls.rolls(text) if roll.label not in ('attack', 'initiative')]
        rest = re.sub(r"\b(?:i|rolled|roll|got|a|an|check|for|my|it's|that's|that|is|" +
                      skill.replace('_', r'\s+') + r")\b|[\W\d_]+", ' ', kit_rolls.without_rolls(text).casefold())
        if not (bare or len(stated) == 1 and stated[0].label in (None, skill) and not rest.strip()):
            return None
        total = int(bare.group(1)) if bare else stated[0].total
        roll_text = text if not bare and stated[0].label == skill else f'{skill.replace("_", " ")} {total}'
        clear = {'type': 'pending_check', 'check': None,
                 'evidence': f'The {skill} check called on turn {pending["called_turn"]} is rolled.'}
        target, area = pending['target'], state.get('area')
        if pending.get('exit'):
            return self._resolve_held_exit(pending, roll_text, revision, state)
        if skill in SOCIAL_CHECK_SKILLS:
            # A called social check is resolved like a stated one, against the call's target,
            # and its outcome moves that NPC's attitude in state (watchroom playtest: a failed
            # Persuasion was narrated and nothing recorded).
            result = self._resolve_social_check(skill, roll_text, roll_text, revision, state,
                                                who=target if target != 'none' else None)
            return Resolution(result.kind, result.public_event, list(result.events) + [clear])
        learned = set((state.get('claims') or {}).get('learned') or ())
        found = []
        for key, claim in kit_claims.compile_claims(self.source or {}).items():
            fact_id = claim.get('fact') or ''
            fact = ((self.source or {}).get('facts') or {}).get(fact_id, {})
            if claim.get('exposure') == 'hidden' and key not in learned and fact.get('area') == area and \
                    skill in kit_claims.claim_skills(claim) and \
                    target in ('none', claim.get('concealer'), fact_id, key):
                found.append((key, claim))
        if len(found) == 1:
            result = self._resolve_check(roll_text, revision, state, *found[0])
            return Resolution(result.kind, result.public_event, list(result.events) + [clear])
        modifier, _ = self._pc_numbers(skill, state, roll_text)
        die = self._die(state, revision, f'called:{pending["called_turn"]}:{skill}', roll_text, modifier, skill)
        evidence = (f'Player rolled the {skill} check Kit called on turn {pending["called_turn"]} '
                    f'(target {target}): d20 {die} + {modifier} = {die + modifier}.')
        return Resolution('called_check', f'You roll {skill.replace("_", " ").title()}: {total}.',
                          [{'type': 'beat', 'tags': ['check'], 'evidence': evidence}, clear])

    def _resolve_check(self, action, revision, state, claim_id, claim):
        """An active look or read at one hidden claim, against that claim's single DC.
        Success shows that claim and nothing else; failure shows only the roll. The skill
        the player chose gates what it can show (Brendon's skill rule): Insight the motive,
        Perception and Investigation the physical tells; a skill that finds nothing about
        it rolls and shows nothing."""
        chosen = kit_claims.chosen_skill(action, implied=False)
        gated = kit_claims.gated_claim(self.source, state, claim_id, claim, chosen)
        if gated is None:
            modifier, passive = self._pc_numbers(chosen, state, action)
            die = self._die(state, revision, f'check:{claim_id}:{chosen}', action, modifier, chosen)
            evidence = (f'Player checked {claim_id} with {chosen}: d20 {die} + {modifier} = {die + modifier}; '
                        f'{chosen} does not reveal it (it takes {"/".join(kit_claims.claim_skills(claim))}).')
            return Resolution('check', 'You find nothing you can be sure of.',
                              [{'type': 'beat', 'tags': ['check'], 'evidence': evidence}])
        claim_id, claim = gated
        # The named skill when it finds this claim; for a claim several skills find, the one
        # the player's verb implies ("I examine the fangs" is Investigation); else its own.
        implied = kit_claims.chosen_skill(action) if claim.get('pc_checks') else None
        skill = next((s for s in (chosen, implied) if s in kit_claims.claim_skills(claim)), claim['pc_check'])
        dc = kit_claims.claim_dc(claim, state.get('actors', {}),
                                 kit_claims.current_floor_level(self.source, state.get('area')))
        result = self._check(skill, dc, state, revision, f'check:{claim_id}', action)
        evidence = f'Player actively checked {claim_id}: {kit_claims.check_evidence(skill, result)}.'
        details = None
        if skill == 'perception' and claim.get('perception_details'):
            # Details scale with the result: a stated roll above an automatic passive counts.
            best = result['total']
            if result.get('auto'):
                modifier, _ = self._pc_numbers(skill, state, action)
                supplied = kit_cards.supplied_roll(action, modifier, skill)
                if supplied:
                    best = max(best, supplied[0] + (supplied[1] if supplied[1] is not None else modifier))
            details = kit_claims.perception_details(claim, best - dc)
        if details is not None and result['success']:
            # A snapshot: what is seen, never what it means (the claim stays unlearned).
            known = set(state.get('known_facts', []))
            facts = self.source['facts']
            events = [{'type': 'reveal_fact', 'fact': fact, 'evidence': evidence} for fact in details
                      if fact not in known]
            events.append({'type': 'beat', 'tags': ['check', 'noticed'],
                           'evidence': f'{evidence} Perception details only ({len(details)} of '
                                       f'{len(claim["perception_details"])}); no conclusion.'})
            return Resolution('check', ' '.join(facts[fact]['text'] for fact in details), events)
        if result['success']:
            text = claim.get('learned_text') or claim['truth']
            events = [{'type': 'claim_learned', 'claim': claim_id, 'evidence': evidence}]
            if claim.get('fact') and claim['fact'] not in state.get('known_facts', []):
                events.append({'type': 'reveal_fact', 'fact': claim['fact'], 'evidence': evidence})
            events.append({'type': 'beat', 'tags': ['check'], 'evidence': evidence})
            return Resolution('check', text, events)
        return Resolution('check', 'You find nothing you can be sure of.',
                          [{'type': 'beat', 'tags': ['check'], 'evidence': evidence}])

    def _lie_read_target(self, narration, state):
        """Whose words the player is reading: the actor they name, else whoever spoke to
        them last, else the only person present."""
        present = self._present_actors(state)
        text = narration.casefold()
        speakers = actor_speakers(self.source)
        for key, actor in present.items():
            names = {key.replace('_', ' '), actor.get('name', ''), speakers.get(key, '')}
            names |= set((((self.source or {}).get('texture_palette') or {}).get('areas', {})
                          .get(state['area'], {}).get('subjects', {}).get(f'actor:{key}')) or ())
            if any(n and re.search(rf"\b{re.escape(n.casefold())}\b", text) for n in names):
                return key
        for record in reversed((state.get('claims') or {}).get('said') or []):
            if record.get('by') in present:
                return record['by']
        return next(iter(present)) if len(present) == 1 else None

    def _resolve_lie_read(self, action, narration, revision, state):
        """Brendon's lie rule, used whatever the lie is about: the NPC's flat 10 + Deception
        against the PC's passive Insight (automatic when it meets), else the PC's active
        Insight roll against that same number. The result is only whether they are being
        straight; it never prints a secret."""
        who = self._lie_read_target(narration, state)
        if who is None:
            raise PendingRuling('Whose words are you weighing? Name who you are reading. No turn was committed.')
        actor = state['actors'][who]
        dc = kit_claims.lie_dc(kit_claims.npc_profile(actor))
        result = self._check('insight', dc, state, revision, f'lie:{who}', action)
        label = actor_speakers(self.source).get(who) or actor.get('name') or who
        said = [r for r in (state.get('claims') or {}).get('said') or [] if r.get('by') == who]
        stance = said[-1]['stance'] if said else None
        evidence = (f'Player read {who} for a lie: {kit_claims.check_evidence("insight", result)} '
                    f'(10 + Deception); last recorded stance {stance or "none"}.')
        if not result['success']:
            public = f'The {label.lower()} gives you nothing to read.'
        elif stance == 'lie':
            public = f'The {label.lower()} is lying to you about that.'
        elif stance in ('boast', 'bargain'):
            public = f'The {label.lower()} is selling it harder than it deserves.'
        elif stance == 'hedge':
            public = f'The {label.lower()} is choosing every word carefully.'
        else:
            public = f'As far as you can tell, the {label.lower()} means it.'
        return Resolution('lie_read', public, [{'type': 'beat', 'tags': ['lie_read'], 'evidence': evidence}])

    def _resolve_stealth(self, action, narration, revision, state):
        """Stealth is the PC's roll against the best passive Perception among the people
        present ("passive Perception is an AC against being snuck up on"). Nobody present
        to notice: no roll."""
        present = self._present_actors(state)
        watchers = {key: kit_claims.npc_passive(actor, 'perception') for key, actor in present.items()}
        words = room_words(self.source, state)
        leaving = bool(re.search(r'\b(door|out|leave|past)\b', narration, re.I) or any(
            re.search(r'\b' + re.escape(word) + r'\b', narration, re.I) for word, _ in words.exits))
        key = self._exit_taken(action, state) if leaving and not watchers else None
        exit_event = {'type': 'move', 'exit': key, 'evidence': f'The player left by the known exit {key}, unnoticed.'}
        if not watchers:
            public = self._exit_text(key, state, 'slip') if leaving else 'You move without a sound.'
            return Resolution('stealth', public, [exit_event] if leaving else
                              [{'type': 'beat', 'tags': ['stealth'], 'evidence': f'Player declared: {action}. Nobody present.'}])
        dc = max(watchers.values())
        modifier, _ = self._pc_numbers('stealth', state, action)
        die = self._die(state, revision, 'stealth', action, modifier, 'stealth')
        total = die + modifier
        evidence = (f'Player tried Stealth: d20 {die} + {modifier} = {total} vs best passive Perception {dc} '
                    f'({", ".join(f"{k} {v}" for k, v in watchers.items())}).')
        if total >= dc:
            if leaving:
                key = self._exit_taken(action, state)
                exit_event = dict(exit_event, exit=key)
            public = self._exit_text(key, state, 'unseen') if leaving else 'You move without drawing an eye.'
            beat = {'type': 'beat', 'tags': ['stealth'], 'evidence': evidence}
            return Resolution('stealth', public, ([dict(exit_event, evidence=evidence)] if leaving else
                                                  self._hidden_events(state, True, evidence)) + [beat])
        return Resolution('stealth', 'Eyes at the table turn your way before you get far.',
                          self._hidden_events(state, False, evidence) +
                          [{'type': 'beat', 'tags': ['stealth', 'noticed'], 'evidence': evidence}])

    def _exit_taken(self, action, state):
        """The known exit from here that the player means (docs/architecture/ROOM_LOADER.md,
        "Which exit"). The most specific match wins: the whole name, then words no other exit
        here shares. A tie on shared words ("the door") narrows to the exit in view (named in
        Kit's last line) or, when the player says they go back, the one they came in by, but
        only when that leaves exactly one. Otherwise Kit asks which in one short line, and
        nothing is committed."""
        source, area = self.source or {}, state.get('area')
        exits = source.get('exits') or {}
        here = [key for key in state.get('known_exits') or ()
                if area in (exits.get(key) or {}).get('areas', ())]
        if not here:
            raise PendingRuling('There is no way out from here that you know of yet. No turn was committed.')
        text = action.casefold()
        words = {}
        for word, key in room_words(source, state).exits:
            words.setdefault(key, set()).add(word)
        shared = {}
        for key_words in words.values():
            for word in key_words:
                shared[word] = shared.get(word, 0) + 1
        said = lambda phrase, where=text: bool(phrase) and re.search(
            r'\b' + re.escape(phrase) + r's?\b', where) is not None
        score = {}
        for key in here:
            hit = {word for word in words.get(key, ()) if said(word)}
            if hit:
                score[key] = (said(_bare_name(exits[key])), sum(shared[w] == 1 for w in hit), len(hit))
        best = max(score.values(), default=None)
        tied = [key for key in here if score.get(key) == best] if score else here
        if not score and GOING_IN.search(QUOTED_SPEECH.sub(' ', text.translate(_TYPOGRAPHIC))):
            inside = set(kit_rooms.room_areas(source))
            inward = [key for key in tied if area not in inside and inside & set(exits[key].get('areas', ()))]
            tied = inward or tied
        if len(tied) > 1:
            heard = self.last_said.casefold()
            preferred = {key for key in tied if said(_bare_name(exits[key]), heard)}
            came_by = (state.get('room') or {}).get('came_by')
            if came_by in tied and GOING_BACK.search(text):
                preferred.add(came_by)
            if len(preferred) == 1:
                tied = list(preferred)
        if len(tied) == 1:
            self._check_onward(tied[0], state)
            return tied[0]
        names = ['the ' + _bare_name(exits[key]) if _bare_name(exits[key]) else key for key in tied]
        ask = (' or '.join(names) if len(names) == 2 else ', '.join(names[:-1]) + ', or ' + names[-1]) + '?'
        raise PendingRuling(ask[0].upper() + ask[1:] + ' No turn was committed.')

    def _check_onward(self, key, state):
        """An exit into an area linked to another room file: that room must mount before
        the move is accepted. If it cannot, Kit says the plain table line and nothing is
        committed; the host gets the error naming what is missing (ROOM_LOADER.md)."""
        source = self.source or {}
        edge = (source.get('exits') or {}).get(key) or {}
        there = next((a for a in edge.get('areas', ()) if a != state.get('area')), None)
        link = ((source.get('areas') or {}).get(there) or {}).get('room_link')
        if link:
            # The commit mounts again inside its transaction; this read is what turns a room
            # that can't mount into Kit's plain line before the move is accepted (a failure at
            # commit is only a host rejection). Same function, so the two can't disagree.
            moved = copy.deepcopy(state)
            moved['area'] = there
            try:
                kit_rooms.arrive(source, moved, link)
            except kit_rooms.RoomMountError as exc:
                pending = PendingRuling(f'{exc.table_line} No turn was committed.')
                pending.host_error = exc.host_view()
                raise pending from None

    def _exit_text(self, key, state, how):
        """The line for going through an exit, from the room file (exit ``go_text`` per area,
        else its name and where it leads)."""
        source, area = self.source or {}, state.get('area')
        edge = (source.get('exits') or {}).get(key) or {}
        told = (edge.get('go_text') or {}).get(area)
        if told and how == 'go':
            return told
        name = edge.get('name') or 'the way out'
        there = next((a for a in edge.get('areas', ()) if a != area), None)
        place = ((source.get('areas') or {}).get(there) or {}).get('called')
        if how in ('slip', 'unseen'):
            return f'You slip out through {name}' + (' unnoticed.' if how == 'unseen' else '.')
        into = place and _bare_name({'name': place}) != _bare_name(edge)  # not "the gate into the gate"
        return f'You go through {name}' + (f' into {place}.' if into else '.')

    def _hidden_events(self, state, hidden, evidence):
        """A PC hidden from everyone present surprises them if a fight starts (kit_combat)."""
        if not kit_combat.config(self.source):
            return []
        scene = kit_combat.scene(state)
        if bool(scene.get('pc_hidden')) == hidden:
            return []
        scene['pc_hidden'] = hidden
        return [{'type': 'scene_state', 'state': scene, 'evidence': evidence}]

    def _resolve_knowledge(self, action, revision, state, claim_id, claim):
        """A player-initiated knowledge roll (History, Arcana...) against a claim's DC.
        Only the player starts one; the runtime never rolls knowledge unprompted."""
        skill = claim['pc_check']
        sheet = state.get('player_sheet')
        modifier = pc_sheet.skill_bonus(sheet, skill) if sheet else None
        supplied = kit_cards.supplied_roll(action, modifier, skill)
        require(sheet is not None or supplied, f'Load a character sheet or state the {skill} roll '
                'from Avrae (e.g. "History 19"). No turn was committed.')
        if supplied:
            die = supplied[0]
            modifier = supplied[1] if supplied[1] is not None else (modifier or 0)
        else:
            require('roll_seed' in state, 'This session predates stable checks; start a fresh database.')
            material = f"{state['roll_seed']}:{revision}:{claim_id}:{action.casefold()}".encode()
            die = int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1
        dc = kit_claims.claim_dc(claim, state.get('actors', {}),
                                  kit_claims.current_floor_level(self.source, state.get('area')))
        total = die + modifier
        name = skill.replace('_', ' ').title()
        evidence = f'Player rolled {name} for {claim_id}: d20 {die} + {modifier} = {total} vs DC {dc}.'
        if total >= dc:
            text = claim.get('learned_text') or claim['truth']
            return Resolution('knowledge', text,
                              [{'type': 'claim_learned', 'claim': claim_id, 'evidence': evidence},
                               {'type': 'beat', 'tags': ['knowledge'], 'evidence': evidence}])
        return Resolution('knowledge', 'Nothing you know places it.',
                          [{'type': 'beat', 'tags': ['knowledge'], 'evidence': evidence}])

    def _card_dcs(self, config, state):
        """One number per secret: watching the deal uses the same DC as the hidden claim
        the cheat reveals (claim_dc), so looking is never harder than not looking."""
        fact = config['cheat'].get('reveals_fact')
        for claim in kit_claims.compile_claims(self.source or {}).values():
            if fact and claim.get('fact') == fact:
                level = kit_claims.current_floor_level(self.source, state.get('area'))
                return {'watch': kit_claims.claim_dc(claim, state.get('actors', {}), level)}
        return {}

    def _group_claim(self, state):
        """The unlearned hidden Insight claim about the people here, when exactly one exists."""
        learned = set((state.get('claims') or {}).get('learned') or ())
        present = self._present_actors(state)
        found = []
        for key, claim in kit_claims.compile_claims(self.source or {}).items():
            fact = (self.source.get('facts') or {}).get(claim.get('fact') or '', {})
            if claim.get('exposure') == 'hidden' and claim['pc_check'] == 'insight' and key not in learned and \
                    fact.get('area') == state['area'] and (claim.get('concealer') in present or not present):
                found.append((key, claim))
        return found[0] if len(found) == 1 else None

    def _declared_table(self, state):
        """(id, config, initial state) of the room's offered table game, or None."""
        for key in kit_cards.offered(self.source):
            config = self.source['procedures'][key]
            if config.get('kind') == 'card_game':
                return key, config, kit_cards.initial_state(config)
        return None

    def _card_engine(self, key, config, state):
        skills = {'perception', 'insight', 'sleight_of_hand', 'deception'} | {(config.get('check') or {}).get('skill') or 'insight'}
        sheet = pc_sheet.sheet_now(state)  # seated at cards: hands on the cards
        modifiers = {skill: self.skill_modifier(skill, state) for skill in skills}
        passives = {skill: (pc_sheet.passive(sheet, skill) if getattr(self, skill, None) is None and sheet else
                            (10 + modifiers[skill] if modifiers[skill] is not None else None))
                    for skill in skills}
        return kit_cards.engine_for(key, config, modifiers, state['roll_seed'], passives=passives,
                                    dcs=self._card_dcs(config, state))

    def skill_modifier(self, skill, state):
        """Host override, else the currently loaded sheet; never cache a PC's stats."""
        override = getattr(self, skill, None)
        if override is not None:
            return override
        sheet = state.get('player_sheet')
        return pc_sheet.skill_bonus(sheet, skill) if sheet else None

    def _resolve_card(self, kind, action, revision, state, table, lead='', extra_events=()):
        """One card-table action through the declared procedure (runtime/kit_cards.py,
        runtime/kit_twenty_one.py). Numbers stay in the ledger evidence, never the event."""
        key, config, body = table
        require('roll_seed' in state, 'This session predates stable checks; start a fresh test database.')
        engine = self._card_engine(key, config, state)
        try:
            public, new_state, reveals = engine.resolve(kind, action, revision, body)
        except kit_cards.NeedsRuling as exc:
            raise PendingRuling(str(exc), attempt=exc.attempt) from exc
        public = f'{lead} {public}'.strip()
        require(len(public) <= CARD_EVENT_MAX_CHARS, 'Card result exceeds the event bound')
        numbers = '; '.join(engine.trace)
        events = [{'type': 'procedure_state', 'procedure': key, 'state': new_state,
                   'evidence': f'Player declared: {action[:300]}. {config["name"]}: {kind}.'
                               + (f' Numbers: {numbers}.' if numbers else '')}]
        events += [{'type': 'reveal_fact', 'fact': fact,
                    'evidence': f'Seen during play of {config["name"]}: {public[:200]}'
                                + (f' Numbers: {numbers}.' if numbers else '')}
                   for fact in reveals if fact not in state['known_facts']]
        events += list(extra_events)
        if getattr(engine, 'toll_outcome', None):
            # A toll staked this same action (extra_events) is the one that rode on the round.
            staked = {event['toll']: event['state'] for event in extra_events if event.get('type') == 'toll_state'}
            events += self._toll_settled(key, engine.toll_outcome, new_state, state, staked)
        events.append({'type': 'beat', 'tags': [kind],
                       'evidence': f'Player declared: {action}. Resolution: {public}'
                                   + (f' Numbers: {numbers}.' if numbers else '')})
        return Resolution(kind, public, events)

    # -- the toll: a real exchange (call 6) ------------------------------------------
    def _resolve_toll(self, action, revision, state):
        if not (self.source or {}).get('tolls'):
            return None
        for key, (toll, body) in kit_toll.here(self.source, state).items():
            kind = kit_toll.intent(action, body)
            if not kind:
                continue
            label = actor_speakers(self.source).get(toll['demanded_by'], toll['demanded_by'])
            if kind in ('toll_play_for', 'toll_defer'):
                return self._toll_to_game(kind, key, toll, body, action, revision, state)
            actor = state['actors'][toll['demanded_by']]
            engine = kit_toll.TollTable(
                key, toll, label, lambda skill: self._pc_numbers(skill, state, action),
                kit_claims.npc_passive(actor, toll['haggle']['npc_skill']),
                lambda skill=None: self._die(state, revision, f'toll:{key}', action,
                                             self._pc_numbers(skill, state, action)[0] if skill else None, skill))
            text, new_body = engine.resolve(kind, action, body)
            numbers = '; '.join(engine.trace)
            evidence = f'Player declared: {action[:300]}. Toll {key}: {kind}.' + (f' Numbers: {numbers}.' if numbers else '')
            return Resolution(kind, text, [kit_toll.event(key, new_body, evidence),
                                           {'type': 'beat', 'tags': [kind], 'evidence': evidence}])
        return None

    def _toll_to_game(self, kind, key, toll, body, action, revision, state):
        """Steering a toll back to the game: it rides on the next round only if the running
        (or offered) game can pay it out; otherwise it stays pending and comes back."""
        table = card_procedure(self.source, state) or self._declared_table(state)
        new_body = dict(body, status=body['status'] if body['status'] != 'not_raised' else 'demanded')
        carry = bool(table and kit_cards.can_carry(table[1], 'toll') and
                     table[0] in toll.get('stakeable_in', [table[0]]) and
                     not kit_cards.is_live(table[2]['public']))
        amount = body.get('agreed') or body['asked']
        if carry and table[0] in (state.get('procedures') or {}) and \
                kit_cards.game_of(table[1]) == 'twenty_one' and \
                not kit_twenty_one.can_cover(table[2]['public'], amount):
            carry = False  # the same cap as any bet: the purse they brought, the table's most
            short = True
        else:
            short = False
        if kind == 'toll_play_for' and carry:
            new_body['status'] = 'staked'
            new_body['restore'] = body['status'] if body['status'] in kit_toll.OPEN else 'demanded'
            game = copy.deepcopy(table[2])
            game['public']['toll_stake'] = amount
            event = kit_toll.event(key, new_body, f'Player declared: {action[:300]}. The toll rides on the next round.')
            lead = (f'The toll rides on the next round: win and it is waived, lose and the {amount} '
                    f'{toll["unit"]} is paid from the stake.')
            card_kind = 'card_round' if game['public'].get('mode') else 'card_offer'
            return self._resolve_card(card_kind, action, revision, state, (table[0], table[1], game),
                                      lead=lead, extra_events=[event])
        new_body['status'] = 'deferred'
        why = ('you cannot cover it from what you brought to the table' if short and kind == 'toll_play_for'
               else 'the game cannot carry it' if kind == 'toll_play_for' else 'the talk turned to the game')
        event = kit_toll.event(key, new_body, f'Player declared: {action[:300]}. Toll deferred: {why}; it stays '
                                              'pending and comes back.')
        card_kind = kit_cards.card_intent(action, table[2]) if table and not short else None
        if card_kind:
            return self._resolve_card(card_kind, action, revision, state, table, extra_events=[event])
        text = ('You cannot cover the toll from what you brought to the table; it stays owed.' if short and
                kind == 'toll_play_for' else 'The toll stays on the table, unpaid, while the talk turns to the game.')
        return Resolution('toll_defer', text, [event, {'type': 'beat', 'tags': ['toll_defer'],
                                                       'evidence': event['evidence']}])

    def _toll_unstuck(self, result, state):
        """A staked toll must ride on a round the player can still play. When nothing will
        carry it any more (they left the table or the room, the table will not deal to them,
        or the game dropped the stake because they cannot cover it), it goes back to the
        status it had before it was staked: owed again, never stranded."""
        events = []
        moved = any(event.get('type') == 'move' for event in result.events)
        games = dict(state.get('procedures') or {})
        tolls = {}
        for event in result.events:
            if event.get('type') == 'procedure_state':
                games[event['procedure']] = event['state']
            elif event.get('type') == 'toll_state':
                tolls[event['toll']] = event['state']
        for key, toll in kit_toll.compile_tolls(self.source).items():
            body = tolls.get(key) or ((state.get('tolls') or {}).get(key))
            if not body or body.get('status') != 'staked':
                continue
            riding = False
            for procedure in toll.get('stakeable_in') or list(games):
                public = (games.get(procedure) or {}).get('public') or {}
                player = public.get('player')
                if public.get('toll_stake') and player is not None and not player.get('unwelcome'):
                    riding = True
            if riding and not moved:
                continue
            restored = dict(body, status=body.get('restore') or 'demanded')
            restored.pop('restore', None)
            events.append(kit_toll.event(key, restored, 'The staked toll no longer rides on a round the player '
                                         f'can play; it is {restored["status"]} again.'))
            for procedure in toll.get('stakeable_in') or list(games):
                game = games.get(procedure)
                if game and (game.get('public') or {}).get('toll_stake'):
                    cleared = copy.deepcopy(game)
                    cleared['public']['toll_stake'] = None
                    events.append({'type': 'procedure_state', 'procedure': procedure, 'state': cleared,
                                   'evidence': f'The toll stake on {procedure} is cleared; the toll is owed again.'})
        return events

    def _toll_settled(self, procedure, outcome, new_state, state, staked=None):
        events = []
        if outcome not in ('won', 'lost'):
            return events  # 'unstaked': _toll_unstuck puts it back to owed
        for key, (toll, body) in kit_toll.here(self.source, state).items():
            body = (staked or {}).get(key) or body
            if body['status'] != 'staked' or procedure not in toll.get('stakeable_in', [procedure]):
                continue
            stake = (new_state['public'].get('last_result') or {}).get('stake') or body['asked']
            new_body = dict(body, status='waived' if outcome == 'won' else 'paid',
                            paid=0 if outcome == 'won' else stake, rode_on=procedure)
            new_body.pop('restore', None)
            events.append(kit_toll.event(key, new_body, f'The toll rode on a round of {procedure}: {outcome}.'))
        return events


# Appraisal labels: Kit's own feeling, or one she reads in an NPC (target npc). Common
# emotions in any room, not one room's moods (watchroom playtest: "anger" was refused);
# a near synonym is normalized to its label rather than rejected.
APPRAISAL_LABELS = ('none', 'amusement', 'interest', 'surprise', 'concern', 'pride', 'frustration',
                    'anger', 'fear', 'suspicion', 'contempt', 'disgust', 'sadness', 'joy', 'relief', 'unease')
APPRAISAL_SYNONYMS = {
    'angry': 'anger', 'rage': 'anger', 'fury': 'anger', 'furious': 'anger', 'irritation': 'frustration',
    'irritated': 'frustration', 'annoyance': 'frustration', 'annoyed': 'frustration', 'frustrated': 'frustration',
    'afraid': 'fear', 'scared': 'fear', 'terror': 'fear', 'dread': 'fear', 'alarm': 'fear',
    'suspicious': 'suspicion', 'distrust': 'suspicion', 'mistrust': 'suspicion', 'wariness': 'suspicion',
    'wary': 'suspicion', 'contemptuous': 'contempt', 'scorn': 'contempt', 'disdain': 'contempt',
    'disgusted': 'disgust', 'revulsion': 'disgust', 'sad': 'sadness', 'grief': 'sadness', 'sorrow': 'sadness',
    'happy': 'joy', 'happiness': 'joy', 'delight': 'joy', 'glee': 'joy', 'relieved': 'relief',
    'uneasy': 'unease', 'anxiety': 'unease', 'anxious': 'unease', 'nervous': 'unease', 'nervousness': 'unease',
    'worry': 'concern', 'worried': 'concern', 'curious': 'interest', 'curiosity': 'interest',
    'amused': 'amusement', 'surprised': 'surprise', 'shock': 'surprise', 'astonishment': 'surprise',
    'proud': 'pride', 'neutral': 'none', 'calm': 'none'}


def appraisal_label(label):
    """The appraisal label for a stated emotion: itself, its normalized synonym, or None."""
    word = str(label or '').strip().casefold()
    return word if word in APPRAISAL_LABELS else APPRAISAL_SYNONYMS.get(word)


PLAN_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'goal': {'type': 'string', 'enum': [
            'story_enjoyment', 'roleplay', 'npc_embodiment', 'competent_opposition',
            'fair_challenge', 'reward_creativity', 'campaign_through_line',
            'satisfying_rewards', 'shared_humor', 'player_surprise', 'momentum',
            'craft_pride']},
        'appraisal': {'type': 'object', 'additionalProperties': False,
                      'properties': {'label': {'type': 'string', 'enum': list(APPRAISAL_LABELS)},
                          'intensity': {'type': 'integer', 'enum': [0, 1, 2, 3]},
                          'cause': {'type': 'string'},
                          'goal_effect': {'type': 'string', 'enum': ['advances', 'threatens', 'neutral']},
                          'target': {'type': 'string', 'enum': ['player', 'npc', 'scene', 'kit']}},
                      'required': ['label', 'intensity', 'cause', 'goal_effect', 'target']},
        'memory_refs': {'type': 'array', 'items': {'type': 'string'}},
        'improv_read': IMPROV_READ_SCHEMA,
        # Detail generation (runtime/kit_detail.py), decided before any prose: what the
        # player asked for, 3-5 one-line candidates, and every fact this turn adds that
        # the source does not supply.
        'detail': kit_detail.DETAIL_SCHEMA,
        'move': {'type': 'string', 'enum': [
            'npc_reply', 'kit_comment_then_npc', 'world_description', 'ruling', 'ask_clarification']},
        'public_brief': {'type': 'object', 'additionalProperties': False,
                         'properties': {
                             **{key: {'type': 'string'} for key in
                                ('tactic', 'reply_to', 'kit_focus', 'callback', 'mirror', 'npc_notice')},
                             'scope': {'type': 'string', 'enum': ['call', 'exchange', 'feature']}},
                         'required': ['tactic', 'reply_to', 'scope', 'kit_focus', 'callback', 'mirror',
                                      'npc_notice']},
        # Any actor id present in the scene (agenda_here / claims_here list them), or none.
        'focus_actor': {'type': 'string'},
        'table_presence': {'type': 'string', 'enum': list(kit_voice.TABLE_PRESENCE)},
        'tone': {'type': 'string', 'enum': ['wry', 'warm', 'threatening', 'curious', 'plain', 'quiet']},
        # Private: at most one new evidence-cited observation about this player.
        'player_note': {'type': 'object', 'additionalProperties': False,
                        'properties': {'note': {'type': 'string'},
                                       'evidence_turns': {'type': 'array', 'items': {'type': 'string'}},
                                       'replaces': {'type': 'string'}},
                        'required': ['note', 'evidence_turns', 'replaces']},
        # Brendon's voice spec (runtime/kit_voice.py): player_mood is private; turn_mode
        # and the brief's mirror and npc_notice are its public carriers.
        'player_mood': kit_voice.PLAYER_MOOD_SCHEMA,
        'turn_mode': {'type': 'string', 'enum': list(kit_voice.TURN_MODES)},
        # Claims and knowers (runtime/kit_claims.py): who says which claim, how, and why.
        # Optional on the bridge; empty when nobody states a claim.
        'claims': kit_claims.CLAIMS_SCHEMA,
        # Agendas (runtime/kit_agenda.py): who advanced what they want, or why nothing did.
        # Required when prepare supplied agenda_here.
        'agenda': kit_agenda.AGENDA_SCHEMA,
        # When anything "catches the eye": the concrete observable reason and its roots.
        'salience': kit_agenda.SALIENCE_SCHEMA,
        # A roll called with advantage/disadvantage cites a condition true right now.
        'roll_call': kit_agenda.ROLL_CALL_SCHEMA,
        # What the PC holds, wears, and has running now, when the situation or the
        # player's words change it. The player's declared state wins.
        'pc_state': kit_agenda.PC_STATE_SCHEMA,
        # The PC's state or habit is odd for the situation: who present notices, and how
        # they react from their wants. It stands; the reaction is the scene event.
        'pc_oddity': kit_agenda.PC_ODDITY_SCHEMA,
        # Rare: neither the situation nor the player settles something that changes an outcome.
        # Kit asks; the turn commits nothing mechanical. Never about what the situation sets.
        'ask_player': kit_agenda.ASK_PLAYER_SCHEMA,
        # Kit's private running plan (runtime/kit_plan.py): the whole current plan when it
        # changes; omitted, the stored plan carries unchanged. Never reaches the performer.
        'plan': kit_plan.PLAN_SCHEMA,
        # Hints and hooks Kit plants, pays off, or drops this turn (runtime/kit_threads.py).
        'open_threads': kit_threads.OPEN_THREADS_SCHEMA,
    },
    'required': ['goal', 'appraisal', 'memory_refs', 'improv_read', 'move', 'public_brief',
                 'focus_actor', 'table_presence', 'tone', 'player_note', 'player_mood', 'turn_mode'],
}

# The strict API schema needs every property required.
API_PLAN_SCHEMA = json.loads(json.dumps(PLAN_SCHEMA))
OPTIONAL_PLAN_KEYS = ('claims', 'agenda', 'salience', 'roll_call', 'pc_state', 'pc_oddity', 'ask_player', 'plan',
                      'open_threads', 'observed_event', 'detail')  # the engine fills these when left out (PR3 a, c)
# Strict mode cannot leave an object out, so the chat-only paths (a PC state change, an
# oddity reaction, a question to the player) are not offered to the API model at all.
CHAT_ONLY_PLAN_KEYS = ('pc_state', 'pc_oddity', 'ask_player', 'plan', 'open_threads')
for _key in CHAT_ONLY_PLAN_KEYS:
    API_PLAN_SCHEMA['properties'].pop(_key)
API_PLAN_SCHEMA['required'] = API_PLAN_SCHEMA['required'] + [
    key for key in OPTIONAL_PLAN_KEYS if key not in CHAT_ONLY_PLAN_KEYS]

SPEECH_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'segments': {'type': 'array', 'items': {'type': 'object',
                     'additionalProperties': False,
                     # Narrator, Kit, or an actor's speaker label (public_view.speakers).
                     'properties': {'speaker': {'type': 'string'},
                         'text': {'type': 'string'},
                         # Required on every Kit segment: a verbatim quote of the public
                         # line from this turn her remark answers (kit_voice.check_kit_asides).
                         'reacts_to': {'type': 'string'}},
                     'required': ['speaker', 'text']}},
    },
    'required': ['segments'],
}
# The strict API schema needs every property required; non-Kit segments send "none".
API_SPEECH_SCHEMA = json.loads(json.dumps(SPEECH_SCHEMA))
API_SPEECH_SCHEMA['properties']['segments']['items']['required'] = ['speaker', 'text', 'reacts_to']

ONE_PASS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'decision': PLAN_SCHEMA, 'performance': SPEECH_SCHEMA},
    'required': ['decision', 'performance'],
}

BRIEF_TEXT_FIELDS = ('tactic',)
BRIEF_FIELDS = BRIEF_TEXT_FIELDS + ('reply_to', 'scope', 'kit_focus', 'callback', 'mirror', 'npc_notice')
# Accepted from older hosts and checked like the rest when sent; no longer asked for (PR3 b).
LEGACY_BRIEF_FIELDS = ('objective', 'visible_cue', 'player_opening')
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
# Speakers that are never an NPC. Every other speaker label is an actor from the room source.
NON_NPC_SPEAKERS = kit_guards.NON_NPC_SPEAKERS
is_npc_speaker = kit_guards.is_npc


def actor_speakers(source):
    """Room adapter, built from the room source: actor id -> public speaker label.

    An actor's own ``speaker`` field wins; else a running procedure's ``labels`` (the card
    table names its seats); else the actor's public ``name``. Each NPC has their own label
    and card (approach-range playtest: one shared label made them interchangeable)."""
    source = source or {}
    labels = {}
    for config in (source.get('procedures') or {}).values():
        if isinstance(config, dict):
            labels.update(config.get('labels') or {})
    out = {}
    for key, actor in (source.get('actors') or {}).items():
        out[key] = actor.get('speaker') or labels.get(key) or actor.get('name') or key
    return out


def actor_aliases(source):
    """Public words that name each actor: their speaker label and the palette's subject words."""
    out = {}
    subjects = {}
    for area in (((source or {}).get('texture_palette') or {}).get('areas') or {}).values():
        for subject, words in (area.get('subjects') or {}).items():
            if subject.startswith('actor:'):
                subjects.setdefault(subject[6:], set()).update(w.casefold() for w in words)
    for key, label in actor_speakers(source).items():
        out[key] = {label.casefold(), key.replace('_', ' '), *subjects.get(key, ())}
    return out


def speech_speakers(source):
    """Every speaker label a performance may use in this room."""
    return NON_NPC_SPEAKERS + tuple(actor_speakers(source).values())


def focus_actor_id(plan):
    """The plan's focus actor id, or None. focus_actor is any present actor id; the older
    value 'other' still means the improv_read's actor_ref."""
    focus = plan.get('focus_actor')
    if focus in (None, 'none'):
        return None
    if focus == 'other':
        actor = (plan.get('improv_read') or {}).get('actor_ref')
        return None if actor in (None, 'none') else actor
    return focus


def focus_speakers(plan, speakers=None):
    """Speaker labels that count as the focus actor speaking."""
    actor = focus_speaker(plan, speakers)
    return (actor,) if actor else ()


def focus_speaker(plan, speakers=None):
    """The public speaker label of the plan's focus actor (from actor_speakers), or None."""
    actor = focus_actor_id(plan)
    if actor is None:
        return None
    return (speakers or {}).get(actor, actor)
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
EXCHANGE_MIN_ACTOR_WORDS = 30  # the selected actor's own speech (voiced actors only)
# The actor floor applies only to a focus actor whose actor card says "speech_floor": true
# (6c's dealer, against the Nik failure). Every other actor may be brief: forcing 30 words
# from a terse voice made every card player a speechmaker and a clipped guard a lecturer
# (watchroom playtest). A brief focus must still speak, and the exchange total floor
# (narration included) still applies.
EXCHANGE_MIN_SEGMENTS = 2    # an embodied beat or second reactor, not one speech alone
FEATURE_MIN_WORDS = 80       # scene entry or scene-turning moment
FEATURE_MIN_SEGMENTS = 2
# Speech ceilings (plan update #3, PR3 d). "Roomy" means the ceiling, not unlimited. Advisory:
# over one is noted on the record (over_ceiling), never rejected. They count only what can be
# cut: narration, any second NPC, and Kit's remarks after her first. Never counted, so never shortened: the
# focus actor's move, a due hook's raiser, the chosen detail's fact, and Kit's single reaction.
EXCHANGE_MAX_WORDS = 90
FEATURE_MAX_WORDS = 150


def performance_limits(scope=None):
    """The flat-reply guard, stated up front so a chat host can meet it on the first try.

    Generated from the constants above so the bridge never drifts from check_scope.
    These are floors against flat replies, not length targets.
    """
    limits = {
        'call': f'At most {CALL_MAX_WORDS} words in at most {CALL_MAX_SEGMENTS} segments. Answer and stop.',
        'exchange': (f'The focus actor speaks (at least {EXCHANGE_MIN_ACTOR_WORDS} words only when their '
                     'card sets speech_floor true; otherwise speech_floor false may be brief but must speak); at least '
                     f'{EXCHANGE_MIN_WORDS} words across non-Kit segments; at least '
                     f'{EXCHANGE_MIN_SEGMENTS} segments (e.g. a visible beat plus the actor).'),
        'feature': (f'At least {FEATURE_MIN_WORDS} words across non-Kit segments in at least '
                    f'{FEATURE_MIN_SEGMENTS} segments.'),
        'ceiling': (f'Narration, any second NPC and any Kit remark after the first aim for {EXCHANGE_MAX_WORDS} '
                    f'words at most in an exchange and {FEATURE_MAX_WORDS} in a feature. That is advisory: going '
                    'over is noted, not rejected. A call stays within '
                    f'{CALL_MAX_WORDS} words in all, and that is hard. '
                    'The focus actor\'s move, a due hook, the chosen detail and Kit\'s one reaction are never '
                    'counted, so never cut them. One NPC speaks unless a second changes the outcome; '
                    'one Kit remark unless the player is playful.'),
        'mirror': (f'When the brief mirror says tight: at most {kit_voice.TIGHT_MAX_WORDS["exchange"]} '
                   f'words in an exchange, {kit_voice.TIGHT_MAX_WORDS["feature"]} in a feature (a call '
                   'keeps its own cap). Combat narration: short sentences (average at most '
                   f'{kit_voice.COMBAT_MAX_AVG_SENTENCE_WORDS} words, none over '
                   f'{kit_voice.COMBAT_MAX_SENTENCE_WORDS}). Showtime: 1 to '
                   f'{kit_voice.SHOWTIME_MAX_KIT_SEGMENTS} Kit segments, and they count toward the floors.'),
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
    'on a real choice for the player, and any raise_now speaker raises it. Style floors become '
    'warnings saved with the turn; secrecy, '
    'player agency, NPC table talk, presence, and the chosen move are still checked.')
ABANDON_INSTRUCTION = (
    'This turn keeps failing. Run abandon for this turn_id (nothing is committed), then prepare '
    'the same player action again with a new turn_id and a simpler decision.')

PRIVATE_INSTRUCTIONS = (
    'You are Kit’s private decision stage, using the supplied canonical personality. '
    'Read DM-only information to keep the scene grounded. The event has already been adjudicated; '
    'do not change its result or request world writes (the engine records accepted_public_event as '
    'the observed event; do not copy it). On a social turn that event restates the player’s declared words; appraise '
    'what they actually said or did, not the scene in general. Appraise its relation to one of Kit’s actual '
    'goals, or choose none. Reference only supplied episode IDs. Choose a high-level move and '
    'regulate her table presence. focus_actor is the id of any actor present in the scene who '
    'carries the turn (the ids claims_here and agenda_here use), or none; an NPC move needs one '
    'and improv_read.actor_ref names the same actor. First make an improv_read: choose a story anchor and its established basis '
    'only if the move touches an active scene, level, or campaign pressure; choose a live actor and one established '
    'goal basis, or none. In kit_choice, one line of about 160 characters: the player’s declared bid '
    '(never their thoughts), the pressure or actor aim it meets, and why Kit foregrounds this '
    'reaction or lets it stay quiet. If no larger thread is relevant, do not insert one. '
    'Then in public_brief choose a tactic: what the actor tries now, grounded in the room, '
    'leaving the player a real opening. Use the actor’s private motives to decide what they try, but phrase the '
    'brief as safe direction for a performer who sees only the public scene. If action_kind '
    'is opening, choose world_description and frame the people and pressure before the '
    'player acts; set focus_actor to the person who speaks first, and the performance needs '
    'that actor’s first line. Show Kit’s '
    'taste through the choice of beat. Do not include hidden identities, clues, or motives. '
    'Keep the trace brief and specific. Do not write dialogue. '
    'An NPC’s motives are distinct from Kit’s reaction. The player may surprise you; do not force a route. '
    'The brief must be consistent with the goal you chose: for npc_embodiment or roleplay, the '
    'tactic is something the actor tries in answer to the player, not only a price or a fact. '
    'In reply_to, copy verbatim the exact part of player_action that most deserves an answer '
    '(use none only for the room opening). Choose scope: call for a narrow roll prompt, ruling, '
    'fact, or clarification (only with a ruling or ask_clarification move, or with no focus actor); '
    'exchange for most social moves; feature for the room opening, a newly important NPC, or a '
    'move that turns the scene. In kit_focus '
    'write one short public-safe direction, derived from your goal and kit_choice, naming the '
    'visible consequence of Kit’s taste in this turn: what she foregrounds, which actor tactic '
    'she lets play out, how she frames a ruling, or a deliberate restraint. kit_focus is not '
    'dialogue, not a copy of kit_choice or the appraisal, and never a hidden fact, an outcome, '
    'an NPC commitment, or a player action. The actor’s objective and tactic come from the '
    'actor’s own motives, not from Kit’s taste. '
    'Table read: in player_mood.read, read the player’s mood from their words, their pacing '
    '(table_read counts their recent message lengths), and out-of-character feedback: playful, '
    'curious, tense, frustrated, bored, cautious, gleeful, or neutral. Its cue is a verbatim quote '
    'of player_action, feedback <note id> (or note <note id>), or pacing: <what changed>; neutral '
    'may use none. player_mood is private. In the brief’s mirror, tell the performer how Kit '
    f'matches or answers that mood, as "{kit_voice.MIRROR_FORMAT}". Frustrated or bored: tight, '
    'and give momentum (a consequence, a decision, a scene turn). Tense, '
    'frustrated, or cautious: no playful humor. Playful or gleeful: play back. Choose turn_mode: '
    'meta for table talk to Kit (required for an out-of-character message), banter for social '
    'back-and-forth, description for exploration, mood, and room results (required for the '
    'opening and room actions), combat for a fight. table_presence showtime lets Kit take the '
    'stage with theatrical description or banter (or for a playful player); never with call '
    'scope, in combat, or for a frustrated player. In npc_notice write none, or "<mood|past_act|'
    'gear|stunt>: <what the focus actor notices about the player’s character and why it matters '
    'to them>", from the actor’s own motives, never Kit’s: mood only from the player’s words '
    'this turn (never feedback or pacing), past_act only from an episode in memory_refs, never '
    'in meta mode, and no dialogue. '
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
    'engaging or interesting is rejected. Never script an NPC line in the brief. On a social turn, choose ruling or call only when the player asked a '
    'rules or mechanics question, or ask_clarification only in the rare case that neither the '
    'situation nor their words settle something that changes the outcome; otherwise play it: '
    'the actor answers in an exchange. refused_attempts, when present, are '
    'recent attempts the table could not resolve (nothing happened); Kit may pick them up. '
    'DETAIL: a player asking for a detail (what someone drinks, plays, wears, what is carved, '
    'what a thing costs) is an invitation: the specific answer is the job, never the least you '
    'can say or a small, simple, or safe one. Decide the answer here, before any prose. Put their words in detail.request (or scene_need: <what> '
    'when the scene needs a fact the source leaves open; else none). When detail_oracle is '
    'present, copy its slot; by status: canon_supplied, reuse the canon fact (choice canon); '
    'source_supplied, the source answers (choice source); priced, the price comes only from '
    'detail_oracle.price (status source: the adventure sets it, choice source, record and '
    'state that amount); otherwise name the closest SRD entry exactly in price_quote.srd_entry (magic '
    'items: a pricing spec in magic; a charged item says renews=yes|no, and renewing charges are '
    'Utility or Complex Multi-Ability, never Consumable) and state that amount; a tiered SRD '
    'entry is recorded under the slot plus "/<tier>"; a local name for the thing is '
    'yours, the price is not (choice priced); unpriced, nobody names a number (choice '
    'unpriced); open, pick one dealt card by draw_id and interpret it, or override once with '
    '"override: <reason>" and candidates; open_no_deck or no oracle, choice self, slot "self: '
    '<subject>/<facet>". For self or override write 3-5 one-line candidates (idea, the '
    'established fact it uses, the player choice it creates), mark the most typical one and '
    'choose another. Prefer familiar real-world or published material adapted to the setting '
    'before building from scratch. Only for self or override: owner is "<actor id|room|kit>: <what '
    'they want from it>"; handle is what the player can do with it; because reads "true because '
    '<established facts or known motives>". A dealt card needs only its draw_id and the one fact '
    '(the card carries its handle and basis); leave every other detail field out. With no detail, '
    'leave detail out. Record every fact this turn adds '
    'that the source does not supply as an invention (slot, kind, fact, basis, public, scope, '
    'procedure, change_reason). procedure names a runtime '
    'procedure from supported_procedures only when the thing is offered as playable; any other '
    'game is flavor (procedure none), and nobody states rules or stakes for it. A canon fact '
    'changes only with an in-story change_reason. '
    'CLAIMS. Every detail anyone states is a claim someone in the world holds. Before you say '
    'one, answer three questions. Source: is it the adventure\u2019s, established canon, or your '
    'choice? If yours, grow it from a fact already in the scene, write it once, and it stays '
    'true. Knower: who holds it? claims_here gives each character\u2019s band: knows, close, '
    'anchored (a wrong version grown from the obvious feature, held with certainty), or '
    'unaware. Read the player character from claims_here.pc (their own loaded sheet); never '
    'assume a particular character. The narrator knows only what that character plainly '
    'perceives, what their passive Insight or Perception has earned (pc_band fingerprint: '
    'deniable evidence, never the label), and what their own rolls found; Kit\u2019s asides hint '
    'only as far as the wink tier allows (point: where to look; name_kind: the kind of thing; '
    'never the secret); the wink tier always comes from the PC\u2019s passive Insight. CHECKS: '
    'claims_here dc is the one number for that secret on every path. Any check the source gives '
    'no DC is 10 + floor(dungeon floor level / 3) (the area may give floor_level, else 1); an NPC '
    'who actively hides something brings a flat 10 + their skill instead. NPCs never roll: in any '
    'opposed check they bring flat 10 + skill (passive). When the PC\u2019s relevant passive meets '
    'the number, they simply notice or succeed, no roll; the player rolls only when actively '
    'trying something that is not automatic, and meeting the number succeeds. An NPC lie is '
    'flat 10 + Deception against the PC\u2019s passive Insight; if the player actively reads '
    'whether someone is lying, they roll Insight against that same number, and it answers '
    'only whether that person is being straight, never another secret. Never tell the player '
    'that the source gives no DC; apply the default (a settled DM-discretion rule, never an open '
    'question). Numbers stay in the ledger: public text never shows a DC, a roll total, a modifier, '
    'or die math; a roll request names the skill only, and a result is told as what the character '
    'notices. '
    'Motive: why would this person say it now? Choose truth, lie, boast, '
    'bargain, hedge, or silence from their wants; Charisma decides how well they manage it. '
    'Intelligence changes how far someone reasons and how they go wrong, never how well they '
    'talk. Nobody answers like a helpful assistant. When the player '
    'asks, someone answers, even if it\u2019s a lie or a refusal. Record each stated claim in '
    'claims (claim id or new, speaker, stance, version, why); a lie, boast, or bargain\u2019s why '
    'cites the speaker\u2019s want. Never roll a knowledge check for the player. '
    'AGENDA. Something in the scene wants something, and it moves when it should: a person, a '
    'monster, a faction, the room itself, a clock. agenda_here lists who is present, what they '
    'want from this player character, their moves, the clocks, and must_advance (the pace says '
    'an advance is due). When an advance is due, or the player stalls, looks away, or is busy '
    'elsewhere, advance one: an actor makes a declared move (or a new one rooted in scene facts, '
    'and never on a secret they are unaware of), or a pressure ticks. If the player is dealing '
    'with that agent right now, hold as engaged: that exchange is its advance. When no advance '
    'is due, a quiet turn is valid even with agents present: hold quiet and say in why what '
    'keeps them waiting this turn. Optional activities recede: when activities says '
    'backgrounded, do not remind, prompt, or choose for the player. What stands out goes in '
    'salience (thing as the performance names it, reason: the concrete visible detail); the '
    'performance names each thing. '
    'PLAN: think ahead, not only in reply. kit_plan is your private running plan: a few beats, '
    'each who is building toward what, roughly when, and why from their wants, agenda, or claims. '
    'Let it shape this turn\u2019s choice. When it should change, send plan with the whole current '
    'plan (at most 5 beats; each new, keep, advance, or revise with a reason; drop the rest with a '
    'reason); leave plan out to carry it unchanged. Roots cite actors, claims, facts, or agenda; '
    'nobody builds toward a secret they are unaware of. Never say the plan; play it. '
    'ATTITUDES: dm_only.attitudes_here is how each NPC here regards the player and what last '
    'moved it; play it, never name it or a roll behind it. A story_brief threshold marked '
    'crossing_now steers, it does not force: play toward its then, starting this turn. '
    'STORY: story_brief is what this scene is about, from the room data, every turn here: who '
    'wants what and their traits, what each act or con is for, the primary hooks, thresholds, '
    'and endings. The NPCs pursue it, not just react: an act serves its purpose, and an '
    'undelivered hook reaches the player. A hook in raise_now is overdue: its NPC raises it this '
    'turn, in character, as their own move. Plan beats may cite hooks as hook:<id>. Never say '
    'the brief or any secret in it. '
    'PC STATE: the situation sets the default (claims_here.pc.situation): seated at a table '
    'game, hands on the game and a carried item set aside; talking or exploring, hands free; a '
    'fight or on guard, weapon, guard, or focus in hand. Anything the player says overrides it. When the fiction or '
    'the player changes it, record the whole picture in pc_state. A declared state or habit '
    'that is odd for the situation stands (advantage too, if really met); never quietly undo it. '
    'Reacting to odd habits is a goal: pc_oddity names who present notices and how their wants '
    'make them react (suspicion, a joke, a higher price, refusing to deal), carried in npc_notice. '
    'Kit just plays: never ask what the PC holds or wears, and never hold a roll for it. Only in '
    'the rare case where neither the situation nor the player settles something that would '
    'change an outcome, ask_player: one short plain question (ask_clarification, call scope); '
    'that turn resolves and commits nothing. Advantage '
    'or disadvantage needs a reason true now (held, equipped, active, or a position); owning is '
    'not holding. Record it in roll_call; the performance names the mode and the cause ref. '
    'Calling for a roll, set roll_call (target: who or what, or none); the player\u2019s bare roll '
    'next turn answers it.'
)

PUBLIC_INSTRUCTIONS = (
    'Perform the chosen DM move as Kit. You have only player-visible room facts and a bounded '
    'public resolution; do not invent discoveries, geometry, rules outcomes, NPC commitments, '
    'or combat results. Never assume a hidden fact from prior knowledge. '
    'A card’s wants and tactics are options the actor chooses in answer to the player’s words, '
    'never a default line or a required beat. '
    'If action_kind is opening, frame a scene in motion rather than listing the room inventory; '
    'telegraph the public social and exploration invitations without announcing a hidden truth. '
    'On a social reply, react to the player’s actual words. A character may take a few sentences '
    'to test, tempt, threaten, or tell a short story when it earns the space, but stop at a real '
    'player decision. Let a second NPC react only when that changes the scene. '
    'Follow the selected public brief, tone, and table presence; quiet means '
    'no Kit segment, brief at most one, present at least one, and showtime one to '
    f'{kit_voice.SHOWTIME_MAX_KIT_SEGMENTS} Kit segments where she takes the stage (they count '
    'toward the floors). At every presence the narration carries her taste. The brief conveys '
    'a choice, not authority to invent facts. '
    'The accepted event will be displayed before your segments on physical/check turns (after '
    'them on an exit, so perform the room reacting as the player goes); do not repeat it verbatim. On a social turn it restates the player’s own words: answer '
    'them, do not echo them back. In a social scene, let the NPC pursue a specific objective '
    'through a response, action, or question grounded in the room; a price or fact alone is '
    'rarely the whole exchange. Give the player something meaningful to answer or act on. '
    'Never resolve what the accepted event did not: play the scene around it. '
    'When ask_player is present (rare), Kit asks that question in her own segment, in those words, and '
    'nothing is resolved or narrated as happening. '
    'turn_mode names the moment: meta and banter are table talk and social play; description '
    'sets the mood; combat is tense and fast, in short sentences. The brief’s mirror says how to '
    'answer the player’s energy: honor its energy, length, and humor; tight means at most '
    f'{kit_voice.TIGHT_MAX_WORDS["exchange"]} words in an exchange or '
    f'{kit_voice.TIGHT_MAX_WORDS["feature"]} in a feature, and the scene moves. When npc_notice '
    'is not none, the focus actor reacts to that thing about the player’s character for their '
    'own reasons, and only from what they could see or know. '
    'The brief’s reply_to names the player’s words the turn must answer. kit_focus is Kit’s own '
    'choice of what this turn foregrounds: enact it through framing, which detail or reaction '
    'gets space, how a ruling is phrased, or, only when table presence allows, a Kit remark. It '
    'is not a line for any NPC and grants no authority over facts, rules outcomes, NPC knowledge '
    'or commitments, or the player’s choices. When '
    'callback is not none, it quotes an earlier public moment (callback_source shows where it '
    'came from): let it visibly return in this turn, through an actor who was there reacting from '
    'their own motives, a returning detail, or Kit’s framing, without re-quoting it at length or '
    'adding facts about it. Scope: '
    'call means answer directly and stop; exchange means the actor answers reply_to, pursues the '
    'tactic with a visible beat, and leaves a live opening; feature means a scene in motion with '
    'room for a short speech or more than one reaction. Never pad to reach a length: no extra '
    'speakers or generic banter, no repeated phrases, no retelling what the player said, no stock '
    'filler, no recycled lines. '
    'NPC VOICES: every NPC speaks only from their own card: its voice_contract rhythm, register, '
    'tics, and humor, and its physical touchstone; never_says and never_words are hard limits, and '
    'max_words_per_sentence caps that NPC’s sentences. Each NPC has their own speaker '
    'label (speakers) and card. Enact a voice through rhythm, never a phonetic accent or stereotype. NPCs '
    'pursue their own objectives and never use table talk (dice, checks, rulings, the story as a '
    'story); an NPC running a table procedure who names its stakes and play in its own terms is '
    'not table talk. NPC speech stays separate from Kit’s: no NPC borrows her wit, asides, one-word verdicts, '
    'or phrasing, or voices her taste; tone and kit_focus never change an NPC’s diction. Two NPCs '
    'in one turn never sound alike, and no NPC reuses a pet name, opener, or phrase from their '
    'recent turns. Fixed source numbers such as a price never change. '
    'refused_attempts, when present, lists recent attempts the table could not resolve; they '
    'changed nothing in the world, Kit may refer to them, and NPCs react only to what they '
    'could visibly have seen. raise_now, when present, is overdue story business: that speaker '
    'raises it this turn in their own voice, as their own move, leaving the player an opening. '
    'PLAYER AGENCY: never state what the player does, '
    'decides, agrees to, thinks, or feels; narrate what others do and what the player can perceive, and '
    'leave the player’s response to the player. '
    'Every Kit segment carries reacts_to: a short verbatim quote (a few words) of the public '
    'line it answers this turn, from player_action, the accepted event, or an earlier segment; '
    'other speakers use none. Her remark must fit that line: never claim something did not '
    'happen when it just did. new_details, when present, are the details the decision chose: '
    'let them land in the scene as stated, with their numbers exact, and never shrink them to '
    'a stock answer. claim_lines, when present, are what a speaker says about a claim: say it as '
    'that speaker would, and never correct or explain it. new_procedures, when present, are table games the runtime can run; only '
    'those may be offered as playable with rules or stakes, and while one runs (table_procedures) '
    'only its own rules and stakes are stated. SCENE FIT: call the player only what '
    'your_character says they are; never narrate anything hidden as clean, honest, or fair (say '
    'only what the player can see); a running procedure stakes only what it tracks, never other '
    'items, prices, or favors.'
)

# Kit's direct table voice: Brendon's voice spec (docs/personality/dm-personality-core.md,
# "Brendon's voice spec") as lean performer guidance. Default for KitChatBridge (one-pass
# and staged) at Brendon's direction; the standalone API path still defaults to `current`.
# It only adds performer instructions: the input, schema, and every validator are
# identical to `current`. It carries no example lines, so nothing in it can be reused
# verbatim or handed to an NPC. Tests cap it at 1,800 characters for live latency (Brendon's
# ceiling is about 2,000).
KIT_EXPRESSION_V1 = (
    'KIT’S TABLE VOICE. Kit is one particular DM with a flair for theatre, not a neutral '
    'narrator. Guiding star: nonsense is not entertaining. Her best line is the boldest one '
    'that is coherent and true to what just happened; a quip that contradicts or ignores the '
    'scene is a failure, never flavor. A question for detail is an invitation: answer the '
    'literal question first, then commit to the named, local answer the decision chose, one '
    'the player can act on. Boldness goes into which detail, never length. None of it costs '
    'a source fact, hidden information, a rules outcome, or the player’s choices. Voice by '
    'turn_mode. Meta and banter: quippy, quick, cheeky; answer first, then the joke. '
    'Description: theatrical, mood-setting, specific; overacting is welcome. Combat: engaged, '
    'tense, evocative; short punchy sentences; stakes in what the player can see, hear, and '
    'smell. Do: react to the exact thing this player did; hold an opinion and still rule '
    'fairly; be exact about a ruling; show earned delight; hand the scene back on a real '
    'choice. Don’t: generic praise, a menu of options, or advice; no sentence template or '
    'stock acknowledgement becomes a habit. Her opinion never changes a fact, rules outcome, or '
    'NPC stance, and never hints at hidden information.'
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
    'and table presence. Do not copy improv_read, appraisal, player_mood, table_read, episode, or '
    'player note text into the performance. To save context, the personality core and the public '
    'dialogue history appear once, in the private input (personality_core, dialogue_history); the '
    'performance uses them from there. Keep the decision brief. '
    'The decision connects the player bid, available story pressure, actor goal, and Kit’s '
    'appraisal before selecting a concrete DM move; do not justify dialogue after the fact.'
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
        return self._complete(PRIVATE_INSTRUCTIONS, payload, 'kit_private_decision', API_PLAN_SCHEMA)

    def perform(self, payload, performance_variant='current'):
        speech = self._complete(PERFORMANCE_VARIANTS[check_variant(performance_variant)], payload,
                                'kit_public_performance', API_SPEECH_SCHEMA)
        for segment in (speech or {}).get('segments', []) if isinstance(speech, dict) else []:
            if isinstance(segment, dict) and segment.get('speaker') != 'Kit':
                segment.pop('reacts_to', None)
        return speech


def supported_procedures(source):
    return kit_cards.offered(source)


def check_plan(plan, episodes, public_event, action_kind=None, candidates=None, player_action=None,
               player_notes=(), committed_turn_ids=(), source=None, state=None, established='',
               oracle=None, claims_packet=None, table_talk=False):
    require(isinstance(plan, dict) and set(plan) - set(OPTIONAL_PLAN_KEYS) == set(PLAN_SCHEMA['required']),
            'Incomplete private decision')
    plan.setdefault('detail', copy.deepcopy(kit_detail.NO_DETAIL))  # no detail this turn
    if 'claims' in plan:
        kit_claims.check_claims(plan['claims'], claims_packet, source or {}, state or {})
    if plan.get('salience'):
        kit_agenda.check_salience(plan['salience'], source or {}, state or {})
    if plan.get('pc_state'):
        kit_agenda.check_pc_state(plan['pc_state'])
    if plan.get('roll_call'):
        # A state the player declares this turn counts for this turn's roll.
        kit_agenda.check_roll_call(plan['roll_call'], source or {},
                                   kit_agenda.with_pc_state(state or {}, plan.get('pc_state'),
                                                            fight=plan.get('turn_mode') == 'combat'))
    plan.setdefault('observed_event', public_event)  # the engine's event, unless Kit copied it
    for key in ('observed_event', 'goal'):
        require(isinstance(plan[key], str) and plan[key].strip(), f'Missing {key}')
    require(plan['observed_event'] == public_event, 'Private decision changed the accepted event')
    appraisal = plan['appraisal']
    require(plan['goal'] in PLAN_SCHEMA['properties']['goal']['enum'], 'Unknown Kit goal')
    require(isinstance(appraisal, dict) and set(appraisal) ==
            {'label', 'intensity', 'cause', 'goal_effect', 'target'},
            'Invalid appraisal')
    if isinstance(appraisal, dict) and appraisal_label(appraisal.get('label')):
        appraisal['label'] = appraisal_label(appraisal['label'])
    require(appraisal['label'] in APPRAISAL_LABELS,
            'Invalid appraisal label (use a common emotion: ' + ', '.join(APPRAISAL_LABELS[1:]) + ')')
    require(type(appraisal['intensity']) is int and 0 <= appraisal['intensity'] <= 3,
            'Invalid appraisal intensity')
    require(isinstance(appraisal['cause'], str) and appraisal['cause'].strip()
            and len(appraisal['cause']) <= 500,
            'Appraisal must have a cause')
    bound = CARD_EVENT_MAX_CHARS if str(action_kind or '').startswith(LONG_EVENT_KINDS) else EVENT_MAX_CHARS
    require(len(plan['observed_event']) <= bound, 'Decision exceeds event bound')
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
    settle_story_read(plan['improv_read'], candidates)
    check_improv_read(plan['improv_read'], candidates)
    for field in ('move', 'table_presence', 'tone'):
        require(plan[field] in PLAN_SCHEMA['properties'][field]['enum'], f'Invalid {field}')
    focus = plan['focus_actor']
    require(isinstance(focus, str) and focus.strip(), 'Invalid focus_actor')
    if focus not in ('none', 'other'):
        actors = (state or {}).get('actors')
        if actors is not None:
            actor = actors.get(focus) or {}
            require(actor and actor.get('location') == (state or {}).get('area') and
                    actor.get('status') not in ('fled', 'dead'),
                    f'focus_actor {focus!r} is not an actor present here; use a present actor id or none')
    require(plan['move'] != 'kit_comment_then_npc' or plan['table_presence'] != 'quiet',
            'Chosen move conflicts with quiet table presence')
    stall = stall_check(plan, action_kind)
    require(action_kind != 'opening' or plan['move'] == 'world_description' or
            (stall and plan['move'] == 'ruling'),
            'Room entry needs a world description (or, as a stall, a ruling that only calls a check)')
    if plan['move'] in ('npc_reply', 'kit_comment_then_npc'):
        require(focus_actor_id(plan) is not None, 'NPC move needs a selected actor')
        require(plan['improv_read']['actor_ref'] == focus_actor_id(plan),
                'NPC move disagrees with selected actor')
    brief = plan['public_brief']
    require(isinstance(brief, dict) and set(brief) - set(LEGACY_BRIEF_FIELDS) == set(BRIEF_FIELDS) and
            all(isinstance(brief[key], str) and 0 < len(brief[key].strip()) <= 240
                for key in brief), 'Invalid public performance brief')
    if action_kind == 'opening':
        # Room entry has no player words: reply_to is none by default (watchroom T0 rejected it).
        brief['reply_to'] = 'none'
    check_reply_to(brief['reply_to'], player_action, action_kind)
    scope = brief['scope']
    require(scope in PLAN_SCHEMA['properties']['public_brief']['properties']['scope']['enum'],
            'Invalid brief scope')
    require(action_kind != 'opening' or scope == 'feature' or stall_check(plan, action_kind),
            'Room entry needs feature scope (or call scope with roll_call: a stall check)')
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
    kit_guards.check_ruling_dodge(plan, action_kind, player_action, table_talk)
    for field in brief:
        if field in BRIEF_QUOTE_FIELDS:
            continue
        require(all(_normalized(note['note']) not in _normalized(brief[field])
                    for note in player_notes if len(note['note'].strip()) >= 20),
                f'public_brief {field} copies a private player note; restate its effect as '
                'public direction in kit_focus')
    check_callback(brief['callback'], plan['memory_refs'], episodes)
    check_player_note(plan['player_note'], player_notes, committed_turn_ids)
    kit_voice.check_voice_plan(plan, action_kind, player_action, table_talk or is_ooc(player_action),
                               player_notes, has_history=bool(committed_turn_ids))
    kit_detail.check_detail(plan['detail'], player_action, action_kind, source, state,
                            supported_procedures(source), established=established,
                            owners=[key for key in candidates['actor_bases'] if key != 'none'],
                            oracle=oracle)
    if plan.get('pc_oddity'):
        kit_agenda.check_pc_oddity(plan['pc_oddity'], plan, state or {})
    if plan.get('ask_player'):
        kit_agenda.check_ask_player(plan['ask_player'], plan, state or {})
    if 'plan' in plan:
        kit_plan.check_plan_block(plan['plan'], source or {}, state or {})


def is_ooc(player_action):
    """Out-of-character table talk: an explicit marker, words addressed to Kit, or a
    question about the rules themselves. Quoted speech is in character and never counts."""
    text = QUOTED_SPEECH.sub(' ', (player_action or '').translate(_TYPOGRAPHIC))
    return bool(OOC_MARKER.search(text) or KIT_ADDRESS.search(text) or
                ('?' in text and RULES_NOUNS.search(text)))


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


def settle_story_read(read, candidates):
    """The story anchor and basis are Kit's memory tags, never a secret or a number: a story
    anchor that is not active here falls back to the scene, and a basis the anchor does not
    offer to its first basis (watchroom T0: 'Story basis is not established for this anchor').
    The actor reference is still checked strictly."""
    if not isinstance(read, dict):
        return
    bases = (candidates or {}).get('story_bases') or {}
    if read.get('story_anchor') not in bases:
        read['story_anchor'] = 'scene' if 'scene' in bases else 'none'
    offered = bases.get(read['story_anchor']) or ['none']
    if read.get('story_basis') not in offered:
        read['story_basis'] = offered[0]


def room_story_bases(source, state):
    """Scene story bases worked out from the mounted room: its tease at an approach, and the
    ids of its story areas and hooks."""
    source, state = source or {}, state or {}
    bases = []
    if ((source.get('areas') or {}).get(state.get('area')) or {}).get('tease'):
        bases.append('tease')
    for area, story in kit_brief.compile_story(source).items():
        bases.append(area)
        bases += [hook['id'] for hook in story.get('hooks') or ()]
    return bases


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


def check_scope(segments, plan, guards=None):
    """Flat-reply guard per selected scope. A floor, not a measure of quality."""
    scope = plan['public_brief']['scope']
    # Showtime: Kit's theatrical narration in her own segments is scene material.
    showtime = plan.get('table_presence') == 'showtime'
    performed = [segment for segment in segments if segment['speaker'] != 'Kit' or showtime]
    performed_words = sum(_words(segment['text']) for segment in performed)
    if scope == 'call':
        total = sum(_words(segment['text']) for segment in segments)
        require(len(segments) <= CALL_MAX_SEGMENTS and total <= CALL_MAX_WORDS,
                f'Call scope ran long ({total} words in {len(segments)} segments; limit '
                f'{CALL_MAX_WORDS} words in {CALL_MAX_SEGMENTS}). Answer directly and stop.')
        return
    if scope == 'exchange':
        guards = guards or {}
        # Without the room's speaker labels there is no actor to count; the total floor applies.
        actor = focus_speaker(plan, guards['speakers']) if 'speakers' in guards else None
        if actor and actor in guards.get('brief_speakers', ()):
            require(any(segment['speaker'] == actor for segment in segments),
                    f'Exchange scope: the selected {actor} never spoke. A brief line is enough; '
                    'the exchange floor still applies to the whole turn.')
        elif actor:
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


CEILINGS = {'exchange': 'EXCHANGE_MAX_WORDS', 'feature': 'FEATURE_MAX_WORDS'}


def ceiling_note(segments, plan, guards=None):
    """Advisory, never a rejection (Nagatha's #95 review). Checks that the cuttable words
    stay under the scope's ceiling. Over it, the committed record carries the note, and
    replays and reviews count it. Call scope has its own hard cap."""
    name = CEILINGS.get(plan['public_brief']['scope'])
    if not name:
        return None
    try:
        check_ceiling(segments, plan, guards or {}, globals()[name])
    except InvalidChange as exc:
        return str(exc)
    return None


def check_ceiling(segments, plan, guards, ceiling):
    """What can be cut stays under the scope's ceiling (raises; ceiling_note makes it a note).
    The protected parts are never counted: the focus actor, a due hook's raiser, the chosen
    detail's fact, and Kit's first segment (her one reaction). Every Kit segment after the
    first counts, in showtime or not."""
    focus = focus_speaker(plan, guards['speakers']) if 'speakers' in guards else None
    protected = {focus} | set(guards.get('raisers') or ())
    facts = [_normalized(item['fact']) for item in kit_detail.public_inventions(plan.get('detail') or {})]
    kit_seen = 0
    words = 0
    for segment in segments:
        if segment['speaker'] == 'Kit':
            kit_seen += 1
            if kit_seen == 1:
                continue
        elif segment['speaker'] in protected:
            continue
        count = _words(segment['text'])
        text = _normalized(segment['text'])
        count -= sum(_words(fact) for fact in facts if fact and fact in text)
        words += max(count, 0)
    require(words <= ceiling,
            f'Over the ceiling: {words} words of narration and side voices (ceiling {ceiling}). Cut '
            'the narration or the second voice; keep the focus actor\'s move, any due hook, the chosen '
            'detail and Kit\'s one reaction whole.')


def check_public_content(text, public_view, player_action, leak_sets=(), phrases=None):
    """Literal leaks: the room source's DM-only phrases (leak_phrases), allowed once the
    phrase is in the public view, and a name the player said first is theirs to use.
    Paraphrases: DM-only keyword sets from the room source (kit_guards section 6)."""
    public = json.dumps(public_view, ensure_ascii=False).lower()
    declared = player_action.lower()
    text = text.lower()
    phrases = phrases or {}
    for phrase in phrases.get('phrases', ()):
        phrase = phrase.lower()
        player_named = phrase in phrases.get('player_may_name', ()) and (
            phrase in declared or phrase in phrases.get('player_said', ()))
        if phrase in text and phrase not in public and not player_named:
            raise InvalidChange('Public performance mentioned a private fact')
    kit_guards.check_paraphrased_leaks(text, public_view, player_action, leak_sets)


def check_brief_public(brief, public_view, player_action, leak_sets=(), phrases=None):
    """Leak check on Kit's direction. reply_to and callback are excluded because
    they are checked verbatim quotes of words the player already said or saw."""
    direction = {key: value for key, value in brief.items() if key not in BRIEF_QUOTE_FIELDS}
    check_public_content(json.dumps(direction, ensure_ascii=False), public_view, player_action,
                         phrases=phrases)
    # Paraphrase sets are checked per field so one field's words cannot pair with another's.
    for value in direction.values():
        kit_guards.check_paraphrased_leaks(value, public_view, player_action, leak_sets)


def all_problems(problems):
    """One message for every failed check: the first as is when it is the only one, else a
    numbered list, so a retry can fix all of them at once."""
    unique = list(dict.fromkeys(problems))
    if len(unique) == 1:
        return unique[0]
    return f'{len(unique)} problems; fix all of them: ' + ' '.join(f'({n}) {p}' for n, p in enumerate(unique, 1))


def check_speech(speech, plan, public_view, player_action, action_kind=None, guards=None,
                 degraded=False, public_event=None):
    """Validate one performance. Returns the spoken text, or (spoken, soft_warnings)
    when degraded is True. Hard checks always raise; soft checks raise unless degraded."""
    guards = guards or {}
    require(isinstance(speech, dict) and set(speech) == {'segments'}, 'Invalid public performance')
    segments = speech['segments']
    require(isinstance(segments, list) and 1 <= len(segments) <= 7,
            'Expected 1–7 spoken segments')
    for segment in segments:
        require(isinstance(segment, dict) and set(segment) in ({'speaker', 'text'},
                                                              {'speaker', 'text', 'reacts_to'}) and
                isinstance(segment['speaker'], str) and segment['speaker'].strip() and
                ('labels' not in guards or segment['speaker'] in guards['labels']) and
                isinstance(segment['text'], str) and 0 < len(segment['text'].strip()) <= 900,
                'Invalid spoken segment')
    kit_count = sum(segment['speaker'] == 'Kit' for segment in segments)
    require(plan['table_presence'] != 'quiet' or kit_count == 0, 'Quiet Kit spoke directly')
    require(plan['table_presence'] != 'brief' or kit_count <= 1, 'Brief Kit took over the scene')
    require(plan['table_presence'] != 'present' or kit_count >= 1, 'Present Kit did not speak')
    if plan['public_brief']['scope'] == 'call':  # a short beat: Kit's reaction is the turn
        kit_guards.check_not_canned(segments)
    speakers = guards.get('speakers')
    focus = focus_speaker(plan, speakers)
    kit_voice.check_voice_presence(segments, plan, focus_speakers(plan, speakers))
    require(plan['move'] != 'kit_comment_then_npc' or
            (kit_count >= 1 and any(is_npc_speaker(segment['speaker']) for segment in segments)),
            'Chosen Kit and NPC move was not performed')
    require(plan['move'] != 'npc_reply' or
            any(is_npc_speaker(segment['speaker']) for segment in segments),
            'Chosen NPC reply was not performed')
    require(plan['move'] != 'world_description' or
            any(segment['speaker'] == 'Narrator' for segment in segments),
            'Chosen world description was not performed')
    require(focus is None or speakers is None or plan['move'] not in ('npc_reply', 'kit_comment_then_npc') or
            any(segment['speaker'] == focus for segment in segments),
            f'Selected focus actor ({focus}) did not speak')
    require(action_kind != 'opening' or
            (any(segment['speaker'] == 'Narrator' for segment in segments) and
             (focus is None or speakers is None or any(segment['speaker'] == focus for segment in segments))),
            'Room entry needs narration and the focus actor\'s first line')
    spoken = '\n'.join(f"{segment['speaker']}: {segment['text'].strip()}" for segment in segments)
    # Every check runs and every failure is reported at once (6c baseline item 5: one error
    # per retry cost the model a retry per problem).
    hard_problems = []

    def hard(check, *args, **kwargs):
        try:
            check(*args, **kwargs)
        except InvalidChange as exc:
            hard_problems.append(str(exc))
    # HARD: secrets (literal and paraphrased), the player's agency, NPC table talk, and
    # a clarification that really asks something.
    hard(check_public_content, spoken, public_view, player_action, phrases=guards.get('leak_phrases'))
    for segment in segments:
        hard(kit_guards.check_paraphrased_leaks, segment['text'], public_view, player_action,
             guards.get('leak_sets', ()), labels=guards.get('labels', ()))
    hard(kit_guards.check_player_agency, segments)
    hard(kit_guards.check_npc_meta, segments)
    if guards.get('table_talk'):
        hard(require, not any(is_npc_speaker(segment['speaker']) for segment in segments),
             'Table talk is the player talking to Kit; no NPC hears or answers it')
    running = declared_procedures(guards.get('declared_procedures', ()), plan)
    configs = guards.get('procedure_configs') or {}
    game_terms = kit_cards.rule_terms([configs.get(key, {}) for key in running]) if running else ()
    hard(check_claimed_numbers, segments, plan, guards, player_action, game_terms)
    # HARD: numbers stay in the ledger; no bonus reminders unless asked (call 4).
    hard(kit_guards.check_public_numbers, segments, rules_question=bool(is_ooc(player_action or '') or
                                                                        RULES_NOUNS.search(player_action or '')))
    # HARD: the toll is an NPC's demand and a real exchange (call 6); no refreshment here (call 3).
    hard(kit_guards.check_toll_exchange, segments, guards.get('toll_amount'), guards.get('toll_raised', True))
    if guards.get('no_refreshment'):
        hard(kit_guards.check_no_refreshment, segments)
    hard(kit_guards.check_clarification_shape, segments, plan)
    # HARD: scene fit. Who the player is, what the deal really was, what can be staked.
    hard(kit_guards.check_player_identity, segments, (public_view or {}).get('your_character'))
    hard(kit_guards.check_clean_deal, segments, guards.get('dealer_cheated', False))
    hard(kit_guards.check_stake_offers, segments, carriable=guards.get('carriable_stakes', ()))
    # HARD: card names, held cards, and mark counts match the running table (item 8).
    hard(check_table_narration, segments, public_view, guards.get('procedure_configs') or {})
    # HARD: Kit reacts to what actually happened this turn; no procedure the runtime
    # cannot carry is stated as settled.
    hard(kit_voice.check_kit_asides, segments, player_action, public_event, action_kind)
    hard(kit_detail.check_detail_performance, segments, running, game_terms)
    # SOFT: style floors. Recorded as warnings, not rejections, in degraded mode.
    history = guards.get('public_history', ())
    soft = (lambda: check_scope(segments, plan, guards),
            lambda: kit_guards.check_padding(segments, player_action, action_kind, history,
                                             json.dumps((public_view or {}).get('table_procedures') or {},
                                                        ensure_ascii=False),
                                             kit_cards.card_words() if running else ()),
            lambda: kit_guards.check_npc_voices(segments, guards.get('voice_contracts'), history),
            lambda: kit_guards.check_npc_repetition(segments, history),
            lambda: kit_guards.check_kit_tics(segments, history),
            lambda: check_callback_used(segments, plan),
            lambda: kit_voice.check_voice_style(segments, plan),
            lambda: kit_detail.check_detail_answer(segments, plan.get('detail'), player_action))
    warnings = []
    for check in soft:
        try:
            check()
        except InvalidChange as exc:
            warnings.append(str(exc))
    problems = hard_problems + ([] if degraded else warnings)
    if problems:
        raise InvalidChange(all_problems(problems))
    return (spoken, warnings) if degraded else spoken


def check_claimed_numbers(segments, plan, guards, player_action, game_terms=()):
    """HARD: numeric exceptions apply only to their speaker, fact, and currency."""
    planned = kit_claims.planned_amounts(plan.get('claims'), guards.get('speakers') or {})
    for segment in segments:
        facts = {}
        for name, fact in (guards.get('numeric_facts') or {}).items():
            units = {kit_guards.COIN_UNITS.get(unit, unit) for unit in fact['unit_words']}
            extra = {amount for claim_id, amounts in planned.get(segment['speaker'], {}).items()
                     if (guards.get('numeric_claims') or {}).get(claim_id, claim_id) == name
                     for amount, unit in amounts if unit in units}
            facts[name] = {**fact, 'allowed_amounts': list(fact['allowed_amounts']) + sorted(extra)}
        kit_guards.check_numeric_facts([segment], facts, player_action,
                                       guards.get('stake_amounts', ()), game_terms)


def declared_procedures(in_state, plan):
    """Procedures already running plus any this decision declares."""
    this_turn = [item['procedure'] for item in ((plan or {}).get('detail') or kit_detail.NO_DETAIL)['inventions']
                 if item['kind'] == 'procedure' and not kit_detail.is_none(item['procedure'])]
    return tuple(in_state) + tuple(this_turn)


def threshold_exit(events):
    """The exit a threshold look this turn was through (its beat's tags), or None."""
    for event in events or ():
        tags = event.get('tags') or ()
        if event.get('type') == 'beat' and 'threshold' in tags:
            rest = [tag for tag in tags if tag not in ('threshold', 'check_request')]
            return rest[0] if rest else None
    return None


def turn_events(runtime, body, plan, turn_id, record=None):
    """The adjudicated events plus what the decision establishes: its canon entries, the
    oracle deal it consumed, and the starting state of a table procedure it declares."""
    if plan.get('ask_player'):
        # A question to the player: the action is not resolved and nothing mechanical
        # commits; one rhythm beat keeps the pacing record honest.
        return [{'type': 'beat', 'tags': ['asked'],
                 'evidence': f"{ASKED_EVENT_PREFIX}{plan['ask_player']['question']}"}]
    events = list(body['events'])
    table_talk = bool(body.get('table_talk'))  # no NPC spoke and no scene time passed
    if record and not table_talk and runtime.source().get('tolls') and not any(e.get('type') == 'toll_state' for e in events):
        # An NPC line that names the toll and its amount puts the demand on the table.
        events += kit_toll.raised_events(runtime.source(), runtime.load()[1], record.get('spoken'), turn_id)
    if 'plan' in plan:
        events.append(kit_plan.plan_event(plan['plan'], turn_id))
    if runtime.source().get('story') and not table_talk:
        revision, _ = runtime.load()
        after = runtime.preview_state(revision, events)
        beat = kit_brief.beat_event(runtime.source(), after, (record or {}).get('spoken'), turn_id)
        if beat:
            events.append(beat)
        events += kit_brief.heard_events(runtime.source(), after, (record or {}).get('spoken'), turn_id)
        # A threshold whose trigger now holds crosses (once per scene) and moves attitudes.
        events += kit_brief.threshold_events(runtime.source(), after, turn_id)
    if plan.get('pc_state'):
        events.append(kit_agenda.pc_state_event(plan['pc_state'], turn_id))
    if plan.get('open_threads'):
        events.append(kit_threads.event(plan['open_threads'], turn_id, runtime.load()[1].get('area')))
    pending = kit_agenda.pending_check_event(plan.get('roll_call'), turn_id) if plan.get('roll_call') else None
    looked = threshold_exit(body['events'])
    if pending and pending.get('check') and looked:
        # A check called on a look through a threshold keeps that view for the roll (watchroom T2).
        pending = {**pending, 'check': {**pending['check'], 'threshold': looked}}
    if pending and pending.get('check') and stall_check(plan, body.get('kind')):
        # The room the description is of: where the PC stands once this turn lands.
        area = runtime.preview_state(runtime.load()[0], body.get('events') or [])['area']
        pending = {**pending, 'check': {**pending['check'], 'held': {'kind': body['kind'], 'area': area}}}
    if body.get('held_description') and not pending and \
            not any(e.get('type') == 'pending_check' for e in list(body.get('events') or []) + events):
        # Delivered: the held obligation is discharged with this turn.
        events.append({'type': 'pending_check', 'check': None,
                       'evidence': f"The held {body['held_description']['kind']} description is delivered."})
    if pending and not any(event.get('type') == 'pending_check' for event in events):  # a held exit wins
        events.append(pending)
    if plan.get('claims'):
        events += kit_claims.said_events(plan['claims'], turn_id, body.get('claims_here'),
                                         runtime.load()[1])
    if body.get('agenda_here') is not None:
        reactors = kit_agenda.oddity_reactors(plan.get('pc_oddity'), runtime.source())
        ticks = kit_agenda.check_agenda(plan.get('agenda'), body['agenda_here'], runtime.source(),
                                        after_event(runtime, body), reactors)
        events.append(kit_agenda.agenda_event(plan['agenda'], body['agenda_here'], turn_id, ticks, reactors))
    detail = plan.get('detail')
    if not detail:
        return events
    events += kit_detail.canon_events(detail, turn_id, body.get('detail_oracle'))
    _, state = runtime.load()
    source = runtime.source()
    running = set(state.get('procedures') or {}) | {event['procedure'] for event in body['events']
                                                    if event.get('type') == 'procedure_state'}
    putoff = put_off_reason(plan)
    for procedure in declared_procedures((), plan):
        config = source.get('procedures', {}).get(procedure)
        if config and procedure not in running and config.get('kind') == 'card_game':
            kit_cards.check_config(config)
            events.append({'type': 'procedure_state', 'procedure': procedure,
                           'state': kit_cards.initial_state(config),
                           'evidence': f'Declared as a table procedure with turn {turn_id}.'
                                       + (f' NPC put-off move: {putoff}' if putoff and
                                          not ASKS_ABOUT_GAME.search(body['action']) else '')})
            running.add(procedure)
    return events


# The player's words are about the game (asking to play, or about it): only then may a
# decision start a table procedure (call 1: a game in the room is never a reason by itself).
ASKS_ABOUT_GAME = re.compile(r"\b(game|games|play|playing|cards?|deal|dealing|bet|bets|wager|ante|stakes?|gambl\w*|"
                             r"join|rules|blackjack|twenty[- ]one|poker|hand|round|buy[- ]in|dealt)\b", re.I)
PUT_OFF = re.compile(r"\b(steer\w*|stall\w*|put (?:\w+ )?off|putting (?:\w+ )?off|distract\w*|divert\w*|"
                     r"keep (?:\w+ ){0,2}(?:busy|seated|at the table|from)|draw (?:\w+ )?in)\b", re.I)


def put_off_reason(plan):
    """The recorded reason when an NPC agenda move uses the game to steer or stall the PCs."""
    for item in ((plan or {}).get('agenda') or {}).get('advances') or ():
        why = f"{item.get('does', '')} {item.get('why', '')}"
        if PUT_OFF.search(why):
            return f"{item.get('agent')}: {item.get('why') or item.get('does')}"
    return None


def check_procedure_start(plan, body, state):
    """HARD (TC-1b): a decision starts a table procedure only when the player's words are
    about the game, or an NPC agenda move records a reason of steering or stalling them."""
    running = set((state or {}).get('procedures') or {}) | {event['procedure'] for event in body['events']
                                                            if event.get('type') == 'procedure_state'}
    new = [p for p in declared_procedures((), plan) if p not in running]
    if new and not ASKS_ABOUT_GAME.search(body['action'] or ''):
        require(put_off_reason(plan), 'A card game in the room is not a reason to start one: start a table '
                'procedure only when the player asks to play or about the game, or record an NPC agenda '
                'move whose why is steering or stalling the PCs.')


def _named_actors(action, aliases=None):
    """Actors the action names, by the room source's public aliases (actor_aliases)."""
    text = action.casefold()
    return {actor for actor, names in (aliases or {}).items()
            if any(re.search(rf"\b{re.escape(name)}\b", text) for name in names if name)}


def _episode_words(episode):
    brief = episode.get('brief') or {}
    texts = [episode.get('player_input'), episode.get('player_bid'), episode.get('kit_choice'),
             episode.get('public_event')]
    texts += [value for key, value in brief.items() if key != 'scope' and isinstance(value, str)]
    return keywords(' '.join(text for text in texts if isinstance(text, str)))


def _relevance(episodes, action, aliases=None):
    """Score function for earlier episodes: shared meaningful words with the action
    (weighted most), the actor the action names or the conversation is already with,
    and the active story thread (a level or campaign anchor, not the generic scene)."""
    last = episodes[-1]
    actors = _named_actors(action, aliases)
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


def select_episodes(episodes, action, limit=MEMORY_LIMIT, recent=MEMORY_RECENT, aliases=None):
    """Always the last `recent` episodes, then earlier ones by relevance, up to `limit`.

    Relevance is transparent (see _relevance). Irrelevant episodes are left out rather
    than padded in. Output stays in chronological order.
    """
    if not episodes:
        return []
    kept = list(range(max(0, len(episodes) - recent), len(episodes)))
    score_of = _relevance(episodes, action, aliases)
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
    aliases = actor_aliases(runtime.source())
    chosen = select_episodes(stored, action, aliases=aliases)
    spoken = {record['turn_id']: record['spoken']
              for record in runtime.kit_turns_by_id([episode['turn_id'] for episode in chosen])}
    episodes = [{**episode, 'spoken': spoken.get(episode['turn_id'], '')[-1200:]}
                for episode in chosen]
    return {'episodes': episodes, 'player_notes': state['kit']['player_notes'],
            'drop_order': trim_order(chosen, stored, action, aliases=aliases)}


def trim_order(chosen, stored, action, recent=MEMORY_RECENT, aliases=None):
    """Episode IDs in the order the budget drops them: earlier episodes least relevant
    first (oldest first on ties), then the recent ones oldest first. The very last
    episode is never listed; fit_to_budget always keeps it."""
    if not chosen:
        return []
    recent_ids = [episode['turn_id'] for episode in stored[-recent:]]
    score_of = _relevance(stored, action, aliases)
    earlier = [(score_of(episode), index, episode['turn_id'])
               for index, episode in enumerate(chosen) if episode['turn_id'] not in recent_ids]
    return [turn_id for _, _, turn_id in sorted(earlier)] + recent_ids[:-1]


# Context budget. The private decision input (personality core, DM context, memory,
# notes, public dialogue) stays within CONTEXT_BUDGET_BYTES (94 KB + the 6 KB voice slot), the same budget
# context() always enforced, now including memory. A one-pass input also carries the
# public half (the static actor cards, ~7 KB, plus the post-event player view when the
# turn changes it, with the core and dialogue history deduplicated out), so the whole
# one-pass input stays within ONE_PASS_BUDGET_BYTES.
# When either would be exceeded, memory is trimmed in this order, least valuable first,
# and the packet says what was trimmed. Player notes are never trimmed (at most 8).
# 118 KB, up from 33 KB (PR #15 fix pass, QA item 9): in the measured worst case (a long
# card game plus 48 max-length canon entries, a card turn that changes the view) the
# public half is ~27.4 KB and the combined floor after every memory trim is ~106.1 KB.
# 118 KB was the private budget plus that public half, with ~2.6 KB to spare; 123 KB adds the story brief.
# +5 KB for the room's story brief in the private half (runtime/kit_brief.py).
# +2 KB for the personality core's growth on main 8f2ad2e (the same ~1.7 KB as the private budget);
# +1 KB for NPC attitudes (dm_only.attitudes_here and the ATTITUDES rule, runtime/kit_attitude.py).
ONE_PASS_BUDGET_BYTES = 126000 + VOICE_MAX_BYTES  # plus the docs/voice slot at its cap
CONTEXT_KEEP_HISTORY = 1          # public dialogue turns always kept
CONTEXT_KEEP_RHYTHM = 3           # recent_rhythm entries always kept
EPISODE_SPOKEN_TRIM_CHARS = 300   # public excerpt per episode after trimming


def _bytes(value):
    return len(encode(value).encode())


def check_room_context(planning_input, source, state):
    """The room's own share of this packet within its caps (kit_rooms.check_context)."""
    kit_rooms.check_context(source, state, dm_only=planning_input['dm_context']['dm_only'],
                            claims=planning_input.get('claims_here'))


def fit_to_budget(planning_input, drop_order, reserve_bytes=0, budget=CONTEXT_BUDGET_BYTES,
                  combined_budget=ONE_PASS_BUDGET_BYTES):
    """Trim the private input in place until it fits `budget` and, with reserve_bytes
    (the one-pass public half), fits `combined_budget`. Returns the kept episode IDs."""
    kit_state = planning_input['kit_state']
    history = planning_input['dialogue_history']
    rhythm = planning_input['dm_context'].get('recent_rhythm', [])
    report = {'episodes_dropped': 0, 'history_dropped': 0, 'rhythm_dropped': 0,
              'excerpts_shortened': False}

    def over():
        size = _bytes(planning_input)
        return size > budget or (reserve_bytes and size + reserve_bytes > combined_budget)

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
    require(not over(), f'Context budget exceeded ({_bytes(planning_input)} private + {reserve_bytes} '
            f'public bytes; budgets {budget} and {combined_budget}) even after trimming memory; '
            'narrow the source adapter')
    return [episode['turn_id'] for episode in kit_state['episodes']]


def established_text(runtime, body):
    """What is already true, for the detail "uses" and "because" checks: the DM context
    (source facts, actors, room rules, accepted state and inventions), the room's public
    performance reference, this turn, and the recent public turns."""
    context = runtime.context()['dm_context']
    reference = runtime.source().get('public_performance', {})
    recent = ' '.join(turn.get('spoken', '') for turn in body.get('public_history', []))
    return ' '.join((encode(context), encode(reference), body['action'], body['public_event'], recent))


def after_event(runtime, body):
    """The people Kit may voice this turn, as an unsaved state: the state once the turn's
    events land, plus, on a move, the people the PC just left. On the turn the PC walks in, the
    room's people react and speak (watchroom playtest: the warden could not challenge Nik
    until a turn later); on the turn they leave, those left behind still react (g17). Only
    for checking the decision; nothing here is committed."""
    revision, before = runtime.load()
    after = runtime.preview_state(revision, body.get('events') or [])
    voiced = [key for key, actor in (before.get('actors') or {}).items()
              if actor.get('location') == before.get('area') and after.get('area') != before.get('area')]
    # Someone heard from the threshold (the tease's heard) can answer through the door.
    voiced += list(kit_brief.heard_here(runtime.source(), after)) + list(kit_brief.heard_here(runtime.source(), before))
    for key in voiced:
        if key in (after.get('actors') or {}):
            after['actors'][key] = {**after['actors'][key], 'location': after['area']}
    return after


def check_decision(runtime, plan, memory, body):
    """Every private decision passes the same checks on every host path. When the
    budget trimmed memory at prepare, only the episodes the model saw can be cited."""
    if body.get('memory_turn_ids') is not None:
        seen = set(body['memory_turn_ids'])
        memory = {**memory, 'episodes': [e for e in memory['episodes'] if e['turn_id'] in seen]}
    source = runtime.source()
    # The people in the scene are the ones there once the event lands: walking in, the PC
    # meets them this turn (watchroom playtest).
    scene = after_event(runtime, body)
    if (body.get('compute') or {}).get('tier') == 'routine':
        kit_router.fill_routine(plan, kit_voice.mode_hint(body['kind'], is_ooc(body.get('action') or ''))
                                or 'description')
    check_plan(plan, memory['episodes'], body['public_event'], body['kind'],
               body['discernment_candidates'], body['action'],
               player_notes=memory['player_notes'],
               committed_turn_ids=runtime.committed_kit_turn_ids(),
               source=source, state=scene,
               established=established_text(runtime, body), oracle=body.get('detail_oracle'),
               claims_packet=body.get('claims_here'), table_talk=bool(body.get('table_talk')))
    check_brief_public(plan['public_brief'], body['public_view'], body['action'],
                       kit_guards.leak_sets(source), kit_guards.leak_phrases(source))
    check_procedure_start(plan, body, runtime.load()[1])
    check_short_beat(plan, body, runtime.load()[1])
    if plan.get('open_threads') is not None:
        kit_threads.check(plan['open_threads'], runtime.load()[1])
    if not plan.get('ask_player'):  # a question to the player moves no agenda
        kit_agenda.check_agenda(plan.get('agenda'), body.get('agenda_here'), source, scene,
                                kit_agenda.oddity_reactors(plan.get('pc_oddity'), source))
    # A public invention reaches the performer and the player: same leak checks as the brief.
    for item in kit_detail.public_inventions(plan['detail']):
        check_brief_public({'invention': item['fact']}, body['public_view'], body['action'],
                           kit_guards.leak_sets(source), kit_guards.leak_phrases(source))


def player_named(runtime, action):
    """The room's player_may_name names the player has said in this session (this turn or
    any committed turn). A name the player said stays theirs to hear back (6c baseline item 5:
    Harria, named by the player, was rejected a turn later)."""
    allowed = kit_guards.leak_phrases(runtime.source()).get('player_may_name', ())
    if not allowed:
        return []
    said = ' '.join([action] + runtime.player_inputs())
    said = said.casefold()
    return sorted(name for name in allowed if re.search(rf'\b{re.escape(name)}\b', said))


def scene_candidates(dm_context, source, state, post_event_state):
    """Discernment candidates for this turn. On a move, the people on both sides of the
    doorway: those the PC leaves still react, and those in the area they walk into react and
    speak this turn (watchroom playtest). Drawn from the room's live actors only."""
    candidates = discernment_candidates(dm_context)
    extra = [b for b in room_story_bases(source, post_event_state) if b not in candidates['story_bases']['scene']]
    if extra:
        candidates = {**candidates, 'story_bases': {**candidates['story_bases'],
                                                    'scene': candidates['story_bases']['scene'] + extra}}
    heard = {**kit_brief.heard_here(source, state), **kit_brief.heard_here(source, post_event_state)}
    for key in heard:  # heard through the door from the threshold: they may answer
        actor = (source.get('actors') or {}).get(key) or {}
        bases = [field for field in ('immediate_goal', 'motive') if actor.get(field)]
        if bases:
            candidates = {**candidates, 'actor_bases': {**candidates['actor_bases'], key: bases}}
    area = post_event_state.get('area')
    if area == state.get('area') or area not in (source.get('areas') or {}):
        return candidates
    arrived = discernment_candidates({**dm_context, 'scene': {**dm_context['scene'], 'current_area': area},
                                      'dm_only': {**dm_context['dm_only'],
                                                  'actors': Runtime.dm_only(source, post_event_state)['actors']}})
    return {**candidates, 'actor_bases': {**candidates['actor_bases'], **arrived['actor_bases']}}


def prepare_inputs(runtime, revision, state, action, resolution, use_memory, one_pass=False,
                   table_talk=False):
    post_event_state = runtime.preview_state(revision, resolution.events)
    public_view = runtime._player_view(runtime.source(), post_event_state)
    context = runtime.context()
    if context['revision'] != revision:
        raise StaleTurn(f'Expected revision {revision}; current is {context["revision"]}')
    memory = kit_memory(runtime, state, action, use_memory)
    public_history = [{'player_input': turn['player_input'], 'spoken': turn['spoken'][-1200:]}
                      for turn in runtime.recent_kit_turns(limit=4)]
    body = {'action': action, 'events': resolution.events, 'kind': resolution.kind,
            'view_before_event': None,
            'public_event': resolution.public_event, 'public_view': public_view,
            'use_memory': use_memory,
            'public_history': public_history,
            'scene_facts': scene_facts(state, resolution.events),
            'player_named': player_named(runtime, action),
            'discernment_candidates': scene_candidates(context['dm_context'], runtime.source(), state,
                                                        post_event_state)}
    if table_talk:
        # Kit answers the player herself; no NPC is the focus, so no actor ids are offered.
        body['discernment_candidates'] = {**body['discernment_candidates'], 'actor_bases': {'none': ['none']}}
    # Only needed to dedupe the one-pass public view; not kept in the staged body.
    body['view_before_event'] = context['dm_context']['player_perceivable'] if one_pass else None
    planning_input = {
        'personality_core': context['personality_core'],
        'dm_context': context['dm_context'],
        'kit_state': {'episodes': memory['episodes'],
                      'player_notes': memory['player_notes'],
                      'current_appraisal': state['kit']['current_appraisal']
                      if use_memory else None},
        'player_action': action, 'accepted_public_event': resolution.public_event,
        'table_read': kit_voice.table_read(action, resolution.kind, table_talk or is_ooc(action), public_history,
                                           memory['player_notes']),
        'action_kind': resolution.kind,
        'dialogue_history': public_history,
        'discernment_candidates': body['discernment_candidates'],
    }
    oracle = detail_oracle(runtime, state, action, resolution.kind)
    if oracle:
        # Private: the slot, canon, texture, and a seeded deal for the detail decision.
        body['detail_oracle'] = oracle
        planning_input['detail_oracle'] = kit_texture.model_view(oracle)
    source = runtime.source()
    if source.get('claims') and not table_talk:
        # Not for table talk: a direct question to Kit is not answered from who knows what.
        # Private: each claim's knowers, the PC's band from the loaded sheet, the wink tier.
        packet = kit_claims.claims_here(source, post_event_state, post_event_state.get('player_sheet'))
        body['claims_here'] = packet
        planning_input['claims_here'] = packet
    if table_talk:
        body['table_talk'] = True  # meta mode at every check; no agenda move or story hook
    agenda = None if table_talk else kit_agenda.agenda_here(source, post_event_state)
    if agenda is not None:
        # Private: who here wants what, their available moves, clocks, and pacing.
        body['agenda_here'] = agenda
        planning_input['agenda_here'] = agenda
    if kit_plan.current(post_event_state):
        # Private: Kit's running plan from earlier turns. Never sent to the performer.
        planning_input['kit_plan'] = {'beats': kit_plan.current(post_event_state)}
    # Private: what this scene is about, from the room data, every turn in the scene (the
    # opening included, so the first line is written with it). Never sent to the performer.
    # Table talk leaves it out: Kit answers the player, not the scene, and a direct question
    # ("Is the dealer cheating me?") must not be answered from the brief's secrets.
    if not table_talk:
        planning_input['story_brief'] = kit_brief.brief(source, post_event_state)
    if resolution.kind == 'check_request':
        # Private: the player asked for a check; the call is Kit's (watchroom T1, Brendon's rule).
        named = re.search(r'\b(' + _SKILL_NAMES + r')\b', action, re.I)
        planning_input['check_request'] = {'rule': CHECK_REQUEST_RULE,
                                           'player_named': named.group(1).casefold().replace(' ', '_') if named else 'none'}
    looked = threshold_exit(resolution.events)
    if looked is None and any(e.get('type') == 'pending_check' and e.get('check') is None for e in resolution.events):
        looked = (state.get('pending_check') or {}).get('threshold')
    if looked and not table_talk:
        # Private: the next area's approach view, tease-only, from the threshold (watchroom T2).
        view = kit_brief.threshold_view(source, post_event_state, looked)
        if view:
            planning_input['threshold_view'] = view
    pending_now = state.get('pending_check') or {}
    held = pending_now.get('held')
    if held and not table_talk and held.get('area', state.get('area')) == post_event_state.get('area'):
        # Private: the description Kit held for this roll, delivered now, scaled to the result.
        # No roll this turn: it is still owed, as the plain view (the obligation persists).
        rolled = any(e.get('type') == 'pending_check' and e.get('check') is None for e in resolution.events)
        body['held_description'] = planning_input['held_description'] = {
            'kind': held['kind'], 'roll': roll_total(action) if rolled else None,
            'rule': HELD_RULE if rolled else HELD_NO_ROLL_RULE,
            'cues': held_cues(source, post_event_state, held.get('area', state.get('area')),
                              pending_now.get('threshold'))}
    threads = kit_threads.view(post_event_state, kit_rooms.stage(source, post_event_state) == 'resolution')
    if threads and not table_talk:
        planning_input['open_threads'] = threads
    due = kit_brief.due_hooks(source, post_event_state)
    if due and not table_talk:
        body['story_due'] = due
        body['story_area'] = post_event_state['area']
    table = card_procedure(source, post_event_state)
    if table and not str(resolution.kind).startswith('card_') and resolution.kind != 'opening':
        planning_input['activities'] = {table[0]: BACKGROUNDED}
    attempts = state.get('refused_attempts', [])[-REFUSED_ATTEMPTS_SHOWN:]
    if attempts:
        # Public: the player saw these pending rulings. Both stages may refer to them.
        body['refused_attempts'] = attempts
        planning_input['refused_attempts'] = attempts
    check_room_context(planning_input, source, post_event_state)
    reserve = _bytes(public_performance_base(runtime, body, one_pass=True)) if one_pass else 0
    kept = fit_to_budget(planning_input, memory['drop_order'], reserve)
    if 'memory_trimmed' in planning_input['kit_state']:
        body['memory_turn_ids'] = kept
    planning_input['kit_state']['episodes'] = episode_views(planning_input['kit_state']['episodes'],
                                                            planning_input['dialogue_history'])
    return revision, body, planning_input


MEMORY_TRIMMED_NOTE = ("Kit's memory was trimmed to fit the context budget this turn "
                       '(input kit_state.memory_trimmed says what went). The session goes on; a long '
                       'session or a heavy room is the cause.')
BACKGROUNDED = ('backgrounded: the player is doing something else. Its state is kept. Do not remind them '
               'of it, prompt a choice in it, or make one for them; it resumes when they act in it again.')


def episode_views(episodes, dialogue_history):
    """The decision's copy of its episodes without text it already reads elsewhere in
    the same packet: `event` (always the copied accepted event, so equal to
    public_event) and a `spoken` excerpt identical to one in dialogue_history, which
    becomes a pointer to it. Checks run on kit_memory, never on this view."""
    shared = {turn.get('spoken'): index for index, turn in enumerate(dialogue_history)
              if turn.get('spoken')}
    views = []
    for episode in episodes:
        view = dict(episode)
        if view.get('event') == view.get('public_event'):
            view.pop('event', None)
        if view.get('spoken') in shared:
            view['spoken'] = f"same as dialogue_history[{shared[view['spoken']]}].spoken"
        views.append(view)
    return views


def scene_facts(state, events):
    """DM-only facts the scene-fit checks need (never shown to the performer): whether
    the dealer cheated the deal now on the table, after this turn's events."""
    procedures = {key: body for key, body in (state.get('procedures') or {}).items()}
    for event in events or ():
        if event.get('type') == 'procedure_state':
            procedures[event['procedure']] = event['state']
    cheated = any(bool((body.get('private') or {}).get('cheated')) and
                  ((body.get('public') or {}).get('gambit') or (body.get('public') or {}).get('round'))
                  for body in procedures.values())
    return {'dealer_cheated': cheated}


def detail_oracle(runtime, state, action, action_kind):
    """The private detail oracle when the player asks for a detail, else None."""
    if action_kind == 'opening' or not kit_detail.asks_for_detail(action):
        return None
    source = runtime.source()
    source_prices = list(kit_guards.numeric_facts(source).items())
    return kit_texture.oracle_packet(action, source, state, action_kind,
                                     price_lookup=lambda text: kit_prices.lookup_hint(text, source_prices))


def prepare_turn(runtime, adjudicator, action, use_memory=True, one_pass=False, table_talk=False):
    require(isinstance(action, str) and 0 < len(action.strip()) <= 1000,
            'Player action must be 1–1000 characters')
    revision, state = runtime.load()
    if table_talk:
        # The host decided this is not a game turn: nothing is adjudicated.
        return prepare_inputs(runtime, revision, state, action, table_talk_resolution(action),
                              use_memory, one_pass, table_talk=True)
    if isinstance(adjudicator, RoomAdjudicator):
        # Every turn, not once: a commit may have mounted another room since the last one.
        adjudicator.mount(runtime.source())
        last = runtime.recent_kit_turns(limit=1)
        addressed = bool(last) and npc_addressed_player(last[-1].get('spoken'))
        said = ' '.join(str(last[-1].get(k) or '') for k in ('public_event', 'spoken')) if last else ''
        resolution = adjudicator.resolve(action, revision, state, addressed=addressed, last_said=said)
    else:
        resolution = adjudicator.resolve(action, revision, state)
    return prepare_inputs(runtime, revision, state, action, resolution, use_memory, one_pass)


def prepare_opening(runtime, one_pass=False):
    revision, state = runtime.load()
    # The entry is the first Kit turn. Host bookkeeping committed before it (the player
    # character, feedback) is its own revision and does not use it up.
    room = state.get('room') or {}
    require(state['area'] not in (room.get('opened') or ()) and (
        runtime.latest_kit_turn_id() is None or kit_rooms.stage(runtime.source(), state) in
        ('approach', 'first_look') and not room.get('turns_in', {}).get(state['area'])),
        'The room entry is available only before the first turn in a room')
    area = runtime.source()['areas'][state['area']]
    arrival = area.get('arrival') or f"The newcomer arrives: {area.get('name') or state['area']}."
    resolution = Resolution('opening', arrival, [
        {'type': 'beat', 'tags': ['scene_entry'],
         'evidence': f"Initial framing of {state['area']} before the player acts."}])
    return prepare_inputs(runtime, revision, state, '[scene entry]', resolution, use_memory=True,
                          one_pass=one_pass)


VIEW_UNCHANGED_NOTE = ('the view after this event is input.private.dm_context.player_perceivable '
                       'with these changes; a path names nested keys joined by "."')
VIEW_DIFF_DEPTH = 3  # view keys, then table_procedures, then one procedure's keys


def view_changes(after, before, depth=VIEW_DIFF_DEPTH, prefix=''):
    """The post-event player view as changes to the pre-event view, keyed by path.

    `set` gives the new whole value at a path; `appended` the items added to the end
    of a list that only grew (a new established detail); `removed` the paths that are
    gone. Dicts are compared `depth` levels deep, so a card turn sends the gambit and
    stacks but not the table's unchanged rules and powers.
    """
    changes = {'set': {}, 'appended': {}, 'removed': []}
    for key, value in after.items():
        path, old = prefix + key, before.get(key, _MISSING)
        if old == value:
            continue
        if depth > 1 and isinstance(value, dict) and isinstance(old, dict):
            inner = view_changes(value, old, depth - 1, path + '.')
            for kind in ('set', 'appended'):
                changes[kind].update(inner.get(kind, {}))
            changes['removed'] += inner.get('removed', [])
        elif (isinstance(value, list) and isinstance(old, list) and old and
              len(value) > len(old) and value[:len(old)] == old):
            changes['appended'][path] = value[len(old):]
        else:
            changes['set'][path] = value
    changes['removed'] += [prefix + key for key in before if key not in after]
    return {kind: found for kind, found in changes.items() if found}


_MISSING = object()


def raise_now_view(due):
    """The performer's view of overdue story hooks: who raises what, in character (hook
    text is public-safe by construction, runtime/kit_brief.py)."""
    return [{'speaker': item['by'], 'raises': item['text'],
             'how': 'their own move this turn, in their voice, with an opening for the player'}
            for item in due]


def public_performance_base(runtime, body, one_pass=False):
    """The performer's public input. In one-pass mode the same model already reads the
    personality core and dialogue history in the private half, so they are sent once."""
    reference = runtime.source().get('public_performance', {})
    kit_guards.check_voice_contracts(reference.get('actor_cards'))
    payload = {
        'player_view_after_event': body['public_view'],  # replaced below when unchanged
        'player_action': body['action'], 'accepted_public_event': body['public_event'],
        'action_kind': body['kind'],
        'performance_reference': reference,
        # The only speaker labels this turn allows: Narrator, Kit, and one per actor here.
        **turn_speakers(runtime, body),
    }
    if body.get('refused_attempts'):
        payload['refused_attempts'] = body['refused_attempts']
    if body.get('story_due'):
        # Public-safe: an overdue story hook its NPC raises this turn (runtime/kit_brief.py).
        payload['raise_now'] = raise_now_view(body['story_due'])
    if one_pass:
        payload['shared_with_private'] = ('personality_core and public dialogue history are in '
                                          'input.private (personality_core, dialogue_history)')
        before = body.get('view_before_event')
        if body['public_view'] == before:
            payload['player_view_after_event'] = ('unchanged by this event: see '
                                                  'input.private.dm_context.player_perceivable')
        elif isinstance(before, dict):
            # Same model, same packet: send only what this event changed, so a card
            # turn does not repeat the table's rules, powers, and canon ledger.
            payload['player_view_after_event'] = {
                'as_changes_to_private_view': VIEW_UNCHANGED_NOTE,
                **view_changes(body['public_view'], before)}
    else:
        payload['personality_core'] = personality_core_text()
        payload['public_history'] = body.get('public_history', [])
    return payload


HEARD_NOTE = ('Inside, not here: heard through the way in. They may call through it (a challenge, a '
              'question) but are not in the scene; describe nothing of them beyond the sound.')


def turn_speakers(runtime, body):
    """{'speakers': [...]} for this turn, plus {'heard': [...]} at an approach: an actor in
    another area of the room is never listed as a speaker here; one heard from this approach
    (the tease's heard) is listed as heard (watchroom T0: the warden, inside, was a landing
    speaker). On a move, the people on both sides of the doorway speak."""
    source = runtime.source()
    revision, before = runtime.load()
    after = runtime.preview_state(revision, body.get('events') or [])
    areas = {before.get('area'), after.get('area')}
    labels = actor_speakers(source)
    where = lambda key: ((after.get('actors') or {}).get(key) or (source.get('actors') or {}).get(key) or {}).get('location')
    heard = {key: sound for key, sound in {**kit_brief.heard_here(source, before),
                                           **kit_brief.heard_here(source, after)}.items()
             if where(key) not in areas}
    here = [label for key, label in labels.items() if key not in heard and where(key) in areas | {None}]
    out = {'speakers': list(dict.fromkeys(NON_NPC_SPEAKERS + tuple(here)))}
    if heard:
        out['heard'] = [{'speaker': labels.get(key, key), 'heard': sound} for key, sound in heard.items()]
        out['heard_note'] = HEARD_NOTE
    return out


def performance_input(runtime, body, plan):
    payload = public_performance_base(runtime, body)
    payload['selected_move'] = {
            'move': plan['move'],
            'focus_actor': focus_speaker(plan, actor_speakers(runtime.source())) or 'none',
            'table_presence': plan['table_presence'], 'tone': plan['tone'],
            'turn_mode': plan.get('turn_mode'),
            'brief': plan['public_brief'],
    }
    if kit_agenda.carriers(plan):
        payload['carriers'] = kit_agenda.carriers(plan)
    if plan.get('ask_player'):
        payload['ask_player'] = {'question': plan['ask_player']['question'],
                                 'note': 'Kit asks this in her own segment and resolves nothing'}
    detail = plan.get('detail') or kit_detail.NO_DETAIL
    shown = kit_detail.public_inventions(detail)
    if shown:
        # Public details this decision establishes; they persist when the turn commits.
        payload['new_details'] = [{'slot': item['slot'], 'fact': item['fact']} for item in shown]
    cues = [{'speaker': 'Kit' if item['speaker'] == 'kit' else
             'Narrator' if item['speaker'] == 'narrator' else
             actor_speakers(runtime.source()).get(item['speaker'], item['speaker']),
             'says': item['version']}
            for item in plan.get('claims') or () if item['stance'] != 'silence']
    if cues:
        # Who says what; never the stance or the truth behind it.
        payload['claim_lines'] = cues
    source = runtime.source()
    for procedure in declared_procedures((), plan):
        config = source.get('procedures', {}).get(procedure)
        if config and config.get('kind') == 'card_game':
            payload.setdefault('new_procedures', {})[procedure] = kit_cards.public_view(
                config, kit_cards.initial_state(config)['public'])
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


# Refused attempts shown to both stages (they are public: the player saw the ruling).
REFUSED_ATTEMPTS_SHOWN = 3

# Kinds whose accepted event is printed after the performance: on an exit the NPCs'
# reaction happens as the player leaves, so it must read before the departure line.
EVENT_AFTER_PERFORMANCE_KINDS = ('exit',)


def check_table_narration(segments, public_view, configs):
    """Every running twenty-one table: the narration's cards and mark counts match its state."""
    problems = []
    text = ' '.join(segment['text'] for segment in segments)
    for key, public in ((public_view or {}).get('table_procedures') or {}).items():
        config = configs.get(key) or {}
        if kit_cards.game_of(config) == 'twenty_one':
            problems += kit_twenty_one.check_narration(text, public, config)
    require(not problems, ' '.join(problems))


def guard_context(source, body):
    """What the style and leak guards need beyond the performance: DM-only paraphrase
    sets and public voice contracts from the room source, and recent public turns."""
    cards = (source or {}).get('public_performance', {}).get('actor_cards', {})
    view = body.get('public_view') or {}
    procedures = view.get('table_procedures') or {}
    configs = {key: config for key, config in ((source or {}).get('procedures') or {}).items()
               if not key.startswith('_') and isinstance(config, dict)}
    # Negotiated toll amounts are backed by toll state, so characters may name them (call 6).
    facts = kit_guards.numeric_facts(source)
    tolls = kit_toll.compile_tolls(source) if (source or {}).get('tolls') else {}
    toll_view = view.get('tolls') or {}
    for key, toll in tolls.items():
        name = toll.get('numeric_fact')
        if name in facts and key in toll_view:
            backed = kit_toll.amounts({key: toll_view[key]})
            facts[name] = {**facts[name], 'allowed_amounts': sorted(set(facts[name]['allowed_amounts']) | backed)}
    here = [toll for key, toll in tolls.items() if toll['area'] == _area_id(source, view)]
    carriable = ('toll', 'tolls', 'passage') if any(kit_cards.can_carry(configs.get(key), 'toll')
                                                    for key in procedures) else ()
    return {'leak_sets': kit_guards.leak_sets(source),
            'leak_phrases': {**kit_guards.leak_phrases(source), 'player_said': list(body.get('player_named') or ())},
            'numeric_facts': facts,
            'procedure_configs': configs, 'carriable_stakes': carriable,
            'toll_amount': here[0]['amount'] if here else None,
            'toll_raised': not here or any(key in toll_view for key in tolls),
            'no_refreshment': bool(((source or {}).get('areas') or {}).get(_area_id(source, view) or '', {})
                                   .get('no_refreshment')),
            'numeric_claims': {key: claim.get('numeric_fact', key)
                               for key, claim in kit_claims.compile_claims(source).items()},
            'stake_amounts': sorted(stake_amounts(procedures)),
            'dealer_cheated': bool((body.get('scene_facts') or {}).get('dealer_cheated')),
            'declared_procedures': tuple(procedures),
            'voice_contracts': {name: card.get('voice_contract') or {} for name, card in cards.items()},
            'speakers': actor_speakers(source), 'labels': speech_speakers(source),
            # The actor word floor is room data: only a card with speech_floor true asks for it
            # (6c's dealer). Every other voice may be terse (watchroom: a guard of short questions).
            'brief_speakers': tuple(name for name in dict.fromkeys(list(actor_speakers(source).values()) + list(cards))
                                    if (cards.get(name) or {}).get('speech_floor') is not True),
            'public_history': body.get('public_history', []),
            'raisers': tuple(item['by'] for item in body.get('story_due') or ()),
            'table_talk': bool(body.get('table_talk'))}


def _area_id(source, view):
    """The area id behind the public view's area name."""
    name = (view or {}).get('area')
    return next((key for key, area in ((source or {}).get('areas') or {}).items() if area.get('name') == name), None)


def stake_amounts(procedures):
    """Every coin amount a running table procedure makes public: stacks, the player's
    purse, the gambit's stakes and ante, and the last payout. Characters may name these
    in sentences about the game (kit_guards.check_numeric_facts), never as a price.
    Card strengths in public card names ("red 8") are strings, so they never count."""
    found = set()

    def walk(value):
        if type(value) is int and 0 < value < 10000:
            found.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    for body in procedures.values():
        walk({key: body.get(key) for key in ('stacks', 'player', 'gambit', 'round', 'carried', 'last_result',
                                             'default_stake', 'max_stake', 'toll_stake', 'pending_bet')})
    return found


def _entering(source, body):
    """The move this turn goes from outside the room into it: the performance happens in the
    new area, so the engine's line comes first (watchroom T6)."""
    move = next((e for e in body.get('events') or () if e.get('type') == 'move'), None)
    if not move or not source:
        return False
    edge = (source.get('exits') or {}).get(move.get('exit')) or {}
    inside = set(kit_rooms.room_areas(source))
    ends = edge.get('areas') or ()
    return any(a in inside for a in ends) and any(a not in inside for a in ends) and \
        _area_id(source, body.get('public_view')) in inside


def checked_record(body, plan, speech, performance_variant, source=None, degraded=False):
    """Validate a performance. Every variant faces the same checks; the record names
    which performer instructions ran so play reviews can tell the variants apart. A
    degraded record says so and keeps the soft warnings it was accepted with."""
    check_variant(performance_variant)
    ask = plan.get('ask_player')
    # An ask_player turn resolves nothing: its public event is the question, not the result.
    public_event = f"{ASKED_EVENT_PREFIX}{ask['question']}" if ask else body['public_event']
    result = check_speech(speech, plan, body['public_view'], body['action'], body['kind'],
                          guards=guard_context(source, body), degraded=degraded,
                          public_event=public_event)
    spoken, warnings = result if degraded else (result, [])
    kit_agenda.check_carriers_spoken(spoken, plan)
    check_held_delivered(body.get('held_description'), spoken)
    if body.get('story_due') and not ask:
        # An undelivered primary hook is overdue: its NPC raises it now (runtime/kit_brief.py).
        kit_brief.check_raised(body['story_due'], source, {'area': body['story_area']}, spoken)
    if ask:
        kit_agenda.check_ask_spoken(speech['segments'], ask)
    elif body['kind'] in EVENT_AFTER_PERFORMANCE_KINDS and not _entering(source, body):
        # The room reacts while the player is still there; then they are gone. The departure
        # line never follows Kit's closing remark (watchroom T6): it goes before her handoff.
        lines = spoken.split('\n')
        handoff = 0
        while handoff < len(lines) and lines[len(lines) - 1 - handoff].startswith('Kit: '):
            handoff += 1
        lines.insert(len(lines) - handoff, f"Narrator: {body['public_event']}")
        spoken = '\n'.join(lines)
    elif body['kind'] not in ('social', 'opening'):
        spoken = f"Narrator: {body['public_event']}\n{spoken}"
    record = {'player_input': body['action'], 'public_event': public_event,
              'trace': plan, 'spoken': spoken, 'performance_variant': performance_variant}
    asides = [{'text': segment['text'], 'reacts_to': segment['reacts_to']}
              for segment in speech['segments'] if segment['speaker'] == 'Kit']
    if asides:
        record['kit_reacts_to'] = asides
    if warnings:
        record.update(degraded=True, soft_warnings=warnings)
    note = ceiling_note(speech['segments'], plan, guard_context(source, body))
    if note:
        record['over_ceiling'] = note  # advisory: the turn commits; reviews count it
    return record


class KitAgent:
    def __init__(self, runtime, model, adjudicator=None, performance_variant='current'):
        self.runtime = runtime
        self.model = model
        self.adjudicator = adjudicator or RoomAdjudicator()
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
            # Checks use the full memory, as the bridge does; the packet's episodes are a
            # slimmed view (episode_views).
            check_decision(self.runtime, plan, kit_memory(self.runtime, self.runtime.load()[1],
                                                          body['action'], body['use_memory']), body)
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
            next_revision = self.runtime.commit_kit_turn(
                turn_id, revision, turn_events(self.runtime, body, plan, turn_id, record), record)
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


ASKED_NEXT_STEP = ('Kit asked the player a question; the action was not resolved and nothing '
                   'mechanical was committed. Show the question. When the player answers, prepare '
                   'their original action again with the answer added, e.g. "<action> (<answer>)".')

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


# The PC speaking out loud: a quoted line, or says/asks/calls/shouts.
ADDRESSING = re.compile(r'["\u201c\u201d]|\b(?:say|says|said|ask|asks|asked|call|calls|called|shout|shouts|'
                        r'whisper|whispers|tell|tells)\b', re.I)


def important_speakers(source):
    """Speakers whose turns are never routine: a card that sets speech_floor, or anyone who
    raises a story hook (room data)."""
    cards = (source.get('public_performance') or {}).get('actor_cards') or {}
    names = {name for name, card in cards.items() if (card or {}).get('speech_floor') is True}
    labels = actor_speakers(source)
    for story in kit_brief.compile_story(source).values():
        names |= {labels.get(hook['by'], hook['by']) for hook in story.get('hooks') or () if hook.get('by')}
    return names


def compute_tier(runtime, body, planning_input):
    """routine / normal / consequential, from what the engine already knows (kit_router)."""
    here = turn_speakers(runtime, body)
    speakers = [s for s in here['speakers'] if s not in NON_NPC_SPEAKERS]
    if ADDRESSING.search(body.get('action') or ''):
        # Someone heard through the door can answer through it when the PC speaks (watchroom T5).
        speakers += [h['speaker'] for h in here.get('heard') or ()]
    threads = planning_input.get('open_threads') or {}
    return kit_router.route(body['kind'], body.get('events') or (), runtime.load()[1], speakers,
                            important_speakers(runtime.source()), body.get('story_due') or (),
                            threads_due=bool(threads.get('due')) if isinstance(threads, dict) else False,
                            held=bool(body.get('held_description')))


def first_try_lines(runtime, body, planning_input):
    """A few lines at the top of every packet stating what the engine already knows it will
    check this turn, so the first decision commits (watchroom T0 and T8: the opening's reply_to
    and story basis, an emotion label, a terse guard). Nothing here relaxes a check."""
    source = runtime.source()
    candidates = planning_input.get('discernment_candidates') or {}
    opening = body['kind'] == 'opening'
    cards = (source.get('public_performance') or {}).get('actor_cards') or {}
    speakers = turn_speakers(runtime, body)
    actors = [s for s in speakers['speakers'] if s not in NON_NPC_SPEAKERS]
    terse = [name for name in actors if (cards.get(name) or {}).get('speech_floor') is not True]
    lines = [
        ('Room entry: reply_to is none (set for you); move world_description; scope feature, at least '
         f'{FEATURE_MIN_WORDS} words in {FEATURE_MIN_SEGMENTS}+ segments.') if opening else
        "reply_to: a short verbatim quote of the player's words.",
        'improv_read story_anchor -> story_basis: ' + '; '.join(
            f'{anchor}: {", ".join(bases)}' for anchor, bases in (candidates.get('story_bases') or {}).items())
        + ' (anything else falls back to scene_state).',
        'actor_ref and focus_actor: ' + ', '.join(candidates.get('actor_bases') or ['none']) + '.',
        'appraisal.label: ' + ', '.join(APPRAISAL_LABELS) + ' (none needs intensity 0).',
        'Speakers this turn: ' + ', '.join(speakers['speakers'])
        + (f"; heard only, not here: {', '.join(h['speaker'] for h in speakers['heard'])}" if speakers.get('heard') else '')
        + '. Every Kit segment needs reacts_to (a short verbatim quote of a public line this turn).',
    ]
    if terse:
        lines.append(f'Terse is fine for {", ".join(terse)}: one short line meets the actor side; do not pad. '
                     f'An exchange still needs {EXCHANGE_MIN_WORDS} words across non-Kit segments in '
                     f'{EXCHANGE_MIN_SEGMENTS}+ segments; a call at most {CALL_MAX_WORDS} words.')
    if body.get('story_due'):
        lines.append('Due now: ' + ', '.join(f"{item.get('id')} (raised by {item.get('by')})"
                                             for item in body['story_due']) + ', in character, this turn.')
    if planning_input.get('check_request'):
        lines.append('The player asked for a check: call one in roll_call or decline. You pick the skill.')
    if planning_input.get('threshold_view'):
        lines.append('A look or listen through a threshold: describe only threshold_view (tease-only); the PC has not moved.')
    if planning_input.get('open_threads'):
        lines.append('Open threads are listed in open_threads: pay off or drop them before the scene ends.')
    held = planning_input.get('held_description')
    if held:
        lines.append(f"The roll is in ({held['roll']}): deliver the held {held['kind']} description now, "
                     'scaled to the result (held_description); not another call.')
    elif body['kind'] in STALL_KINDS and not body.get('story_due') and \
            not (runtime.load()[1].get('pending_check') or {}).get('held'):
        lines.append(STALL_LINE)
    if not opening and not held:
        lines.append(SHORT_BEAT_LINE)
    compute = planning_input.get('compute') or {}
    if compute.get('tier') == 'routine':
        lines.append('Routine turn (engine): you may leave out ' + ', '.join(compute['may_omit'])
                     + '; the engine fills neutral values. Write move, kit_choice, the brief and the speech.')
    return lines


HOST_STAMPS = ('received_at', 'model_sent_at', 'model_done_at', 'shown_at')


def check_stamps(stamps):
    """Host stamps are epoch seconds under their known names (HOST_TIMING.md)."""
    require(isinstance(stamps, dict) and set(stamps) <= set(HOST_STAMPS) and
            all(type(value) in (int, float) and value > 0 for value in stamps.values()),
            f'Host stamps are epoch seconds named {", ".join(HOST_STAMPS)}')
    return {key: float(value) for key, value in stamps.items()}


def turn_latency(timing):
    """End-to-end time for one turn, from the player's message to Kit's first playable line,
    split into host, runtime, model, validation and retry. Durations the host did not stamp are
    None and named in ``missing``; nothing is guessed."""
    timing = timing or {}
    stamps = timing.get('host_stamps') or {}
    attempts = timing.get('attempts') or []
    missing = [key for key in HOST_STAMPS if key not in stamps and not (
        key in ('model_sent_at', 'model_done_at') and attempts and all(key in a for a in attempts))]
    span = lambda a, b: round(b - a, 3) if a is not None and b is not None else None
    model = [span(a.get('model_sent_at'), a.get('model_done_at')) for a in attempts]
    model_s = round(sum(model), 3) if model and None not in model else None
    first_sent = next((a['model_sent_at'] for a in attempts if 'model_sent_at' in a), None)
    rejected = [a for a in attempts if a['outcome'] == 'rejected']
    last_done = attempts[-1].get('model_done_at') if attempts else None
    retry_s = span(rejected[0].get('model_done_at'), last_done) if rejected else 0.0
    received, shown = stamps.get('received_at'), stamps.get('shown_at')
    end = span(received, shown)
    runtime_s = (timing.get('runtime_prepare_ms') or 0) / 1000
    validation_ms = round(sum(a.get('validation_ms') or 0 for a in attempts), 2)
    host = None
    if end is not None and model_s is not None:
        host = round(end - model_s - runtime_s - validation_ms / 1000, 3)
    return {'end_to_end_s': end, 'host_s': host,
            'host_before_prepare_s': span(received, timing.get('prepare_started_at')),
            'host_prepare_to_model_s': span(timing.get('prepared_at'), first_sent),
            'runtime_prepare_ms': timing.get('runtime_prepare_ms'), 'model_s': model_s,
            'validation_ms': validation_ms, 'retry_s': retry_s, 'rejects': len(rejected),
            'shown_after_commit_s': span(timing.get('committed_at'), shown),
            'packet_bytes': timing.get('packet_bytes'),
            'output_bytes': [a['output_bytes'] for a in attempts], 'missing': missing}


class KitChatBridge:
    """Host this model loop in an assistant chat, with no API credential in Python."""
    def __init__(self, runtime, adjudicator=None, manifests=False):
        """``manifests``: send one-pass packets in three layers (kit_manifest; the live CLI
        does). Off by default, so staged evals and the Python API see the full packet."""
        self.runtime = runtime
        self.adjudicator = adjudicator or RoomAdjudicator()
        self.manifests = manifests

    @_stale_guided
    def prepare(self, action=None, turn_id=None, use_memory=True, one_pass=False, opening=False,
                performance_variant=None, table_talk=False, host_stamps=None):
        """Stage a turn. One-pass turns fix their performer variant here (default
        DEFAULT_BRIDGE_VARIANT); staged turns choose it at decide. ``table_talk``: the host
        marks the line as the player talking to Kit mid-scene (meta mode, never adjudicated,
        recorded as table talk); the hidden-information guards still apply."""
        turn_id = turn_id or str(uuid.uuid4())
        started = time.time()
        clock = time.perf_counter()
        stamps = check_stamps(host_stamps or {})
        require(one_pass or performance_variant is None,
                'A staged turn chooses its performance variant at decide')
        if one_pass:
            performance_variant = check_variant(performance_variant or DEFAULT_BRIDGE_VARIANT)
        if opening:
            require(action is None and not table_talk, 'Room opening does not take a player action')
            revision, body, planning_input = prepare_opening(self.runtime, one_pass=one_pass)
        else:
            try:
                revision, body, planning_input = prepare_turn(
                    self.runtime, self.adjudicator, action, use_memory, one_pass=one_pass,
                    table_talk=table_talk)
            except PendingRuling as exc:
                if not exc.attempt:
                    raise
                # Record the refused attempt publicly so the next turn can refer to it.
                recorded = self.runtime.record_refused_attempt(action, str(exc))
                ruling = PendingRuling(f'{exc} The attempt is noted in the public history.', attempt=True)
                ruling.recorded_revision = recorded
                raise ruling from exc
        body['host_mode'] = 'one_pass' if one_pass else 'staged'
        if one_pass:
            body['performance_variant'] = performance_variant
            # The engine decides how much this turn asks Kit to write (kit_router; PR4).
            body['compute'] = compute_tier(self.runtime, body, planning_input)
            if body['compute']['tier'] == 'routine':  # only a routine turn changes what Kit writes
                planning_input['compute'] = body['compute']
        self.runtime.stage_kit_turn(turn_id, revision, body)
        # Wall clock, not monotonic: stages may run in separate processes.
        self.runtime.record_kit_timing(turn_id, mode=body['host_mode'], prepared_at=time.time(),
                                       prepare_started_at=started,
                                       **({'performance_variant': performance_variant}
                                          if one_pass else {}))
        if stamps:
            self.stamp(turn_id, **stamps)
        warning = load_voice()[1]
        notice = {'voice_warning': warning} if warning else {}
        if body.get('memory_turn_ids') is not None:
            # Loud, not silent: the host sees that Kit's memory was cut to fit the budget.
            notice['context_warning'] = MEMORY_TRIMMED_NOTE
        if body.get('table_talk'):
            notice['table_talk'] = TABLE_TALK_NOTE
        first_try = first_try_lines(self.runtime, body, planning_input)
        if one_pass:
            packet = {'first_try': first_try, 'turn_id': turn_id, 'stage': 'one_pass', **notice,
                      'performance_variant': performance_variant,
                      'instructions': one_pass_instructions(performance_variant),
                      'schema': ONE_PASS_SCHEMA,
                      'performance_limits': performance_limits(), 'host_retry': HOST_RETRY_NOTE,
                      'input': {'private': planning_input,
                                'public': public_performance_base(self.runtime, body, one_pass=True)}}
        else:
            packet = {'first_try': first_try, 'turn_id': turn_id, 'stage': 'private_decision', **notice,
                      'instructions': PRIVATE_INSTRUCTIONS, 'schema': PLAN_SCHEMA,
                      'performance_limits': performance_limits(), 'host_retry': HOST_RETRY_NOTE,
                      'input': planning_input}
        manifest = {}
        if one_pass and self.manifests:
            packet, manifest = self._layer(turn_id, packet)
        # Runtime time and packet size, from the bridge's own clock (docs/architecture/HOST_TIMING.md).
        self.runtime.record_kit_timing(turn_id, runtime_prepare_ms=round((time.perf_counter() - clock) * 1000, 2),
                                       packet_bytes=_bytes(packet), **manifest)
        return packet

    def _layer(self, turn_id, packet):
        """SessionManifest, RoomManifest, TurnDelta (kit_manifest). A body the host was sent
        recently is replaced by its hash."""
        session, room, _ = kit_manifest.split(packet)
        hashes = {'session': kit_manifest.digest(session), 'room': kit_manifest.digest(room)}
        recent = [row for row in self.runtime.recent_kit_timings(limit=kit_manifest.FULL_EVERY + 1)
                  if row['turn_id'] != turn_id]
        held = kit_manifest.plan_sends(recent)
        cached = {layer: hashes[layer] in held[layer] for layer in hashes}
        layered, _, _ = kit_manifest.layered(packet, cached['session'], cached['room'])
        return layered, {'manifest': {**hashes, 'sent': [layer for layer in hashes if not cached[layer]]},
                         'room_manifest': room, 'full_packet_bytes': _bytes(packet)}

    def rehydrate(self, turn_id):
        """Both manifest bodies for a layered turn, in full (the host lost a copy)."""
        timing = self.runtime.kit_timing(turn_id) or {}
        record = timing.get('manifest')
        require(record is not None, f'Turn {turn_id!r} was not sent in layers; nothing to rehydrate')
        variant = timing.get('performance_variant') or DEFAULT_BRIDGE_VARIANT
        session = {'performance_variant': variant, 'instructions': one_pass_instructions(variant),
                   'schema': ONE_PASS_SCHEMA, 'performance_limits': performance_limits(),
                   'host_retry': HOST_RETRY_NOTE, 'personality_core': personality_core_text()}
        room = timing.get('room_manifest') or {}
        hashes = {'session': kit_manifest.digest(session), 'room': kit_manifest.digest(room)}
        self.runtime.record_kit_timing(turn_id, manifest={**hashes, 'sent': ['session', 'room']})
        return {'turn_id': turn_id,
                'session_manifest': {'hash': hashes['session'], 'body': session},
                'room_manifest': {'hash': hashes['room'], 'body': room},
                'manifest_rule': kit_manifest.MANIFEST_RULE}

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
            turn_id, pending['revision'], turn_events(self.runtime, body, pending['plan'], turn_id, record),
            record, consume_pending=True)
        return self._committed_result(turn_id, revision, body, record, variant)

    def _committed_result(self, turn_id, revision, body, record, variant):
        result = {'revision': revision, 'turn_id': turn_id,
                  'public_event': record['public_event'], 'spoken': record['spoken'],
                  'performance_variant': variant, 'timing': self._finish_timing(turn_id, record)}
        if record['trace'].get('ask_player'):
            result.update(asked=True, next_step=ASKED_NEXT_STEP)
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

    def stamp(self, turn_id, **stamps):
        """Record host-side times for a turn (epoch seconds): received_at (the player's message
        arrived), model_sent_at / model_done_at (the packet went to the model / its output came
        back), shown_at (Kit's first playable line was shown). See HOST_TIMING.md."""
        stamps = check_stamps(stamps)
        prior = self.runtime.kit_timing(turn_id) or {}
        self.runtime.record_kit_timing(turn_id, host_stamps={**(prior.get('host_stamps') or {}), **stamps})
        return {'turn_id': turn_id, 'host_stamps': {**(prior.get('host_stamps') or {}), **stamps}}

    def _attempt(self, turn_id, output, host_stamps, clock, outcome):
        """One submitted output: its bytes, the model trip the host stamped, validation time."""
        prior = self.runtime.kit_timing(turn_id) or {}
        stamps = check_stamps(host_stamps or {})
        attempt = {'output_bytes': _bytes(output), 'validation_ms': round((time.perf_counter() - clock) * 1000, 2),
                   'outcome': outcome, **{key: stamps[key] for key in ('model_sent_at', 'model_done_at') if key in stamps}}
        self.runtime.record_kit_timing(turn_id, attempts=list(prior.get('attempts') or []) + [attempt])

    @_stale_guided
    def complete(self, turn_id, output, degraded=False, host_stamps=None):
        """Validate and commit one model output in one host round trip. ``host_stamps``: the
        host's model_sent_at and model_done_at for this output (HOST_TIMING.md)."""
        clock = time.perf_counter()
        try:
            record = (self.runtime.kit_timing(turn_id) or {}).get('manifest')
            if isinstance(output, dict) and (record or 'manifest' in output):
                kit_manifest.check_echo(output, record)
                output = {key: value for key, value in output.items() if key != 'manifest'}
            result = self._complete(turn_id, output, degraded)
        except InvalidChange:
            self._attempt(turn_id, output, host_stamps, clock, 'rejected')
            raise
        if not result.get('already_committed'):
            self._attempt(turn_id, output, host_stamps, clock, 'committed')
            result['timing'] = self.runtime.kit_timing(turn_id)
        return result

    def _complete(self, turn_id, output, degraded=False):
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
            turn_id, revision, turn_events(self.runtime, body, plan, turn_id, record), record,
            consume_pending=True)
        return self._committed_result(turn_id, next_revision, body, record, variant)


EXAMPLE_SHEET = PROJECT_ROOT / 'tests/fixtures/characters/example_pc.json'


def start_session(db, sheet_path=None, runtime=None, room=None, area=None, manifests=False):
    """The one bootstrap step for any AI hosting Kit (see AGENTS.md): create a fresh room
    session, load the player's sheet (the generic example PC when none is given), and
    stage the room's opening through the bridge. Returns the first prepare packet plus
    the exact next command, so a new host cannot take a wrong first step."""
    # Mount first: a room that cannot mount fails here, before any database is touched,
    # with the host's error and Kit's plain table line (kit_rooms.RoomMountError).
    source = kit_rooms.load_room(room or DEFAULT_ROOM)
    if area is not None and area not in source['areas']:
        raise kit_rooms.RoomMountError(room or DEFAULT_ROOM, [f'no area {area!r} in this room'])
    own = runtime is None
    runtime = runtime or Runtime(db)
    try:
        try:
            runtime.initialize(source, area or source['starting_area'], room_path=room or DEFAULT_ROOM)
        except InvalidChange as exc:
            raise InvalidChange(f'{exc} Resume it with view and '
                                'prepare, or pass a new --db to start fresh.') from exc
        path = Path(sheet_path) if sheet_path else EXAMPLE_SHEET
        sheet = json.loads(path.read_text(encoding='utf-8'))
        loaded = runtime.set_player_sheet(sheet)
        prepared = KitChatBridge(runtime, RoomAdjudicator(), manifests=manifests).prepare(
            opening=True, one_pass=True)
        turn = prepared['turn_id']
        return {
            'stage': 'started', 'db': str(db), 'character': loaded['character'],
            'sheet': str(path), 'example_sheet': not sheet_path,
            'next_step': ('You are Kit. Write one JSON object {"decision", "performance"} that follows '
                          'prepared.instructions and prepared.schema, save it to a file, then run: '
                          f'python3 -m runtime.kit_agent complete --db {db} --turn-id {turn} '
                          '--input-file <file>. Show the player only the "spoken" field. Every later '
                          f'turn: python3 -m runtime.kit_agent prepare --one-pass --db {db} '
                          '--action "<the player\'s words>", then complete again. When the player talks to you, '
                          'not the room, mid-scene, add --table-talk to prepare.'
                          + (' Add "manifest": {"session": <session_manifest.hash>, "room": <room_manifest.hash>} '
                             'to every output; a "cached" manifest is the copy you were sent earlier '
                             '(rehydrate --turn-id T if you lost it).' if manifests else '')),
            'prepared': prepared,
        }
    finally:
        if own:
            runtime.close()


# Two lines of host framing printed after the persona (persona-continuity R2). They state the
# authority split only; who Kit is lives in the personality core itself.
PERSONA_AUTHORITY_NOTE = (
    'Authority: outside a running scene, talk as Kit with no command; nothing said there is game state.\n'
    'In play, the bridge (start, prepare, complete) owns rules, hidden state, and what happened; prep talk is not canon.')


def persona_text(folder=None):
    """The exact persona text the bridge sends (personality_core_text), any voice-cap
    warning, and the authority note. No database, no scene, no state."""
    warning = load_voice(folder)[1]
    parts = [personality_core_text(folder).rstrip('\n')]
    if warning:
        parts.append(f'Voice warning: {warning}')
    parts.append(PERSONA_AUTHORITY_NOTE)
    return '\n\n'.join(parts) + '\n'


def _cli_stamps(items):
    out = {}
    for item in items or ():
        name, _, value = item.partition('=')
        try:
            out[name.strip()] = float(value)
        except ValueError:
            raise InvalidChange(f'--stamp takes NAME=EPOCH_SECONDS, got {item!r}') from None
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start', 'init', 'view', 'visual', 'prepare', 'decide', 'finish', 'complete',
                                            'abandon', 'feedback', 'character', 'notes', 'play', 'trace',
                                            'timing', 'persona', 'stamp', 'rehydrate'])
    parser.add_argument('--db', default='kit.sqlite')
    parser.add_argument('--room', help='start/init: a room file to mount (default: area 6c; see '
                                       'docs/architecture/ROOM_LOADER.md)')
    parser.add_argument('--area', help='start: begin in this area of the room (default: its starting_area)')
    parser.add_argument('--model', help='Optional standalone Responses API model for play')
    parser.add_argument('--perception', type=int, help='Test character Wisdom (Perception) modifier')
    parser.add_argument('--insight', type=int, help='Test character Wisdom (Insight) modifier')
    parser.add_argument('--sleight-of-hand', dest='sleight_of_hand', type=int,
                        help='Test character Dexterity (Sleight of Hand) modifier, for card play')
    parser.add_argument('--no-memory', action='store_true', help='Ablation: hide Kit’s prior episodes from her decision stage')
    parser.add_argument('--one-pass', action='store_true', help='One model output for live chat; use complete to commit')
    parser.add_argument('--performance-variant', choices=PERFORMANCE_VARIANTS,
                        help=f'Performer instructions: for prepare --one-pass or decide (default '
                             f'{DEFAULT_BRIDGE_VARIANT}), or for play (default current)')
    parser.add_argument('--opening', action='store_true', help='Prepare the initial scene entry instead of a player action')
    parser.add_argument('--table-talk', dest='table_talk', action='store_true',
                        help='prepare: the host marks this line as table talk to Kit mid-scene (meta mode, '
                             'not adjudicated, not logged as the PC speaking; leak guards still apply)')
    parser.add_argument('--action', help='Player action for prepare')
    parser.add_argument('--action-file', help='UTF-8 player action file for prepare')
    parser.add_argument('--request', help='visual: the user\'s exact art request')
    parser.add_argument('--visual-mode', dest='visual_mode', choices=kit_visual.VISUAL_MODES,
                        help='visual: requested asset mode (default scene_vignette)')
    parser.add_argument('--turn-id', help='Turn ID returned by prepare')
    parser.add_argument('--input-file', help='JSON plan, speech, or combined output; - reads stdin')
    parser.add_argument('--text', help='feedback: the player’s out-of-character comment')
    parser.add_argument('--evidence', action='append',
                        help='feedback: committed turn ID the comment is about (repeatable; '
                             'default: latest turn)')
    parser.add_argument('--name', help='character: the player character\'s name')
    parser.add_argument('--ancestry', help='character: the player character\'s ancestry (e.g. Harengon)')
    parser.add_argument('--class-name', dest='class_name', help='character: class (optional)')
    parser.add_argument('--level', type=int, help='character: level (optional)')
    parser.add_argument('--sheet', help='start/character: a character_sheet_v1 JSON file (any PC; see '
                                        'runtime/pc_sheet.py). start defaults to the example PC')
    parser.add_argument('--held', help='character: comma list of what the PC holds now ("" for nothing)')
    parser.add_argument('--active', help='character: comma list of spells/conditions active now')
    parser.add_argument('--replaces', default='none', help='feedback: note id this feedback supersedes')
    parser.add_argument('--degraded', action='store_true',
                        help=f'finish/complete: accept style misses as warnings (only after '
                             f'{DEGRADED_AFTER_REJECTIONS} rejections on the turn)')
    parser.add_argument('--stamp', action='append', default=[],
                        help='prepare/complete/stamp: a host time NAME=EPOCH_SECONDS, one of '
                             + ', '.join(HOST_STAMPS) + ' (docs/architecture/HOST_TIMING.md); repeatable')
    parser.add_argument('--full', action='store_true',
                        help='prepare --one-pass/start: send the whole packet, not the three layers '
                             '(docs/architecture/MANIFESTS.md)')
    parser.add_argument('--pretty', action='store_true',
                        help='prepare/decide/finish/complete: indent the JSON for reading (default compact)')
    args = parser.parse_args()
    if args.command == 'persona':
        # Kit before any game: the persona text the bridge uses, with no database or scene.
        sys.stdout.write(persona_text())
        return 0
    if args.command == 'start':
        try:
            result = start_session(args.db, args.sheet, room=args.room, area=args.area, manifests=not args.full)
        except kit_rooms.RoomMountError as exc:
            print(json.dumps(exc.host_view(), ensure_ascii=False), file=sys.stderr)
            return 2
        except (InvalidChange, PendingRuling) as exc:
            print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False,
                         **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
        return 0
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = kit_rooms.load_room(args.room or DEFAULT_ROOM)
            runtime.initialize(source, source['starting_area'])
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'view':
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'visual':
            if not args.request:
                parser.error('visual requires --request')
            try:
                result = kit_visual.build_visual_brief(runtime, args.request, args.visual_mode)
                kit_visual.validate_visual_brief(result)
            except InvalidChange as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False,
                             **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
        elif args.command == 'trace':
            print(json.dumps(runtime.recent_kit_turns(), indent=2, ensure_ascii=False))
        elif args.command == 'timing':
            print(json.dumps([{**row, 'latency': turn_latency(row)} for row in runtime.recent_kit_timings()],
                             indent=2, ensure_ascii=False))
        elif args.command == 'rehydrate':
            if not args.turn_id:
                parser.error('rehydrate requires --turn-id')
            try:
                print(json.dumps(KitChatBridge(runtime).rehydrate(args.turn_id), ensure_ascii=False))
            except InvalidChange as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
                return 2
        elif args.command == 'stamp':
            if not args.turn_id or not args.stamp:
                parser.error('stamp requires --turn-id and at least one --stamp NAME=EPOCH_SECONDS')
            try:
                print(json.dumps(KitChatBridge(runtime).stamp(args.turn_id, **_cli_stamps(args.stamp)),
                                 ensure_ascii=False))
            except (InvalidChange, ValueError) as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
                return 2
        elif args.command == 'notes':
            print(json.dumps(runtime.player_notes(), indent=2, ensure_ascii=False))
        elif args.command == 'character' and args.sheet:
            sheet = json.loads(Path(args.sheet).read_text(encoding='utf-8'))
            print(json.dumps(runtime.set_player_sheet(sheet), indent=2, ensure_ascii=False))
        elif args.command == 'character' and (args.held is not None or args.active is not None):
            lists = {key: [v.strip() for v in value.split(',') if v.strip()]
                     for key, value in (('held', args.held), ('active', args.active)) if value is not None}
            print(json.dumps(runtime.set_pc_state(**lists), indent=2, ensure_ascii=False))
        elif args.command == 'character':
            if not (args.name and args.ancestry):
                parser.error('character requires --sheet, or --name and --ancestry')
            print(json.dumps(runtime.set_player_character(args.name, args.ancestry, args.class_name,
                                                          args.level), indent=2, ensure_ascii=False))
        elif args.command in ('prepare', 'decide', 'finish', 'complete', 'abandon', 'feedback'):
            bridge = KitChatBridge(runtime, RoomAdjudicator(args.perception, args.insight,
                                                             sleight_of_hand=args.sleight_of_hand),
                                   manifests=not args.full)
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
                                            performance_variant=args.performance_variant,
                                            table_talk=args.table_talk, host_stamps=_cli_stamps(args.stamp))
                else:
                    if not args.turn_id or not args.input_file:
                        parser.error(f'{args.command} requires --turn-id and --input-file')
                    raw = sys.stdin.read() if args.input_file == '-' else Path(args.input_file).read_text(encoding='utf-8')
                    submitted = json.loads(raw)
                    variant = args.performance_variant or DEFAULT_BRIDGE_VARIANT
                    result = (bridge.decide(args.turn_id, submitted, variant) if args.command == 'decide' else
                              bridge.finish(args.turn_id, submitted, degraded=args.degraded)
                              if args.command == 'finish' else
                              bridge.complete(args.turn_id, submitted, degraded=args.degraded,
                                              host_stamps=_cli_stamps(args.stamp)))
            except PendingRuling as exc:
                result = {'stage': 'pending_ruling', 'message': str(exc), 'committed': False}
                if getattr(exc, 'host_error', None):
                    result['host_error'] = exc.host_error
                if getattr(exc, 'recorded_revision', None) is not None:
                    result.update(attempt_recorded=True, revision=exc.recorded_revision)
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
            # Compact by default: the chat host reads this whole packet every turn, and
            # indentation alone added about a quarter to its size. --pretty for people.
            print(json.dumps(result, ensure_ascii=False,
                             **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
        else:
            if not args.model:
                parser.error('standalone play requires --model; for ChatGPT use prepare/decide/finish')
            if not os.environ.get('OPENAI_API_KEY'):
                parser.error('standalone play requires OPENAI_API_KEY; for ChatGPT use prepare/decide/finish')
            model = OpenAIResponsesModel(args.model)
            agent = KitAgent(runtime, model, RoomAdjudicator(args.perception, args.insight,
                                                               sleight_of_hand=args.sleight_of_hand),
                             performance_variant=args.performance_variant or 'current')
            print(f"Kit's table: {runtime.source().get('id')}. Enter an action, or /quit. Private traces: separate trace command.")
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

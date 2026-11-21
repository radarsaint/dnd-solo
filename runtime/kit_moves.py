"""The turn spine: eight player moves, one open ask, one skill picker, one speaking contract.

Room-agnostic and book-agnostic. Standard library only. Nothing here writes player-facing
prose; it classifies, routes, checks, and explains a rejection in one ``Fix:`` line.

Every player message is one of eight moves (Brendon, 2026-11-13):

    look     notice, search, examine        -> passive first, then a called check
    talk     speak to someone present       -> the NPC answers, or a social check
    recall   what the character knows       -> background baseline, then a knowledge check
    move     go somewhere                   -> an exit or a clarify that names the ways on
    use      an item, feature, or spell     -> the sheet or the object
    fight    attack, initiative, combat act -> the fight engine
    rest     short or long rest             -> the rest procedure
    ask_dm   a question to Kit, out of play -> Kit answers as Kit (rules, the table, a ruling)

The host declares the move it read in the decision (``player_move``, optional); Python checks
the declaration and keeps a deterministic default (``classify``) as the cross-check.

The open ask (``open_ask``): whenever Kit asks the player for something (a roll, initiative,
an attack or damage total, a save, a confirm, an answer to an NPC's question), the ask carries
why it was asked: the subject, the player's own words, the skill, and who is waiting. The
next message is resolved against it first. A number never arrives without a reason.

The skill picker (``pick_skill``): the move and its object choose the skill, not a word list.
Looking for anything hidden (scanning brush, watching a treeline, listening for movement) is
Perception. A passive score that meets the hidden number reveals without a roll; an active
roll on a notice never comes out below the passive. The player may push back on the skill in
fiction ("shouldn't that be Perception?"); Kit accepts when the requested skill fits the act.

The speaking contract (``speaking_problems`` / ``check_speaking_contract``): a reply is not a
bare number or a bare rule, never prints an internal label, never asks a question it already
answered in the same reply or asks for a roll the player already gave, and never moves the PC
against what the player said he does.
"""
import re

from . import _lazy
from .state_context import InvalidChange

MOVES = ('look', 'talk', 'recall', 'move', 'use', 'fight', 'rest', 'ask_dm')
STANCES = ('none', 'hold', 'advance', 'withdraw')

PLAYER_MOVE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['kind'],
    'properties': {
        'kind': {'type': 'string', 'enum': list(MOVES)},
        'target': {'type': 'string'},
        'stance': {'type': 'string', 'enum': list(STANCES)},
    },
}

OPEN_ASK_KINDS = ('roll', 'initiative', 'attack', 'damage', 'save', 'confirm', 'npc_question',
                  'choice', 'sheet')

SKILLS = ('athletics', 'acrobatics', 'sleight_of_hand', 'stealth', 'animal_handling', 'medicine',
          'survival', 'perception', 'insight', 'intimidation', 'deception', 'persuasion',
          'religion', 'arcana', 'nature', 'history', 'investigation')
KNOWLEDGE_SKILLS = ('history', 'arcana', 'religion', 'nature')

# -- classification ------------------------------------------------------------------------

_Q = re.compile(r"['\u2018\u2019]")


def _plain(text):
    return _Q.sub("'", str(text or '')).strip()


def _read(text):
    """The line as the move and skill readers see it: typos repaired (runtime/kit_lexicon.py)."""
    from . import kit_lexicon
    return _plain(kit_lexicon.normalize(_plain(text)))


# Looking FOR something that may be hidden, or watching a place for what moves in it.
# Object-led ("for anyone hiding", "for an ambush") so "I hide behind the crates" stays Stealth.
_NOTICE_VERB = (r"scan\w*|watch\w*|survey\w*|sweep\w*|peer\w*|squint\w*|listen\w*|"
                r"keep(?:s|ing)? (?:an |my |a close |a careful |our )?eyes? (?:on|out)|"
                r"eyes? on|look(?:s|ing|ed)? (?:over|out|around|about|for|across|along|into|at the "
                r"(?:brush|trees|treeline|thickets?|bushes|ridge|embankment|shadows|woods|rocks|undergrowth))|"
                r"search(?:es|ing)? the (?:brush|trees|treeline|thickets?|bushes|ridge|embankment|"
                r"shadows|woods|rocks|undergrowth|tree ?line|hills?|road|trail) for|"
                r"study(?:ing)? the (?:brush|trees|treeline|thickets?|bushes|ridge|embankment|"
                r"shadows|woods|rocks|undergrowth)|check(?:s|ing)? the (?:brush|trees|treeline|thickets?|"
                r"bushes|ridge|embankment|shadows|woods|rocks|undergrowth) for|"
                r"ears? (?:up|turn\w*|swivel\w*|prick\w*)|on (?:guard|alert|the lookout)|notice\w*|spot\w*")
_NOTICE_OBJECT = (r"\bfor (?:any(?:one|body|thing)? |some(?:one|body|thing) |signs? of |movement|motion|"
                  r"an? ambush|ambush\w*|archers?|watchers?|hidden|lurk\w*|hiding|trouble|danger|threats?|"
                  r"enemies|foes|bandits|scouts|eyes|tracks)"
                  r"|\b(?:anyone|anybody|someone|something) (?:hiding|hidden|lurking|watching|waiting)\b"
                  r"|\bhidden (?:archers?|foes|enemies|figures?|attackers?|watchers?)\b")
NOTICE_RE = _lazy.regex(r"(?i)\b(?:" + _NOTICE_VERB + r")\b")
NOTICE_OBJECT_RE = _lazy.regex(r"(?i)" + _NOTICE_OBJECT)
_RECALL_RE = _lazy.regex(r"(?i)\b(?:do|does|did|would|might|could) (?:i|we|nik|he|she|they) "
                        r"(?:know|recall|remember|recognize|recognise)\b|\bwhat do (?:i|we) know\b")
_SEARCH_OBJECT_RE = _lazy.regex(r"(?i)\b(?:search|rummage|go through|pat down|examine|inspect)\w* "
                               r"(?:the |this |that |his |her |their |its )?(?:chest|crate|desk|body|"
                               r"bodies|corpse|pack|saddlebags?|wagon|cart|drawer|room|shelf|shelves|"
                               r"pockets?|bag|box|horses?|carcass)")


def notice_intent(action):
    """True when the act looks or listens for something that may be hidden."""
    text = _read(action)
    if not text or _RECALL_RE.search(text):
        return False
    if _SEARCH_OBJECT_RE.search(text) and not NOTICE_OBJECT_RE.search(text):
        return False
    return bool(NOTICE_RE.search(text) or NOTICE_OBJECT_RE.search(text) and re.search(
        r"(?i)\b(?:look|search|check|study|eye|glance|stare|gaze)\w*\b", text))


_HOLD_RE = _lazy.regex(
    r"(?i)\b(?:stop(?:s|ping|ped)?(?: \w+){0,3} (?:back|short|here|where|at)|"
    r"stay(?:s|ing)?(?: put| back| here| where| at| behind| in cover| hidden)?|"
    r"hold(?:s|ing)? (?:my |our |his )?(?:position|ground|back|here)|hang(?:s|ing)? back|"
    r"remain(?:s|ing)?(?: \w+){0,2} (?:back|here|where|behind)|keep(?:s|ing)? (?:my |our |his )?distance|"
    r"wait(?:s|ing)? (?:here|back|where)|don'?t (?:move|go|approach)|not (?:moving|approaching|going "
    r"(?:any )?(?:closer|forward|nearer))|(?:\d+|fifty|thirty|forty|sixty|a hundred) (?:feet|ft\.?|yards) back)\b")
_ADVANCE_RE = _lazy.regex(
    r"(?i)\b(?:approach\w*|go(?:es)? (?:up|forward|over|closer|ahead)|walk\w* (?:up|over|forward|closer)|"
    r"mov\w* (?:up|forward|closer|in)|advanc\w*|head\w* (?:over|toward|towards|up)|step\w* (?:forward|closer|up))\b")
_WITHDRAW_RE = _lazy.regex(r"(?i)\b(?:back away|back off|retreat\w*|withdraw\w*|fall back|run away|flee\w*)\b")


def stance_of(action):
    """Where the player said the PC stands: hold, advance, withdraw, or none."""
    text = _plain(action)
    if _HOLD_RE.search(text):
        return 'hold'
    if _WITHDRAW_RE.search(text):
        return 'withdraw'
    if _ADVANCE_RE.search(text):
        return 'advance'
    return 'none'


_REST_RE = _lazy.regex(r"(?i)\b(?:short rest|long rest|take a rest|make camp|set up camp|camp for the night|"
                      r"sleep (?:here|for the night)|bed down)\b")
_FIGHT_RE = _lazy.regex(r"(?i)\b(?:attack\w*|stab\w*|slash\w*|shoot\w*|fire (?:at|an arrow)|swing\w* at|"
                       r"strike\w*|punch\w*|initiative|cast \w+(?: \w+)? at)\b")
_MOVE_RE = _lazy.regex(r"(?i)\b(?:go(?:es)? (?:to|into|through|back|down|up|north|south|east|west|in)|"
                      r"head\w* (?:to|for|into|back|north|south|east|west)|walk\w* (?:to|into|through)|"
                      r"enter\w*|leave|travel\w*|follow (?:the )?(?:trail|road|path|tracks)|"
                      r"climb\w* (?:up|down|into))\b")
_TALK_RE = _lazy.regex(r"(?i)[\"\u201c]|\b(?:i (?:say|ask|tell|call out|shout|greet|whisper)|ask (?:him|her|them)|"
                      r"talk to|speak (?:to|with))\b")
_USE_RE = _lazy.regex(r"(?i)\b(?:cast\w*|drink\w*|use\w*|light\w* (?:a|my|the) (?:torch|lantern)|"
                     r"read\w* the scroll|open\w* (?:the|my)|unlock\w*|pick\w* the lock|put on|draw\w* my)\b")
_ASK_DM_RE = _lazy.regex(r"(?i)^\s*(?:\(|ooc\b|kit,|q:)|\b(?:shouldn'?t|wouldn'?t|isn'?t|is) (?:th(?:is|at|e)|it|"
                        r"\w+ing(?: \w+){0,3}) (?:not )?(?:be )?(?:an? )?(?:" + '|'.join(s.replace('_', ' ') for s in SKILLS) +
                        r")\b|\bhow does (?:that|this|\w+) work\b|\bwhat(?:'s| is) the rule\b"
                        r"|\bcan i (?:use|take|spend) (?:my |a |an )?(?:bonus action|reaction|action|movement)\b"
                        r"|\bdoes (?:that|this|it) (?:provoke|count as|use|take) |\bhow (?:far|many feet) can i\b"
                        r"|\bdo (?:i|we) (?:need|have) to roll\b|\bis my (?:passive )?\w+ (?:enough|high enough)\b")


# A question put as a rules question ("Can I stay hidden if I use my bonus action?", "Does
# hiding end when I cast?") asks the DM, whatever the stance in it.
_RULES_QUESTION_RE = _lazy.regex(
    r"(?i)(?:^|[.!,]\s+)(?:can|could|do|does|did|is|am|are|would|will|should|if|how|when|what)\b[^.!?]*\b(?:"
    r"bonus action|reaction|(?:an |my |the )action|advantage|disadvantage|stay hidden|still hidden|"
    r"remain hidden|stealth|dc|saving throw|save|spell slot|concentration|opportunity attack|movement|cover|"
    r"prone|surprised?|initiative|ability check|proficien\w*|rule)\b[^?]*\?")
_OBJECT_VERB = (r"toss\w*|throw\w*|threw|lob\w*|push\w*|shov\w*|pok\w*|prod\w*|knock\w*|drop\w*|"
                r"kick\w*|roll\w*|tap\w*|nudg\w*|flick\w*|slid\w*|set\w*|plac\w*|pour\w*")
_OBJECT_ACT_RE = _lazy.regex(
    r"(?i)\b(?:" + _OBJECT_VERB + r")\s+(?:a|an|the|my|his|her|some|one|that|this)\s+[\w-]+(?:\s+[\w-]+)?"
    r"\s+(?:into|onto|on|at|against|in|over|across|under|down|through|toward|towards)\s+(?:the|a|an|that|this)\b"
    r"|\b(?:knock\w*|tap\w*|pok\w*|prod\w*)\s+(?:on|at)\s+(?:the|a|an|that|this)\b"
    r"|\b(?:pok\w*|prod\w*|tap\w*|nudg\w*|push\w*|shov\w*)\s+(?:the|a|an|that|this)\s+[\w-]+(?:\s+[\w-]+)?"
    r"\s+with\s+(?:my|a|an|the|his|her)\b")
_HARM_RE = _lazy.regex(r"(?i)\b(?:attack\w*|hit\w*|stab\w*|slash\w*|shoot\w*|kill\w*|hurt\w*|strike\w*|"
                      r"smash\w* (?:him|her|them)|to (?:hit|hurt|kill|wound|knock (?:him|her|them) out))\b")


def object_act(action):
    """An object put to use at a place ("toss a stone into the thicket", "knock on the door"),
    with no harm meant to anyone. An attack needs a target creature and intent to harm."""
    text = _plain(action)
    return bool(_OBJECT_ACT_RE.search(text)) and not _HARM_RE.search(text)


def object_acts(action):
    """How many object interactions one line declares ("draw my dagger and kick the stool" is two)."""
    text = _plain(action)
    if _HARM_RE.search(text):
        return 0
    return len(_OBJECT_ACT_RE.findall(text)) + len(_lazy.regex(
        r"(?i)\b(?:draw|stow|sheathe|pick up|grab|open|close)\w*\s+(?:my|a|an|the)\b").findall(text))


def classify(action):
    """The move a message most plausibly is (the deterministic default; a host declaration wins)."""
    text = _read(action)
    if not text:
        return 'look'
    if _ASK_DM_RE.search(text) or _RULES_QUESTION_RE.search(text):
        return 'ask_dm'
    if _RECALL_RE.search(text):
        return 'recall'
    if _REST_RE.search(text):
        return 'rest'
    if object_act(text):
        return 'use'
    if _FIGHT_RE.search(text) or _HARM_RE.search(text):
        return 'fight'
    if _TALK_RE.search(text):
        return 'talk'
    if notice_intent(text):
        return 'look'
    # The skill the act calls for says what kind of move it is: reading or swaying a person is
    # talk; climbing, tumbling or sneaking is moving (runtime/kit_skills.py rows, not new words).
    from . import kit_skills
    skill = kit_skills.matched_skill(text)
    if skill in ('insight', 'persuasion', 'deception', 'intimidation'):
        return 'talk'
    if skill in ('athletics', 'acrobatics', 'stealth'):
        return 'move'
    if _MOVE_RE.search(text) or stance_of(text) in ('advance', 'withdraw') or re.search(r"(?i)\b(?:hide|hiding|sneak\w*|creep\w*|slip away)\b", text):
        return 'move'
    if _USE_RE.search(text):
        return 'use'
    return 'look'


def check_declared(declared, action):
    """Problems with a host-declared ``player_move`` (an empty list is clean)."""
    if declared is None:
        return []
    problems = []
    if not isinstance(declared, dict) or set(declared) - {'kind', 'target', 'stance'}:
        return ['player_move is {"kind", "target", "stance"}']
    if declared.get('kind') not in MOVES:
        problems.append('player_move.kind is one of: ' + ', '.join(MOVES))
    if 'stance' in declared and declared['stance'] not in STANCES:
        problems.append('player_move.stance is one of: ' + ', '.join(STANCES))
    said = stance_of(action)
    if declared.get('stance') == 'advance' and said == 'hold':
        problems.append('player_move.stance contradicts the player: he said the PC holds his position')
    # The costly misreads: starting a fight or a rest the player never asked for.
    if declared.get('kind') == 'fight' and not _FIGHT_RE.search(_plain(action)) and classify(action) != 'fight':
        problems.append('player_move.kind contradicts the player: he did not attack; never start a fight for him')
    if declared.get('kind') == 'rest' and not _REST_RE.search(_plain(action)):
        problems.append('player_move.kind contradicts the player: he did not ask to rest')
    if 'target' in declared and (not isinstance(declared['target'], str) or len(declared['target']) > 120):
        problems.append('player_move.target is a short name of what the move is aimed at')
    return problems


# -- the skill picker -----------------------------------------------------------------------

def pick_skill(action, kind=None, stated=None):
    """(skill, why) for an act. A stated skill with a reason wins; then the act's object."""
    from . import kit_skills
    if stated in SKILLS:
        return stated, 'stated'
    kind = kind or classify(action)
    if kind != 'recall' and notice_intent(action):
        return 'perception', 'looking for something that may be hidden is Perception'
    skill = kit_skills.skill_for_intent(_read(action))
    return skill, 'intent map'


_PUSHBACK_RE = _lazy.regex(
    r"(?i)\b(?:shouldn'?t|wouldn'?t|isn'?t|is|would|could|can) (?:th(?:is|at|e \w+)|it|i|we|"
    r"\w+ing(?: \w+){0,4}) (?:not )?(?:be |use |roll |make |go with |try )?(?:an? |more of an? |more )?"
    r"(?P<a>" + '|'.join(s.replace('_', ' ') for s in SKILLS) + r")\b"
    r"|\b(?:what about|how about|use|try|roll|make it|instead of \w+,?) (?:an? )?"
    r"(?P<b>" + '|'.join(s.replace('_', ' ') for s in SKILLS) + r")(?: instead| rather)?\b"
    r"|^\s*(?P<c>" + '|'.join(s.replace('_', ' ') for s in SKILLS) + r")\s*\?")


def pushback_skill(message, called=None):
    """The skill the player argues for instead of the one called, or None."""
    for hit in _PUSHBACK_RE.finditer(_plain(message)):
        name = (hit.group('a') or hit.group('b') or hit.group('c') or '').casefold().replace(' ', '_')
        if name in SKILLS and name != called:
            return name
    return None


# Which skills fit which kind of act. A pushback is accepted when it lands in the family.
_FAMILIES = (
    ('notice', ('perception',)),
    ('search', ('investigation', 'perception')),
    ('read_person', ('insight',)),
    ('knowledge', KNOWLEDGE_SKILLS),
)


def rule_pushback(called, requested, stored_action):
    """(skill, accepted, why): Kit weighs a skill pushback and makes the final call."""
    if requested not in SKILLS or requested == called:
        return called, False, 'no change'
    best, _why = pick_skill(stored_action)
    if requested == best:
        return requested, True, 'the act fits %s' % requested.replace('_', ' ').title()
    if notice_intent(stored_action) and requested == 'perception':
        return requested, True, 'looking for something hidden is Perception'
    if _SEARCH_OBJECT_RE.search(_plain(stored_action)) and requested in ('investigation', 'perception'):
        return requested, True, 'a hands-on search can be Investigation or Perception'
    if notice_intent(stored_action) and called == 'perception':
        return called, False, 'looking for something that may be hidden'
    return called, False, ''



def passive_reveals(passive, hidden_number):
    """A passive score that meets the hidden number reveals without a roll."""
    return passive is not None and hidden_number is not None and int(passive) >= int(hidden_number)


def notice_total(total, passive):
    """An active look never comes out below what the character notices passively."""
    if passive is None:
        return total
    return max(int(total), int(passive))


def known_stealth(stat_block):
    """The Stealth bonus a stat block actually gives, or None when it is unknown.

    A listed Stealth wins; an SRD line with none listed uses its Dexterity modifier (the
    engine's ``initiative``), which is what an unlisted skill is. An inline block from a book
    that states no Stealth is unknown: a roll decides, never an assumed number."""
    from . import srd_creatures
    if not isinstance(stat_block, dict):
        return None
    if type(stat_block.get('stealth')) is int:
        return stat_block['stealth']
    skills = stat_block.get('skills') or {}
    if type(skills.get('stealth')) is int:
        return skills['stealth']
    if 'srd' in stat_block:
        found = srd_creatures.CREATURES.get(str(stat_block['srd']).strip().casefold()) or {}
        if type(found.get('stealth')) is int:
            return found['stealth']
        if type(found.get('initiative')) is int:
            return found['initiative']
    return None


# -- the open ask ---------------------------------------------------------------------------

def open_ask(kind, subject, player_words='', skill=None, stakes=None, waits='player', why=None):
    """One record of what Kit asked for and why."""
    assert kind in OPEN_ASK_KINDS, kind
    record = {'kind': kind, 'subject': str(subject or '')[:300], 'player_words': str(player_words or '')[:600],
              'waits': waits}
    if skill:
        record['skill'] = skill
    if stakes:
        record['stakes'] = str(stakes)[:200]
    if why:
        record['why'] = str(why)[:200]
    return record


def open_ask_from_state(state):
    """The one open ask in a save, whatever path stored it, or None."""
    state = state or {}
    pending = state.get('pending_check') or {}
    if pending.get('skill'):
        stored = pending.get('open_ask') or {}
        return {**open_ask('roll', stored.get('subject') or pending.get('action') or pending.get('target') or '',
                           stored.get('player_words') or pending.get('action') or '', skill=pending['skill'],
                           why=stored.get('why') or pending.get('reason')),
                'from': 'pending_check'}
    combat = state.get('combat') or {}
    if combat.get('status') == 'awaiting_initiative':
        return {**open_ask('initiative', 'the fight that is starting'), 'from': 'combat'}
    waiting = combat.get('awaiting') or {}
    if waiting:
        kind = {'roll_call': 'save', 'reaction_window': 'choice', 'flourish_window': 'choice',
                'kit_call': 'roll'}.get(waiting.get('kind'), 'choice')
        if waiting.get('awaits') == 'attack_roll':
            kind = 'attack'
        elif waiting.get('awaits') == 'damage_roll':
            kind = 'damage'
        return {**open_ask(kind, waiting.get('trigger') or waiting.get('kind') or ''), 'from': 'combat'}
    return None


_NUMBER_RE = _lazy.regex(r"(?<![\w.])(\d{1,2})(?!\w|\.\d)")


def answer_of(message, ask):
    """What a message gives an open ask: the total, a skill pushback, and whether it also asks."""
    text = _plain(message)
    numbers = [int(n) for n in _NUMBER_RE.findall(re.sub(r"(?i)\b\d+\s*(?:feet|ft|yards|gp|sp|cp)\b", ' ', text))]
    return {
        'total': numbers[-1] if numbers else None,
        'pushback': pushback_skill(text, (ask or {}).get('skill')),
        'asks': '?' in text,
    }


# -- the speaking contract ------------------------------------------------------------------

_SKILL_WORDS = '|'.join(s.replace('_', ' ') for s in SKILLS)
MECHANIC_WORDS = frozenset(
    ('roll', 'rolls', 'initiative', 'check', 'save', 'saving', 'throw', 'advantage', 'disadvantage',
     'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma', 'str', 'dex', 'con',
     'int', 'wis', 'cha', 'short', 'long', 'rest', 'attack', 'damage', 'hit', 'points', 'concentration',
     'blinded', 'charmed', 'deafened', 'frightened', 'grappled', 'incapacitated', 'invisible',
     'paralyzed', 'petrified', 'poisoned', 'prone', 'restrained', 'stunned', 'unconscious', 'exhaustion',
     'passive', 'me', 'your', 'a', 'an', 'the', 'for', 'it', 'sleight', 'of', 'hand', 'animal', 'handling') +
    tuple(w for s in SKILLS for w in s.split('_')))


def is_mechanic_run(name):
    """'Roll History', 'Roll Initiative', 'Dexterity Saving Throw': rules words, not a person."""
    words = re.findall(r"[A-Za-z']+", name or '')
    return bool(words) and all(w.casefold() in MECHANIC_WORDS for w in words)


_BARE_RESULT = _lazy.regex(
    r"(?i)^\s*(?:you (?:roll(?:ed)?|got|have)\s+)?(?:a |an )?(?:(?:" + _SKILL_WORDS + r"|initiative|"
    r"attack|damage|(?:\w+ )?save|saving throw|check)\b\s*[:=]?\s*)?\d{1,3}\s*[.!]?\s*$"
    r"|^\s*(?:you roll|rolled)\s+(?:" + _SKILL_WORDS + r"|initiative|attack|damage)\s*[:=]?\s*\d{1,3}\s*[.!]?\s*$"
    r"|^\s*(?:initiative|ac|hp|dc)\s*[:=]\s*\d{1,3}\s*[.!]?\s*$")
INTERNAL_LABEL = _lazy.regex(
    r"(?i)\btable talk(?: to kit)?\s*:|\b(?:public_event|turn_id|pending_check|open_ask|host_facts|player_move|"
    r"observed_event|public_brief|spoiler_fence|kit_choice|improv_read|accepted_public_event|"
    r"knowledge_answer|check_outcome|deferred_action_id)\b|[{}]|\bplayer (?:declared|bid)\s*:")
_MOVES_PC = _lazy.regex(
    r"(?i)\byou (?:go ahead|go forward|move (?:up|forward|closer|in|ahead)|step (?:forward|closer|up|out)|"
    r"approach\w*|walk (?:up|forward|over|closer|toward\w*)|advance\w*|head (?:over|toward\w*|up|in)|"
    r"close the distance|creep (?:closer|forward|up)|edge (?:closer|forward)|make your way (?:to|toward|over|forward))\b")
_ROLL_CALL = _lazy.regex(r"(?i)\broll(?: me)?(?: an?| your)? (" + _SKILL_WORDS + r"|initiative)\b")
_CLARIFY_Q = re.compile(
    r"(?i)(?:^|(?<=[.!?]\s))(?:which|what|where|who|how|left or right|feet or|[^.?!]{0,60}\bor\b[^.?!]{0,60})"
    r"[^.?!]*\?")


def _sentences(text):
    return [s for s in re.split(r'(?<=[.!?])\s+', (text or '').strip()) if s.strip()]


def _body(text):
    """The spoken words without speaker prefixes ("Kit: ", "Narrator: ")."""
    return re.sub(r'(?m)^\s*[A-Z][\w .\'-]{0,40}:\s*', '', text or '').strip()


def bare_result(text):
    """True when the whole reply is a number or a roll result with nothing after it."""
    body = _body(text)
    lines = [line for line in body.splitlines() if line.strip()]
    return bool(lines) and all(_BARE_RESULT.match(line) for line in lines)


# Host tools and engine files are the host's business: their names never reach the player
# ("roll it and tell me the total", not "roll it in <dice bot>").
HOST_TOOL = _lazy.regex(
    r"(?i)\bavrae(?:'s)?\b|\bkit[._](?:sqlite|agent|prep|moves|perform)\w*|\b[\w-]+\.(?:sqlite|json|py|txt)\b|"
    r"\b(?:validator|turn record)\b")
_HOST_TOOL_PHRASES = (
    (r"\s*\((?:with )?the avrae roll if you have it\)", ''),
    (r"\s+(?:in|from|with|on|via|using)\s+avrae\b", ''),
    (r"\b(?:the|its|your)\s+avrae\s+", lambda m: m.group(0).split()[0] + ' '),
    (r"\bavrae's\b", 'your'),
    (r"\bavrae\b", 'your dice'),
)


def internal_label(text):
    """The first internal label, field name or host-tool name in a reply, or None."""
    body = _body(text)
    found = INTERNAL_LABEL.search(body) or HOST_TOOL.search(body)
    return found.group(0) if found else None


def player_safe(text):
    """Player-facing engine text with any host-tool name taken out (refusals, asks)."""
    out = str(text or '')
    for pattern, repl in _HOST_TOOL_PHRASES:
        out = re.sub('(?i)' + pattern, repl, out)
    return re.sub(r'  +', ' ', out)


def shape_problems(text, player_action='', ask=None, call=False):
    """A question the same reply already answers, a roll asked for again, a choice re-asked."""
    problems = []
    body = _body(text)
    given = answer_of(player_action, ask)
    if given['total'] is not None and ask and ask.get('skill'):
        asked = _ROLL_CALL.search(body)
        if asked and asked.group(1).casefold().replace(' ', '_') == ask['skill']:
            problems.append('Fix: the player already gave the %s roll. Resolve it; do not ask for it again.'
                            % ask['skill'].replace('_', ' ').title())
    sentences = _sentences(body)
    if not call:
        for i, sentence in enumerate(sentences[:-1]):
            if not _CLARIFY_Q.search(sentence):
                continue
            later = ' '.join(sentences[i + 1:])
            if re.search(r'(?i)\byou (?:see|spot|find|notice|hear|make out|catch|learn|recall|remember)\b', later):
                problems.append('Fix: ask or resolve, not both. Drop the question this reply already answers.')
                break
    words = set(re.findall(r"[a-z']+", _plain(player_action).casefold()))
    for sentence in sentences:
        for left, right in re.findall(r"(?i)\b(\w+) or (?:the )?(\w+)\?", sentence):
            said = left if left.casefold() in words else right if right.casefold() in words else None
            if said:
                problems.append('Fix: the player already said which (%s). Do not ask him to choose again.' % said)
                break
    return problems


def stance_problems(text, player_action='', stance=None):
    """Narration that moves the PC against the position the player said he holds."""
    stance = stance or stance_of(player_action)
    if stance == 'hold' and _MOVES_PC.search(_body(text)):
        return ['Fix: the player said his character holds his position. Do not narrate him moving forward.']
    return []


def speaking_problems(text, player_action='', ask=None, stance=None, call=False):
    """Every speaking-contract problem in a whole reply (speaker prefixes allowed)."""
    if not _body(text):
        return ['Fix: say what happens, then hand the turn back. The reply was empty.']
    problems = []
    if bare_result(text):
        problems.append('Fix: a bare number or roll result is not a reply. Say what the roll means in the scene, '
                        'then hand the turn back.')
    if internal_label(text):
        problems.append('Fix: no internal labels, field names, host-tool names (%s) or turn records in speech. '
                        'Say it in the scene.' % internal_label(text))
    problems += stance_problems(text, player_action, stance)
    problems += shape_problems(text, player_action, ask, call)
    return list(dict.fromkeys(problems))


def _joined(segments):
    return '\n'.join('%s: %s' % (s.get('speaker', ''), s.get('text', '')) for s in segments or ())


def check_turn_shape(segments, player_action, ask=None, call=False):
    """HARD (style): no question the reply already answers, no roll asked for twice."""
    problems = shape_problems(_joined(segments), player_action, ask, call)
    if problems:
        raise InvalidChange(' '.join(problems))


def check_stance(segments, player_action, stance=None):
    """HARD (agency): the narration never moves the PC against what the player said."""
    problems = stance_problems(_joined(segments), player_action, stance)
    if problems:
        raise InvalidChange(' '.join(problems))

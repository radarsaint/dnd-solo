"""Physical actions and a minimal fight for a room (area 6c first).

The 6c baseline (2026-10-03) read attacks, grabs, a table flip, a coin grab, and a paint
wipe as plain talk or "You take a look." The rule here is general, not per verb: an act
of the body on a creature or a thing in the room changes the world, and the change is
persisted before Kit writes a word.

    parse()          what the player physically does: attack (weapon, unarmed, or spell),
                     grab, touch a face, flip/overturn a thing, take loose valuables
    Fight            resolves it: the world change (``scene_state``), the fight
                     (``combat_state``), actor statuses (``actor_status``), and reveals

A fight, at a play-by-post table with Avrae (Brendon: Avrae is at every game):

* Surprise first. Usually no one is surprised: the PC walked in openly. Only a PC hidden
  from everyone when the fight starts surprises them.
* The PC's initiative is the total the player reports from Avrae; Kit never rolls for the
  player. NPC initiative is their flat 10 + Dexterity (NPCs never roll a contest).
* A blow declared before initiative resolves as the PC's first action; it is never voided.
  An attack without a stated total waits for it ("Roll the attack").
* NPC turns run in order between the PC's turns: retreat first if the room's rule says so,
  else attack the PC with Kit's private, seeded d20 against the PC's AC.
* The vampire act holds until ordinary physical fact cracks it (a wound, burned paint, a
  wiped face, fitted fangs seen up close, a man grovelling for copper); then the hidden
  fact is revealed and stays revealed.
* Public text never shows AC, hit points, DCs, or roll totals (call 4). The damage a PC
  takes is told as a number, because the player applies it in Avrae.

Deterministic Python; no model calls, no dice for the player.
"""
import copy
import hashlib
import re

from . import kit_reactions
from . import kit_rolls
from .state_context import require

QUOTED = re.compile(r'"[^"]*"')
SPEECH_SINGLE = re.compile(r"(?:(?<=^)|(?<=[\s(\[:;,.!?\u2014-]))'(?=\S)[^\n]*?(?<=\S)'(?=$|[\s)\].,!?;:\u2014-])")

WEAPONS = (r'greataxe|axe|handaxe|greatsword|longsword|shortsword|sword|rapier|scimitar|dagger|knife|blade|'
           r'mace|maul|warhammer|hammer|club|quarterstaff|staff|spear|javelin|pike|halberd|glaive|whip|flail|'
           r'crossbow|longbow|shortbow|bow|arrow|bolt|sling|fist|fists|elbow|knee|boot|foot|heel|shield')
ATTACK_VERBS = (r'attack|attacks|attacking|swing|swings|swinging|slash|slashes|stab|stabs|strike|strikes|hit|hits|'
                r'punch|punches|kick|kicks|shoot|shoots|fire at|thrust|thrusts|lunge|lunges|cleave|cleaves|cut|'
                r'chop|chops|smash|smashes|stomp|stomps|headbutt|run (?:him|her|it|them) through|'
                r'put (?:my|the) (?:' + WEAPONS + r') (?:through|into)|bury (?:my|the) (?:' + WEAPONS + r') in|'
                r'drive (?:my|the) (?:' + WEAPONS + r') (?:through|into)|bash|bashes|throw (?:my|a|the) (?:dagger|knife|'
                r'javelin|axe|handaxe|spear) at|kill|murder|bite')
ATTACK = re.compile(r'\b(' + ATTACK_VERBS + r')\b')
# Spells: the attack-roll ones, the saving-throw ones (ability, half on a save?), and the
# ones that always hit. Area spells catch everyone at the table.
SPELL_ATTACK = ('fire bolt', 'ray of frost', 'eldritch blast', 'chill touch', 'shocking grasp', 'chromatic orb',
                'scorching ray', 'guiding bolt', 'witch bolt', 'inflict wounds', 'produce flame', 'thorn whip')
SPELL_SAVE = {'fireball': ('dex', True, True), 'burning hands': ('dex', True, True),
              'lightning bolt': ('dex', True, True), 'thunderwave': ('con', True, True),
              'shatter': ('con', True, True), "dragon's breath": ('dex', True, True),
              'toll the dead': ('wis', False, False), 'mind sliver': ('int', False, False),
              'sacred flame': ('dex', False, False), 'vicious mockery': ('wis', False, False),
              'poison spray': ('con', False, False), 'mind spike': ('wis', True, False)}
SPELL_AUTO = ('magic missile',)
SPELLS = tuple(SPELL_ATTACK) + tuple(SPELL_SAVE) + SPELL_AUTO
_SPELL = re.compile(r"\b(" + '|'.join(re.escape(s) for s in sorted(SPELLS, key=len, reverse=True)) + r")\b")
GRAB = re.compile(r'\b(grab|grabs|grabbing|seize|seizes|grip|grips|grapple|grapples|collar|collars|haul|hauls|'
                  r'yank|yanks|pin|pins|tackle|tackles|shove|shoves|push|pushes|drag|drags|catch|catches|clamp)\b')
FACE = re.compile(r'\b(wipe|wipes|wiping|smear|smears|rub|rubs|scrub|scrubs|lick (?:my|a) thumb|swipe|swipes|'
                  r'pull|pulls|tug|tugs|pluck|plucks|pry|touch|touches|flick|flicks)\b')
FACE_PARTS = re.compile(r"\b(cheek|cheeks|face|faces|paint|makeup|make-up|powder|greasepaint|flour|fangs?|teeth|"
                        r"tooth|forehead|jaw|chin|lips?|skin)\b")
TEETH = re.compile(r'\b(teeth|tooth|fangs?|mouth|gums?)\b')
FLIP = re.compile(r'\b(flip|flips|flipping|overturn|overturns|upend|upends|heave|heaves|tip|tips|kick over|'
                  r'knock over|knocks over|throw over|turn over|shove over|topple|topples)\b')
TABLE = re.compile(r'\b(table|card table)\b')
TAKE = re.compile(r'\b(scoop|scoops|scooping|grab|grabs|snatch|snatches|pocket|pockets|pocketing|take|takes|'
                  r'swipe|swipes|pick up|picks up|gather|gathers|sweep|sweeps|lift|lifts|palm|palms|steal|steals|'
                  r'help myself to)\b')
VALUABLES = re.compile(r'\b(coins?|gold|silver|copper|pot|money|stacks?|the stakes|winnings|ring|silver ring|purse)\b')
COVERT = re.compile(r"\b(quietly|unnoticed|unseen|without (?:anyone|them) (?:seeing|noticing)|slip|slips|palm|palms|"
                    r"secretly|covertly|furtively|stealthily|on the sly|discreetly|"
                    # a covert clause: while or when nobody watches, or the others look away
                    r"(?:while|when|as)\s+(?:no ?one|no-one|nobody|they|the others|everyone(?: else)?|he|she|their "
                    r"(?:backs?|eyes?))(?:'s|'re|\s+(?:is|are|was|were))?\s+(?:not\s+)?(?:looking|watching|distracted|busy|"
                    r"turned|elsewhere|looking away|looks away|look away))\b")
# Shield typed on his own turn, or after its window passed: a reaction spell with no trigger now.
OWN_SHIELD = re.compile(r"!cast\s+shield\b|\bshield\s+(?:myself|me)\b|\b(?:cast|casts|casting|raise|raises|throw up|throws up)\s+(?:a\s+|my\s+)?shield\b"
                        r"(?!\s+(?:bash|slam))")
# Combat movement away from his foes ('I step back 30 feet', 'I fall back', 'I disengage').
WITHDRAW = re.compile(r"\b(?:disengage|disengages|disengaging)\b|\b(?:step|steps|stepping|back|backs|backing|move|moves|"
                      r"moving|fall|falls|falling|retreat|retreats|retreating|withdraw|withdraws|run|runs|running|"
                      r"dash|dashes|dashing|hop|hops|scramble|scrambles)\b[^.!?]{0,40}?\b(?:away|back|off|clear|"
                      r"out of (?:his |its |her |their )?reach|\d+\s*(?:feet|foot|ft))\b")
WAIT = re.compile(r'\b(wait|waits|ready|readied|hold my action|hold (?:my )?ground|let them come|'
                  r'make the first move|stand my ground|on guard)\b')
EVERYONE = re.compile(r'\b(middle of the (?:card )?table|the (?:card )?table|all of them|them all|everyone|'
                      r'the lot of them|the four|the whole table|the group)\b')
ANY_STANDING = re.compile(r"\b(whoever(?:'s| is)? (?:still )?(?:standing|left|up)|anyone (?:still )?standing|"
                          r"the (?:last|nearest|closest) one|whoever)\b")
NEAREST = re.compile(r'\b(nearest|closest|first)\b')
PRONOUN = re.compile(r'\b(him|her|his|it|its|them|their|he|she|one of them|the pale one|that one)\b')
OBJECTS = re.compile(r'\b(door|wall|floor|tub|carving|fresco|deck|cards|chair|ceiling|lock)\b')
# The PC's own things and body: "my face", "out of my purse" are not acts on the room.
OWN = re.compile(r'\b(my|our)\s+(?:own\s+)?(?:\w+\s+)?(face|cheeks?|fangs?|teeth|lips?|skin|coins?|gold|silver|purse|'
                 r'pouch|money|ring|stake|stack|winnings)\b|\b(?:out of|from) my\b')
GAZE = re.compile(r'\b(eye|eyes|gaze|look|attention|breath|drift|meaning|light)\b')
NONLETHAL = re.compile(r'\b(knock (?:him|her|them|it) out|non-?lethal|pull (?:my|the) punch|to subdue)\b')

ACTIVE_STATUSES = ('alive',)


# -- checkpoints (PR-H): the engine stops where the player owns the next input -----------
# Brendon's 691e834 harness: Nik (AC 14, Shield, slots) took 38 and dropped without being
# offered Shield; a kill went straight on into enemy turns and flight. A checkpoint is
# deterministic: the fight state records what waits (``awaiting``), the turn commits, and
# the player's answer resumes it exactly where it stopped. It only stops when the player
# owns something there; otherwise the round runs on as before.
class Checkpoint(Exception):
    """The fight stops here; ``fight['awaiting']`` says for what."""


class Unclear(Exception):
    """The answer to a checkpoint does not settle it; nothing is committed. ``code`` says why:
    unclear (Kit could not read it), not_offered, not_available, needs_cast (a reaction spell is cast
    in Avrae first), needs_roll (an attack waits on its roll), ranged_weapon (no opportunity attack
    with a ranged weapon), needs_save (the roll call's save)."""
    def __init__(self, message, code='unclear', ask=None):
        super().__init__(message)
        self.code = code
        self.ask = ask


class NeedsChoice(Exception):
    """A reaction or flourish window is open and the reply has no structured choice yet: Kit reads
    it (``react: <id>|decline|unclear``, ``flourish: describe|new_action|unclear``). The engine never
    reads the player's words for intent."""
    def __init__(self, waiting):
        super().__init__(waiting.get('kind'))
        self.waiting = waiting


ELEMENTS = kit_reactions.ELEMENTS
RANGED = re.compile(r'\b(bow|crossbow|longbow|shortbow|sling|dart|javelin|ray|bolt|blowgun|net)\b')
# Window event families: a declined window is not offered again for the same family that round,
# unless the stakes change (the hit would now drop the PC).
FAMILIES = ('hit', 'leaves_reach', 'npc_save', 'npc_spell')


# -- what a verb acts on (general guards; no room names) ---------------------------------
# A physical act needs its noun as the verb's own object: "takes the chair and sets a copper
# on the table" takes a chair; "flicks his ears ... eyes on the dealer's face" touches no face.
CLAUSE_BREAK = re.compile(r"[,.;:!?]|\b(?:and|then|while|but|as|before|after|so)\b")
# "into his pocket": a TAKE word after a possessive or article is a noun, not the verb.
NOUN_USE = re.compile(r"\b(?:my|our|his|her|their|its|your|a|an|the)\s+(?:\w+\s+)?$")
POSSESSIVE = re.compile(r"\b(my|our|his|her|their)\s+(?:own\s+)?(?:\w+\s+)?$")
CARRIED_OR_BODY = re.compile(r"(?:pocket|pouch|purse|belt|pack|bag|sheath|sleeve|coat|cloak|lap|ears?|face|"
                             r"cheeks?|brow|forehead|hands?|lips?|teeth|skin|chin|jaw)\b")
ACTOR_WORDS = re.compile(r"\b(dealer|player|players|man|woman|men|women|vampire|vampires|bandit|bandits|thug|"
                         r"thugs|guard|guards|stranger|captain|he|she|they|him|them)\b")


# -- what an attack verb is aimed at (general; no room names) ---------------------------
# A violent verb is an attack only when it is aimed at someone: its own object is a creature,
# a person, or a named actor ("shoot the dealer", "kick him"), it is aimed through a
# preposition ("fire at the man"), or it uses a weapon ("thrust my dagger at him"). Its object
# being anything else is an idiom or a gesture, never a strike: "shoot the breeze", "kill
# time", "thrust my chin at the dealer", "kick back", "kick my feet up".
_SKIP = re.compile(r"(?:the|a|an|this|that|these|those|some|\w+ly|right|straight|all)$")
_OWNERS = ('my', 'our', 'his', 'her', 'their', 'its', 'your')
_AIM_PREPOSITIONS = ('at', 'on', 'into', 'through', 'against', 'toward', 'towards', 'upon')
CREATURE_WORDS = re.compile(r"(?:dealer|player|players|man|woman|men|women|vampires?|bandits?|thugs?|guards?|"
                            r"stranger|captain|creature|monster|doppelganger|guy|bastard|one|someone|anyone|"
                            r"everyone|whoever|him|her|them|it|me|you)s?$")
# Someone else's body part is a target ("his throat"); a bare one is not ("kick back").
BODY_WORDS = re.compile(r"(?:throat|neck|chest|gut|head|face|arm|wrist|hand|leg|back|shoulder|heart|eye|side|"
                        r"ribs?|kneecap|jaw|nose|belly|knee)s?$")


def aimed_attack(text, verb, actor_names=()):
    """True when the attack verb match ``verb`` in ``text`` is aimed at someone (see above)."""
    rest = text[verb.end():]
    cut = CLAUSE_BREAK.search(rest)
    clause = rest[:cut.start()] if cut else rest
    words = re.findall(r"[a-z][a-z'-]*", clause)
    if not words:
        return True  # "I attack!", "I shoot." : the fight path asks who
    owner = None
    for index, word in enumerate(words):
        if word in _AIM_PREPOSITIONS or word == 'with':
            return True  # aimed through a preposition, or a weapon named for the blow
        if word in _OWNERS:
            owner = word
            continue
        if _SKIP.match(word):
            continue
        if word.endswith("'s") and (CREATURE_WORDS.match(word[:-2]) or word[:-2] in actor_names):
            return True  # "the dealer's hand"
        noun = ' '.join(words[index:index + 2])
        if re.match(r'(?:' + WEAPONS + r')s?$', word):
            return True  # "thrust my dagger", "kick my boot into him"
        if owner in ('my', 'our'):
            return False  # the PC's own body or things: a gesture ("thrust my chin")
        if CREATURE_WORDS.match(word) or any(noun.startswith(name) or word == name for name in actor_names):
            return True
        if BODY_WORDS.match(word):
            return owner is not None  # "his throat", "the dealer's hand" (owner word before it)
        return False  # an object or a figure of speech: "shoot the breeze", "kill time"
    return owner not in ('my', 'our')


def first_aimed_attack(text, actor_names=()):
    """The first ATTACK verb in ``text`` that is aimed at someone, or None."""
    for verb in ATTACK.finditer(text):
        if NOUN_USE.search(text[:verb.start()]):
            continue  # "a kick", "the cut": a noun, not the act
        if aimed_attack(text, verb, actor_names):
            return verb
    return None


def pc_names(state):
    """Lowercase name words of the player character (from the loaded sheet), for third-person
    narration: "Mira slides the copper back into her pocket"."""
    name = ((state or {}).get('player_sheet') or {}).get('name') or ''
    return tuple(word for word in re.findall(r"[a-z][a-z'-]+", name.casefold()) if len(word) > 1)


def object_of(text, verb, pattern, words=5):
    """The first match of ``pattern`` in the verb's own object: after the verb, within
    ``words`` words, and before the clause ends. Offsets are in ``text``."""
    rest = text[verb.end():]
    cut = CLAUSE_BREAK.search(rest)
    rest = rest[:cut.start()] if cut else rest
    span = re.match(r"\s*(?:\S+\s*){0,%d}" % words, rest).group(0)
    found = pattern.search(span)
    if not found:
        return None
    return re.compile(re.escape(found.group(0))).search(text, verb.end() + found.start())


def is_own(text, noun_start, pcs=()):
    """True when the noun at ``noun_start`` is the PC's own: "my coin", "Mira's ring", or
    "his pocket" in third-person narration where the nearest actor before it is the PC."""
    before = text[:noun_start]
    if OWN.search(text[max(0, noun_start - 25):noun_start + 20]):
        return True
    if any(re.search(r"\b%s's\s+(?:own\s+)?(?:\w+\s+)?$" % re.escape(name), before) for name in pcs):
        return True
    owner = POSSESSIVE.search(before)
    if not owner or owner.group(1) in ('my', 'our') or not pcs:
        return bool(owner and owner.group(1) in ('my', 'our'))
    # "his gold" may be anyone's; "his pocket", "his face" in the PC's own sentence are the PC's.
    if not CARRIED_OR_BODY.match(text[noun_start:]):
        return False
    head = before[:owner.start()]
    pc_at = max((m.end() for name in pcs for m in re.finditer(r"\b%s\b" % re.escape(name), head)), default=-1)
    actor_at = max((m.end() for m in ACTOR_WORDS.finditer(head) if m.group(1) not in ('he', 'she', 'they')),
                   default=-1)
    return pc_at > actor_at


def taken_valuables(text, pcs=()):
    """(verb match, loot match) when the PC takes valuables that are not their own, else
    (None, None). Each TAKE verb is tried; a noun use ("into his pocket") is skipped."""
    for verb in TAKE.finditer(text):
        if NOUN_USE.search(text[:verb.start()]):
            continue
        loot = object_of(text, verb, VALUABLES)
        if loot and POSSESSIVE.search(text[:loot.start()]) and re.match(r"\s*back\b", text[loot.end():]):
            continue  # "takes her gold back": reclaiming their own stake
        if loot and not is_own(text, loot.start(), pcs) and \
                not OWN.search(text[max(0, loot.start() - 25):loot.end() + 16]):
            return verb, loot
    return None, None


def touched_face(text, pcs=()):
    """True when a hand-contact verb has someone else's face (or its paint) as its object."""
    for verb in FACE.finditer(text):
        part = object_of(text, verb, FACE_PARTS, words=7)
        if part and not is_own(text, part.start(), pcs):
            return True
    return False


def narration(action):
    """The action without its quoted speech (double or single quotes): only what the PC
    does with their body decides a physical act."""
    text = (action or '').translate(str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"'}))
    text = QUOTED.sub(' ', text)
    return SPEECH_SINGLE.sub(' ', text)


def config(source):
    """The room's combat block, plus every actor whose ``stat_block`` (inline or an SRD
    reference, runtime/srd_creatures.py) makes them a fighter. A room with fighters and no
    combat block can still fight on-engine (watchroom playtest)."""
    from . import srd_creatures
    block = (source or {}).get('combat') or {}
    known = block.get('actors') or {}
    statted = {key: srd_creatures.stat_block(actor.get('stat_block'))
               for key, actor in ((source or {}).get('actors') or {}).items()
               if isinstance(actor, dict) and actor.get('stat_block') and key not in known}
    statted = {key: stats for key, stats in statted.items() if stats}
    if not statted:
        return block
    return {**block, 'actors': {**known, **statted}}


def initial_scene():
    return {'table': 'upright', 'pot': 'on_table', 'ring': 'on_table', 'pc_took': [], 'grappled': None,
            'grovelling': None, 'provocations': 0, 'act': 'holding', 'cracked_by': None}


def scene(state):
    return copy.deepcopy(state.get('scene') or initial_scene())


def fight(state):
    return copy.deepcopy(state.get('combat'))


def check_scene(body):
    require(isinstance(body, dict) and body.get('table') in ('upright', 'overturned') and
            body.get('act') in ('holding', 'cracked') and isinstance(body.get('pc_took'), list) and
            len(body['pc_took']) <= 12, 'Scene state needs table, act, and what the PC took')


def check_fight(body):
    require(isinstance(body, dict) and body.get('status') in ('awaiting_initiative', 'running', 'over') and
            isinstance(body.get('hp'), dict) and isinstance(body.get('order'), list),
            'Combat state needs a status, hit points, and an order')


def present(source, state):
    """Actor ids in this area who can still act (not fled, down, or dead)."""
    return [key for key, actor in (state.get('actors') or {}).items()
            if actor.get('location') == state.get('area') and actor.get('status') in ACTIVE_STATUSES]


def labels(source):
    from .kit_agent import actor_speakers  # local: kit_agent imports this module
    return actor_speakers(source)


def _names(source, key):
    actor = (source.get('actors') or {}).get(key) or {}
    label = labels(source).get(key, key).casefold()
    names = {label, label.replace('-', ' '), (actor.get('name') or '').casefold()}
    first = label.split()[0] if label else ''
    if first and first not in ('the', 'pale'):
        names.add(first)  # "dealer", "door-side", "fresco-side", "fourth"
    last = label.split()[-1] if label else ''
    if last and all((labels(source).get(other, other).casefold().split() or [''])[-1] != last
                    for other in (source.get('actors') or {}) if other != key):
        names.add(last)  # the head noun when only this actor has it: "watch warden" -> "warden"
    palette = (((source.get('texture_palette') or {}).get('areas') or {}).get(actor.get('location') or '', {})
               .get('subjects', {}).get(f'actor:{key}')) or ()
    names |= {n.casefold() for n in palette}
    return {n for n in names if n and n not in ('pale man',)}


def name_target(text, source, state, candidates):
    """The actor the words name, among ``candidates``, or None."""
    best = None
    for key in candidates:
        for name in _names(source, key):
            found = re.search(rf"\b{re.escape(name)}\b", text)
            if found and (best is None or found.start() < best[1]):
                best = (key, found.start())
    return best[0] if best else None


def _creature_words(text):
    return bool(PRONOUN.search(text) or re.search(r"\b(dealer|player|players|man|woman|one|vampire|vampires|"
                                                  r"bandit|thug|guy|bastard|throat|collar|wrist|arm|hand|hands|"
                                                  r"neck|shoulder|head|chest|gut)\b", text))


_CLAUSE_OPEN = re.compile(r"[.;!?]\s*|,?\s+(?:and\s+)?then\b\s*|,?\s+and\b\s*", re.I)
_CLAUSE_CLOSE = re.compile(r"[.;!?]|,|\s+(?:and\s+)?then\b|\s+and\b", re.I)


def cast_level(text):
    """The slot level the player's Avrae cast used: '!cast absorb elements -l 2', 'at 2nd level',
    'level 2 slot'; None when the message does not say."""
    found = re.search(r"!cast\b[^\n)]*?\s-l\s*(\d)|\bat\s+(\d)(?:st|nd|rd|th)[- ]level\b|\b(?:level|lvl)\s+(\d)\s+slot\b|"
                      r"\b(\d)(?:st|nd|rd|th)[- ]level\s+slot\b", text or '', re.I)
    return int(next(g for g in found.groups() if g)) if found else None


def split_clause(action, names):
    """(the clause naming the reaction, the rest of the message)."""
    found = None
    for n in names:
        found = re.search(r'\b' + re.escape(n) + r'\b', action, re.I)
        if found:
            break
    if not found:
        return action, ''
    # An Avrae aside ('(Avrae: !cast absorb elements -l 2)') and its '!' belong to the clause.
    masked = re.sub(r'\([^)]*\)', lambda m: '_' * len(m.group(0)), action)
    masked = re.sub(r'!(?=\w)', '_', masked)
    start = 0
    for m in _CLAUSE_OPEN.finditer(masked, 0, found.start()):
        start = m.end()
    close = _CLAUSE_CLOSE.search(masked, found.end())
    end = close.end() if close else len(action)
    return action[start:end], (action[:start] + ' ' + action[end:]).strip(' ,;')


def late_reaction(text, source, state, here):
    """'I Uncanny Dodge that hit', 'Hellish Rebuke on the imp': a reaction the last foes' turns
    made legal without a prompt, named by the player."""
    events = (state.get('combat') or {}).get('unprompted') or ()
    resources = state.get('pc_resources') or {}
    aimed = re.search(r"\s-t\s+([a-z][\w'-]*)", text)
    named = (name_target(aimed.group(1), source, state, here) if aimed else None) or \
        name_target(text, source, state, here)
    for event in sorted(events, key=lambda e: e.get('attacker') != named):
        for key in event['options']:
            found = kit_reactions.entry(resources, key) or {}
            names = {found.get('name', '').casefold(), key.replace('_', ' ')} - {''}
            if any(re.search(r'\b' + re.escape(n) + r'\b', text) for n in names):
                return {'kind': 'late_reaction', 'target': event.get('attacker'), 'react': key, 'event': event,
                        'names': sorted(names, key=len, reverse=True),
                        'avrae': bool(re.search(r'!cast|\bcasts\b', text))}
    for found in resources.get('reactions') or ():
        if found['id'] in ('shield', 'opportunity_attack'):
            continue  # Shield on his turn is own_shield; an opportunity attack is just an attack
        names = {found.get('name', '').casefold(), found['id'].replace('_', ' ')} - {''}
        if any(re.search(r'\b' + re.escape(n) + r'\b', text) for n in names):
            return {'kind': 'late_reaction', 'target': None, 'react': found['id'], 'event': None,
                    'names': sorted(names, key=len, reverse=True),
                    'avrae': bool(re.search(r'!cast|\bcasts\b', text))}
    return None


def parse(action, source, state):
    """The player's act: one clause (parse_one), or a ``multi`` of every clause in order when a
    running fight's message holds two or more acts, moves or reactions (#101 review at f3e880e)."""
    if (state.get('combat') or {}).get('status') == 'running' and not (state.get('combat') or {}).get('awaiting'):
        steps = clauses(action, source, state)
        if len(steps) >= 2 or (steps and steps[0]['act'].get('kind') == 'missing_reaction'):
            first = next((s['act'] for s in steps if s['act'].get('target')), steps[0]['act'])
            return {'kind': 'multi', 'target': first.get('target'), 'steps': steps}
    return parse_one(action, source, state)


_SPLIT = re.compile(r"\s*\n\s*|[.;!?]+\s*|,\s*(?:and\s+)?(?:then\s+)?|\s+(?:and\s+)?then\s+|\s+and\s+", re.I)
_DETAIL = re.compile(r"^\W*(?:\(|\d|dc\s*\d|for\s+\d|total|avrae)|^\s*!\w|^\W*[A-Za-z']+\W*$|"
                     r"^\W*(?:i\s+)?(?:pause|breathe|take a (?:deep |slow )?breath|steady (?:myself|now|my\w*)|"
                     r"brace myself|grin|wink|nod|shrug|smile|laugh|sigh)\b", re.I)
SHIELD_SELF = re.compile(r"\bshield\s+(?:myself|me)\b|\b(?:cast|casts|casting|raise|raises)\s+(?:a\s+|my\s+)?shield\b"
                         r"(?!\s+(?:bash|slam))|!cast\s+shield\b")
UNRESOLVED = "I couldn't tell what that would do in this fight"


# An Avrae-shaped line: a command, a bold field, "X casts Y!" / "X attacks with Y!", or a
# "Field: number" result line ("To Hit: 1d20 (11) + 7 = 18", "Hellish Rebuke: 12 fire").
_AVRAE_SHAPED = re.compile(r"^\s*(?:!\w|\*\*|[\w' -]+ (?:casts|attacks with|uses) [^\n]*!\s*$|"
                           r"(?:to hit|damage|dc|meta|effect|spell slots|[\w' -]+ save)\s*:|[\w' -]{2,40}:\s*`?\d)", re.I)
_BLOCK_HEAD = re.compile(r"!cast\s+([a-z' ]+?)(?:\s+-\w|\s*$)|!a(?:ttack)?\s+([a-z' ]+?)(?:\s+-\w|\s*$)|"
                         r"\bcasts\s+([a-z' ]+?)!|\battacks with (?:an? )?([a-z' ]+?)!|\*\*([a-z' ]+?)\*\*", re.I)


def avrae_blocks(action):
    """[(start, end)] of each pasted Avrae block: from its first Avrae-shaped line to its last.
    A short name line between two of them (a target, 'Hollow-eyed ghoul') is inside; the lines
    after the last one are the player's again (#101 review at 92b86a6)."""
    lines, at = [], 0
    for line in action.split('\n'):
        lines.append((at, at + len(line), line))
        at += len(line) + 1
    shaped = [bool(_AVRAE_SHAPED.match(line)) for _, _, line in lines]
    blocks, i = [], 0
    while i < len(lines):
        if not shaped[i]:
            i += 1
            continue
        j = i
        while True:
            k = j + 1
            while k < len(lines) and not shaped[k] and len(lines[k][2].split()) <= 4 and \
                    not re.match(r"\s*(?:i|then|and)\b", lines[k][2], re.I):
                k += 1
            if k < len(lines) and shaped[k]:
                j = k
                continue
            break
        blocks.append((lines[i][0], lines[j][1]))
        i = j + 1
    return blocks


def _pieces(action):
    """(start, end, is_block) spans: Avrae blocks whole, the rest split at clause boundaries."""
    masked = re.sub(r'\([^)]*\)', lambda m: '_' * len(m.group(0)), action)
    masked = re.sub(r'!(?=\w)', '_', masked)
    out, at = [], 0
    regions = []
    for b0, b1 in avrae_blocks(action):
        regions.append((at, b0, False))
        regions.append((b0, b1, True))
        at = b1
    regions.append((at, len(action), False))
    for r0, r1, block in regions:
        if block:
            out.append((r0, r1, True))
            continue
        cut = r0
        for m in _SPLIT.finditer(masked, r0, r1):
            if m.end() > r1:
                break
            out.append((cut, m.start(), False))
            cut = m.end()
        out.append((cut, r1, False))
    return [p for p in out if p[1] > p[0]]


def clauses(action, source, state):
    """Every clause of the message that is an act, a move or a reaction, in order, each with
    the details after it (its rolls, its Avrae aside or pasted block, a trailing 'and the imp').
    Waiting and breathing are flavor (details), never a clause of their own."""
    resources = state.get('pc_resources') or {}
    shield_known = any(r.get('id') == 'shield' for r in resources.get('reactions') or ())
    steps, lead = [], None
    for start, end, block in _pieces(action):
        piece = action[start:end].strip()
        if not re.search(r'[A-Za-z]', piece):
            if steps:
                steps[-1]['end'] = max(steps[-1]['end'], end)
            continue
        act = None
        if block:
            head = _BLOCK_HEAD.search(piece)
            name = next((g for g in head.groups() if g), '').strip().casefold() if head else ''
            own = re.match(r"\s*!(?:cast|a|attack)\b|\s*[\w' -]+ (?:casts|attacks with) ", piece, re.I)
            prev = steps[-1]['text_so_far'] if steps else ''
            if steps and (name and name in prev.casefold() or not own):
                steps[-1]['end'] = max(steps[-1]['end'], end)  # the results of the clause before it
                steps[-1]['text_so_far'] = action[steps[-1]['start']:steps[-1]['end']]
                continue
            act = parse_one(piece, source, state)
        elif not _DETAIL.match(piece):
            missing = missing_reaction(piece, resources)
            if not missing and not shield_known and SHIELD_SELF.search(piece.casefold()):
                missing = 'Shield'
            act = {'kind': 'missing_reaction', 'target': None, 'name': missing} if missing else \
                parse_one(piece, source, state)
        if act is None or act.get('kind') in (None, 'wait'):
            if steps:
                steps[-1]['end'] = max(steps[-1]['end'], end)
                steps[-1]['text_so_far'] = action[steps[-1]['start']:steps[-1]['end']]
            elif lead is None:
                lead = start
            continue
        first = start if lead is None else lead
        steps.append({'start': first, 'end': end, 'act': act, 'block': block, 'text_so_far': action[first:end]})
        lead = None
    for step in steps:
        step.pop('text_so_far', None)
        step['text'] = action[step['start']:step['end']].strip(' ,;\n')
        step['label'] = _label(step)
    if len(steps) < 2:
        return steps
    # Each clause re-read on its own text with its details (an attack's rolls ride after it).
    for step in steps:
        if step['act'].get('kind') != 'missing_reaction':
            again = parse_one(step['text'], source, state)
            if again and again.get('kind') == step['act'].get('kind'):
                step['act'] = again
    return steps


def _label(step):
    act = step['act']
    if act.get('kind') == 'missing_reaction':
        return act['name']
    if act.get('kind') == 'late_reaction':
        names = act.get('names') or [act['react'].replace('_', ' ')]
        again = ' again' if re.search(r'\bagain\b', step['text'], re.I) else ''
        return names[0].title() + again
    return f'"{step["text"][:80]}"'


def missing_reaction(text, resources):
    """A reaction the catalog knows, named in the clause, that is not on his sheet."""
    have = {r['id'] for r in resources.get('reactions') or ()}
    low = text.casefold()
    for key, spec in kit_reactions.CATALOG.items():
        if key in have or key in ('shield', 'opportunity_attack'):
            continue
        if re.search(r'\b' + re.escape(spec['name'].casefold()) + r'\b', low):
            return spec['name']
    return None


def parse_one(action, source, state):
    """What the player physically does, or None. A dict with ``kind`` (attack, grab,
    face, flip, take, wait), ``target`` (actor id or None), and the details each needs."""
    if not config(source) or state.get('area') != config(source).get('area', state.get('area')):
        return None
    text = narration(action).casefold()
    here = present(source, state)
    sc = scene(state)
    aimed = re.search(r"\s-t\s+([a-z][\w'-]*)", text)  # Avrae's -t names the target
    named = (name_target(aimed.group(1), source, state, here) if aimed else None) or \
        name_target(text, source, state, here)
    spell = _SPELL.search(text)
    in_fight = bool((state.get('combat') or {}).get('status') in ('awaiting_initiative', 'running'))
    late = late_reaction(text, source, state, here) if in_fight else None
    if late:
        return late
    if in_fight and OWN_SHIELD.search(text):
        return {'kind': 'own_shield', 'target': None, 'avrae': bool(re.search(r'!cast|casts shield!', text))}
    away = WITHDRAW.search(text) if in_fight else None
    if spell:
        name = spell.group(1)
        area = name in SPELL_SAVE and SPELL_SAVE[name][2]
        return {'kind': 'attack', 'spell': name, 'weapon': name, 'area': bool(area),
                'target': None if area else (named or _default_target(text, source, state, here)),
                **({'move_first': {'disengage': bool(re.search(r'\bdisengag', text))}}
                   if away and away.start() < spell.start() else {})}
    actor_names = tuple(name for key in (state.get('actors') or {}) for name in _names(source, key))
    attack = first_aimed_attack(text, actor_names)
    weapon = re.search(r'\b(' + WEAPONS + r')\b', text)
    if attack and attack.group(1) in ('stomp', 'stomps'):
        target = named or sc.get('grovelling') or _default_target(text, source, state, here)
        return {'kind': 'attack', 'weapon': 'stomp', 'target': target, 'area': False, 'unarmed': True}
    hostile_target = named or (_creature_words(text) and not OBJECTS.search(text[attack.end():attack.end() + 30]
                                                                             if attack else ''))
    stated_attack = kit_rolls.attack_total(action) is not None and (weapon or in_fight or named)
    if (attack and (hostile_target or stated_attack or in_fight) and
            not (TABLE.search(text[attack.end():attack.end() + 25]) and not named)) or (not attack and stated_attack):
        held = None if weapon or not re.search(r'\b(?:stab|stabs|slash|slashes|thrust|thrusts|cut|cuts)\b', text) \
            else sheet_weapon(state)  # 'I stab' with no weapon named: the blade on his sheet
        return {'kind': 'attack', 'weapon': weapon.group(1) if weapon else held or 'unarmed strike',
                'target': named or _default_target(text, source, state, here), 'area': False,
                'unarmed': not (weapon or held), 'nonlethal': bool(NONLETHAL.search(text))}
    if FLIP.search(text) and TABLE.search(text):
        return {'kind': 'flip', 'object': 'table', 'target': None}
    if touched_face(text, pc_names(state)) and (named or _creature_words(text) or here):
        return {'kind': 'face', 'target': named or _default_target(text, source, state, here),
                'teeth': bool(TEETH.search(text))}
    pcs = pc_names(state)
    take, loot = taken_valuables(text, pcs)
    if take and loot and table_scene(source):
        what = 'ring' if re.search(r'\bring\b', text) and not re.search(r'\bcoins?|gold|pot|money|stacks?\b', text) \
            else 'coins'
        return {'kind': 'take', 'what': what, 'target': None, 'covert': bool(COVERT.search(text)),
                'handful': bool(re.search(r'\b(handful|a few|some|fistful|a stack)\b', text))}
    grab = GRAB.search(text)
    # A grapple is aimed at a creature: what the verb takes ('the rope', 'my cloak') decides.
    gripped = re.split(r"[,;.\n]|\band\b|\bthen\b", text[grab.end():])[0] if grab else ''
    if grab and not (name_target(gripped, source, state, here) or _creature_words(gripped)):
        grab = None
    if grab and (named or _creature_words(text)) and here and not VALUABLES.search(text[grab.end():grab.end() + 30]) \
            and not GAZE.search(text[grab.end():grab.end() + 20]):
        return {'kind': 'grab', 'target': named or _default_target(text, source, state, here),
                'teeth': bool(TEETH.search(text)), 'wrist': bool(re.search(r'\b(wrist|hand|arm)\b', text))}
    if in_fight and APPROACH.search(text) and not attack:
        return {'kind': 'approach', 'target': named or _default_target(text, source, state, here)}
    if in_fight and WITHDRAW.search(text) and not attack:
        return {'kind': 'withdraw', 'target': None, 'disengage': bool(re.search(r'\bdisengag', text))}
    if in_fight and WAIT.search(text):
        return {'kind': 'wait', 'target': None}
    return None


APPROACH = re.compile(r"\b(?:close (?:in|the (?:distance|gap))|closes in|step (?:up|in)|steps (?:up|in)|advance|advances|"
                      r"charge|charges|rush|rushes|move (?:toward|towards|up to|back to|in on)|close on|press in)\b")


def sheet_weapon(state):
    """The first melee weapon on his sheet's gear, or None."""
    for item in ((state.get('player_sheet') or {}).get('gear') or ()):
        found = re.search(r'\b(' + WEAPONS + r')\b', str(item).casefold())
        if found and not RANGED.search(found.group(1)):
            return found.group(1)
    return None


def table_scene(source):
    """True for a room whose combat block keys loose loot on a table (``loose_money``): only
    there do coins and a ring lie about to be taken, and only there is ``room_now`` shown."""
    return bool(((source or {}).get('combat') or {}).get('loose_money'))


# Conditions that stop the PC moving and acting (SRD: incapacitated, and every condition that
# includes it), and the 0 HP state.
INCAPACITATING = ('incapacitated', 'paralyzed', 'petrified', 'stunned', 'unconscious')
# SRD: attack rolls against a paralyzed, petrified, stunned or unconscious creature have
# advantage; a hit from within 5 feet on a paralyzed or unconscious one is a critical hit.
ADVANTAGE_AGAINST = ('paralyzed', 'petrified', 'stunned', 'unconscious')
AUTO_CRIT = ('paralyzed', 'unconscious')
ROUND_SECONDS = 6


def pc_conditions(state):
    """The PC's conditions now (names): they persist past the fight until they end by rule."""
    return list((state or {}).get('pc_conditions') or [])


def condition_terms(state):
    """How each of the PC's conditions ends (SRD): {name: {'rounds': n} (a duration in rounds,
    ticking at the end of his turns), {'until_s': t} (the session clock), {'while': other}
    (it lasts while the other does: the centipede's paralysis while poisoned), {'while':
    'down'} (unconscious at 0 hit points), and 'save': {ability, dc, when: 'end_of_turn'} (he
    repeats the save at the end of each of his turns)}."""
    return copy.deepcopy((state or {}).get('pc_condition_terms') or {})


def pc_incapacitated(state):
    """Why the PC cannot move or act now ('dead', 'down', or the condition), else None."""
    current = (state or {}).get('combat') or {}
    if current.get('pc_dead'):
        return 'dead'
    if current.get('pc_down'):
        return 'down'
    for name in pc_conditions(state):
        if name in INCAPACITATING:
            return name
    return None


def expire_after(state, seconds):
    """(names, terms, ended) once ``seconds`` of game time pass: conditions whose duration runs
    out end, and so does whatever lasts only while they do."""
    names, terms = pc_conditions(state), condition_terms(state)
    now = int((state or {}).get('elapsed_seconds') or 0) + int(seconds)
    ended = []
    for name in list(names):
        term = terms.get(name) or {}
        if 'until_s' in term and now >= int(term['until_s']) or \
                'rounds' in term and int(seconds) >= int(term['rounds']) * ROUND_SECONDS:
            ended.append(name)
        elif 'rounds' in term:
            term['rounds'] = int(term['rounds']) - int(seconds) // ROUND_SECONDS
    changed = True
    while changed:
        changed = False
        for name in names:
            parent = (terms.get(name) or {}).get('while')
            if name not in ended and parent and parent != 'down' and (parent in ended or parent not in names):
                ended.append(name)
                changed = True
    kept = [n for n in names if n not in ended]
    return kept, {n: t for n, t in terms.items() if n in kept}, ended


def soonest_expiry(state):
    """Seconds until the first timed condition ends, else None."""
    terms = condition_terms(state)
    now = int((state or {}).get('elapsed_seconds') or 0)
    waits = []
    for name in pc_conditions(state):
        term = terms.get(name) or {}
        if 'until_s' in term:
            waits.append(max(1, int(term['until_s']) - now))
        elif 'rounds' in term:
            waits.append(max(1, int(term['rounds']) * ROUND_SECONDS))
    return min(waits) if waits else None


def _default_target(text, source, state, here):
    """Who a physical act means when the words do not name anyone. "The nearest" is the
    room's reach order. Otherwise (him, his wrist, whoever is left): the one the PC already
    holds or is fighting, else the dealer of a deal in progress, else whoever spoke to the
    PC last, else the leader, else the nearest."""
    if not here:
        return None
    order = [key for key in config(source).get('reach_order') or here if key in here] or list(here)
    if NEAREST.search(text):
        return order[0]
    sc = scene(state)
    current = state.get('combat') or {}
    pending = current.get('pending') if isinstance(current.get('pending'), dict) else {}
    candidates = [sc.get('grovelling') if re.search(r'\b(hand|hands|fingers)\b', text) else None,
                  sc.get('grappled'), pending.get('target'), current.get('last_target')]
    if re.search(r'\b(deal|dealing|deck|cards|mid-deal)\b', text):
        for key, config_ in ((source or {}).get('procedures') or {}).items():
            if isinstance(config_, dict) and key in (state.get('procedures') or {}):
                candidates.append((config_.get('cheat') or {}).get('actor'))
    said = ((state.get('claims') or {}).get('said') or [])
    if said:
        candidates.append(said[-1].get('by'))
    candidates.append(config(source).get('leader'))
    for key in candidates:
        if key in here:
            return key
    return order[0]


class Fight:
    """Resolve one physical act (or an initiative report) into public lines and events."""

    def __init__(self, source, state, revision, action, check, roll=None, choice=None):
        self.source = source
        self.choice = choice    # Kit's structured read of the reply to an open window (or None)
        self.config = config(source)
        self.state = state
        self.revision = revision
        self.action = action
        self.check = check      # (skill, dc, label) -> pc_check result dict
        self.roll = roll        # host override for Kit's own d20s (tests), else seeded
        self.scene = scene(state)
        self.fight = fight(state)
        self.statuses = {}
        self.reveals = []
        self.lines = []
        self.trace = []
        self.labels = labels(source)
        self.needs_roll = False  # the act is an attack still waiting on its Avrae roll
        self.sheet = state.get('player_sheet') or {}
        self.kills = []          # who the PC's blows killed this turn (a flourish may follow)
        self.flourish_of = None  # resumed from a flourish: whose death the player described
        self.resources = kit_reactions.current(state)  # the PC's reaction inventory, slots, uses
        self.resources_changed = not isinstance(state.get('pc_resources'), dict)
        self.conditions = pc_conditions(state)
        self.terms = condition_terms(state)
        self.conditions_changed = False

    # -- helpers ---------------------------------------------------------------------
    def label(self, key):
        return self.labels.get(key, key).lower()

    def die(self, tag):
        if self.roll:
            return self.roll()
        material = f"{self.state.get('roll_seed', '')}:{self.revision}:{tag}:{self.action.casefold()}".encode()
        return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1

    def status(self, key):
        return self.statuses.get(key) or (self.state['actors'][key].get('status'))

    def active(self, key):
        actor = self.state['actors'][key]
        return actor.get('location') == self.state.get('area') and self.status(key) in ACTIVE_STATUSES

    def hostiles(self):
        return [key for key in self.config.get('actors', {}) if key in self.state['actors'] and self.active(key)]

    def stats(self, key):
        return self.config['actors'][key]

    def ensure_fight(self, started_by):
        if self.fight and self.fight.get('status') != 'over':
            return False
        hp = {key: self.stats(key)['hp'] for key in self.config['actors']
              if key in self.state['actors'] and self.state['actors'][key].get('status') != 'hidden'}
        self.fight = {'status': 'awaiting_initiative', 'round': 1, 'order': [], 'next': 0,
                      'pc_initiative': None, 'surprised': list(self.surprised()), 'hp': hp, 'max_hp': dict(hp),
                      'pc_damage': 0, 'pending': None, 'opener_spent': False, 'started_by': started_by,
                      'last_target': None, 'engaged': []}
        self.trace.append(f'fight starts ({started_by}); surprised: {self.fight["surprised"] or "nobody"}')
        self.scene['pc_hidden'] = False  # the first blow gives the PC away
        return True

    def start_by_trigger(self, trigger, pc_surprised, trace, waking=None):
        """A room trigger starts (or joins) the fight without the PC attacking (kit_triggers).
        The ambushers are never surprised; the PC is when he noticed none of them. Joining a
        running fight, each newcomer takes its place in the order by its initiative."""
        waking = list(trigger['actors'] if waking is None else waking)
        started = self.ensure_fight(f"trigger:{trigger['id']}")
        if started:
            self.fight['surprised'] = ['pc'] if pc_surprised else []
        else:
            for key in waking:
                if key in self.config.get('actors', {}) and key not in self.fight['hp']:
                    self.fight['hp'][key] = self.fight['max_hp'][key] = self.stats(key)['hp']
                    if self.fight['order']:
                        self.join_order(key)
        self.trace.append(f"room trigger {trigger['id']}: {', '.join(waking)} join; {trace}")
        if trigger.get('reveal'):
            self.lines.append(trigger['reveal'])
        if self.fight['status'] == 'awaiting_initiative':
            self.lines.append('Roll initiative.')
        return started

    def pc_surprised_now(self):
        """Surprised and his first turn not yet over (SRD: no move, action, or reaction)."""
        return 'pc' in (self.fight.get('surprised') or ()) and self.fight.get('round') == 1 and \
            not self.fight.get('surprise_spent')

    def pc_can_react(self):
        """SRD surprise: a surprised PC takes no reaction until his first turn ends (round 1).
        The seam #101's reaction windows read; a PC who is down or incapacitated has none."""
        if not self.fight or self.fight.get('pc_down'):
            return False
        return not self.pc_surprised_now() and not any(c in INCAPACITATING for c in self.conditions)

    def initiative_of(self, key):
        """(count, tiebreak): the PC's reported total, an NPC's flat 10 + Dexterity."""
        if key == 'pc':
            return (self.fight.get('pc_initiative') or 0, 99)
        bonus = self.stats(key).get('initiative', 0)
        return (10 + bonus, bonus)

    def join_order(self, key):
        """A creature joining a running fight takes its initiative count in the order (SRD);
        whoever is up next stays up next."""
        order = self.fight['order']
        mine = self.initiative_of(key)
        at = next((i for i, other in enumerate(order) if self.initiative_of(other) < mine), len(order))
        order.insert(at, key)
        if at <= self.fight['next']:
            self.fight['next'] += 1  # its count has passed this round: it acts from the next
        self.trace.append(f'{key} joins the order at initiative {mine[0]}')

    def surprised(self):
        """Nobody is surprised unless the PC is hidden from everyone when it starts."""
        return [key for key in self.hostiles()] if self.scene.get('pc_hidden') else []

    def pc_ac(self):
        return int(self.sheet.get('ac') or 10) + (5 if (self.fight or {}).get('shield_up') else 0)

    # -- checkpoints -------------------------------------------------------------------
    def wait_for(self, kind, awaits, **detail):
        """Record what the fight waits on and stop. The id names the deferred action."""
        material = f"{self.revision}:{kind}:{self.fight.get('round')}:{sorted(detail.items())}".encode()
        self.fight['awaiting'] = {'kind': kind, 'awaits': awaits,
                                  'deferred_action_id': hashlib.sha256(material).hexdigest()[:12], **detail}
        self.trace.append(f'checkpoint: {kind} ({awaits})')
        raise Checkpoint()

    def start_pc_turn(self):
        """Shield ends and the reaction comes back at the start of the PC's turn; an Absorb Elements
        charge is live for this turn's first melee hit."""
        for key in ('shield_up', 'reaction_used'):
            self.fight.pop(key, None)
        if self.fight.get('absorb_bonus'):
            self.fight['absorb_bonus']['armed'] = True

    def spend_reaction(self, key, slot_level=None):
        """The reaction is used; its cost is paid from the session's inventory (a spell's slot is the
        one the player's Avrae cast used, or the lowest free one at its level)."""
        self.fight['reaction_used'] = True
        self.fight.pop('unprompted', None)
        self.resources, slot = kit_reactions.spend(self.resources, key, slot_level)
        self.resources_changed = True
        self.trace.append(f'PC uses {key}' + (f' (level {slot} slot, cast in Avrae)' if slot else ''))

    def unprompted(self, trigger, options, **event):
        """A reaction this event made legal but not worth a prompt (#101 P2): the player may still
        declare it, before his own act on his next turn."""
        self.fight.setdefault('unprompted', []).append({'trigger': trigger, 'options': list(options), **event})
        self.trace.append(f"{', '.join(options)} legal for {trigger} by {event.get('attacker')}, not prompted")

    def pc_late_reaction(self, act):
        """He declares a reaction he was not prompted for: it answers the event it was legal for
        (the attacker he names, else the latest). The cost is paid; the round's reaction is the one
        already past, so his own turn's reaction stays. True when it took effect; otherwise the
        reason is said (alone: its own line; in a multi-clause message: "didn't happen because")."""
        react = act['react']
        found = kit_reactions.entry(self.resources, react) or {}
        event = act['event']
        name = found.get('name', react)
        self.refused_because = None

        def refuse(line, because):
            self.refused_because = because
            if not getattr(self, 'in_multi', False):
                self.lines.append(line)
            return False

        late_ok = ('absorb_elements', 'uncanny_dodge', 'deflect_missiles', 'parry', 'hellish_rebuke')
        avrae_cast = bool(re.search(r'!cast\s+' + re.escape(name.casefold()), self.action.casefold()))
        if event is not None and found.get('effect') not in late_ok and \
                (self.declared_effect(react) or {}).get('type') not in ('reduce_damage', 'deal_damage'):
            # A reroll (Silvery Barbs) cannot be replayed after the hit has landed: said, nothing spent.
            return refuse(f'That hit has already landed; {name} cannot change it now.',
                          'that hit has already landed and it cannot change it now')
        if event is None:
            # Nothing it can answer now (the hit was not its kind, or the reaction is spent): no
            # effect. Only a cast Avrae actually made is counted, at its -l level (else its own).
            fizzled = self.avrae_fizzle(name)
            if fizzled:
                return refuse(f'{name} has nothing to answer right now, so it fizzles. {fizzled}',
                              f'it has nothing to answer right now, so it fizzles. {fizzled}'[:-1])
            return refuse(f'{name} has nothing to answer right now, so it does nothing.',
                          'it has nothing to answer right now')
        if not kit_reactions.payable(self.resources, found):
            return refuse(f'{name} is not available: no slot or use left.', 'there is no slot or use left for it')
        if found.get('kind') == 'spell' and not act.get('avrae'):
            return refuse(f'Cast {name} in Avrae first (!cast {name.casefold()}), then say so.',
                          f'it is cast in Avrae first (!cast {name.casefold()})')
        effect = found.get('effect')
        if effect == 'hellish_rebuke' and self.reaction_roll() is None:
            return refuse(f"Roll {name}'s damage in Avrae ({found.get('dice', 'its roll')}), then say so.",
                          f"its damage roll is missing ({found.get('dice', 'its roll')} in Avrae)")
        level = cast_level(self.action) or (self.choice or {}).get('slot_level')
        if level and found.get('kind') == 'spell':
            slot = (self.resources.get('slots') or {}).get(str(level))
            need = (found.get('cost') or {}).get('slot') or 1
            if int(level) < int(need) or not slot or slot['used'] >= slot['max']:
                return refuse(f'There is no level {level} slot left for {name} on the sheet.',
                              f'there is no level {level} slot left for it')
        self.fight.pop('unprompted', None)
        self.resources, slot = kit_reactions.spend(self.resources, react, level)
        self.resources_changed = True
        self.trace.append(f"PC declares {react} for the unprompted {event['trigger']} by {event.get('attacker')}"
                          + (f' (level {slot} slot)' if slot else ''))
        dealt = int(event.get('damage') or 0)
        if effect in ('absorb_elements', 'uncanny_dodge'):
            back = dealt - dealt // 2
            self.fight['pc_damage'] = max(0, int(self.fight.get('pc_damage') or 0) - back)
            if effect == 'absorb_elements':
                self.fight['absorb_bonus'] = {'type': event['type'], 'dice': '1d6', 'armed': True}
                self.lines.append(f"Absorb Elements: resistance to the {event['type']}; your next melee hit "
                                  f"adds 1d6 {event['type']}.")
            else:
                self.lines.append(f'Uncanny Dodge: you take half, {dealt // 2} instead of {dealt}.')
        elif effect in ('deflect_missiles', 'parry') or (self.declared_effect(react) or {}).get('type') == 'reduce_damage':
            cut = min(dealt, int(self.reaction_roll() or 0))
            self.fight['pc_damage'] = max(0, int(self.fight.get('pc_damage') or 0) - cut)
            self.lines.append(f'{name}: {cut} less damage.')
        else:
            self.answer_attacker({'attacker': event.get('attacker'), 'trigger': event['trigger']}, react)
        return True

    MULTI_ACTIONS = ('attack', 'grab', 'face', 'flip', 'take', 'wait')

    def run_clauses(self, act):
        """A message of several clauses (#101 review at f3e880e), structurally: every clause in
        order; a reaction clause resolves as a reaction, every other one goes to the act and move
        parser. No clause is dropped: each resolves, or Kit says it didn't happen and why."""
        steps = act['steps']
        whole = self.action
        acted = reacted = moved = False
        self.in_multi = True
        try:
            for index, step in enumerate(steps, 1):
                self.action = step['text']
                one = step['act']
                kind = one.get('kind')
                label = step['label']
                before = len(self.lines)
                because = None
                if not self.fight or self.fight.get('status') != 'running':
                    because = 'the fight is over'
                elif self.fight.get('awaiting'):
                    because = 'the fight is waiting on your answer first'
                elif not self.pc_turn_now():
                    because = 'it is not your turn'
                elif kind == 'missing_reaction':
                    because = 'it is not on your sheet'
                    fizzled = self.avrae_fizzle(one['name'])
                    if fizzled:
                        because += f', so the cast fizzles. {fizzled[:-1]}'
                elif kind == 'late_reaction':
                    effect = (kit_reactions.entry(self.resources, one['react']) or {}).get('effect')
                    if reacted:
                        # Refused before any cast is asked for; one Avrae already made fizzles, counted.
                        because = 'you have already used your reaction'
                        fizzled = self.avrae_fizzle((kit_reactions.entry(self.resources, one['react']) or {})
                                                    .get('name', one['react']))
                        if fizzled:
                            because += f', so the cast fizzles. {fizzled[:-1]}'
                    elif acted and effect == 'absorb_elements' and one.get('event'):
                        because = 'you have already acted, and the fire it answers came before your turn'
                    elif self.pc_late_reaction(one):
                        reacted = True
                    else:
                        because = self.refused_because or 'it has nothing to answer'
                elif kind == 'withdraw':
                    self.pc_move_away(one)
                    moved = True
                elif kind == 'approach':
                    self.pc_approach(one)
                    moved = True
                elif kind == 'own_shield':
                    self.pc_own_shield(one)  # a cast with no trigger: said, never his action
                elif kind in self.MULTI_ACTIONS:
                    if acted:
                        because = 'you have already used your action this turn'
                    elif kind == 'attack' and self.out_of_reach(one):
                        because = f"the {self.label(one['target'])} is out of your reach now"
                    elif kind == 'attack':
                        if one.get('move_first'):
                            self.pc_move_away(one['move_first'])
                            moved = True
                            if self.out_of_reach(one):
                                because = f"the {self.label(one['target'])} is out of your reach now"
                        if because is None:
                            acted = self.pc_attack(one)
                        if because is None and not acted:
                            self.needs_roll = True
                            return
                    else:
                        acted = True
                        {'grab': self.pc_grab, 'face': self.pc_face, 'flip': self.pc_flip, 'take': self.pc_take,
                         'wait': self.pc_wait, 'own_shield': self.pc_own_shield}[kind](one)
                if because is None and len(self.lines) == before:
                    because = None if one.get('flavor') else UNRESOLVED.replace("I couldn't tell", 'I could not tell')
                if because:
                    said = f"{label} didn't happen because {because}."
                    if said not in self.lines:  # the same refusal is said once
                        self.lines.append(said)
                self.trace.append(f"clause {index}/{len(steps)}: {'refused' if because else 'resolved'} "
                                  f"({step['text'][:60]})")
                if self.fight.get('awaiting'):
                    # A checkpoint opened (a window, a flourish): the clauses after it wait for his turn.
                    rest = ' '.join(s['text'] for s in steps[index:])
                    if rest:
                        self.fight['declared_next'] = rest
                        for later, s in enumerate(steps[index:], index + 1):
                            self.trace.append(f'clause {later}/{len(steps)}: resolved (held for your turn: '
                                              f"{s['text'][:60]})")
                        self.lines.append('The rest waits for your next turn.')
                    break
        finally:
            self.in_multi = False
            self.action = whole
        self.after_pc_action(acted or moved)  # moving ends his turn the way one move does

    def avrae_fizzle(self, name):
        """A reaction spell Avrae already cast that cannot take effect: Avrae spent the slot (at
        its -l level, else the spell's own), so the engine counts it too. The sentence that says
        so, or '' when Avrae did not cast it."""
        if not re.search(r'!cast\s+' + re.escape(name.casefold()) + r'\b', self.action.casefold()):
            return ''
        spec = next((c for c in kit_reactions.CATALOG.values() if c['name'] == name), {})
        if spec and spec.get('kind') != 'spell':
            return ''
        level = cast_level(self.action) or spec.get('level') or 1
        slot = (self.resources.get('slots') or {}).get(str(level))
        if not slot or slot['used'] >= slot['max']:
            return ''
        self.resources['slots'] = copy.deepcopy(self.resources['slots'])
        self.resources['slots'][str(level)]['used'] += 1
        self.resources_changed = True
        self.trace.append(f'{name} cast in Avrae with nothing to do: level {level} slot counted')
        return f'The level {level} slot Avrae spent is counted.'

    def out_of_reach(self, act):
        """A melee blow at a foe he has moved out of reach of (this turn's clauses, in order)."""
        key = act.get('target')
        weapon = str(act.get('weapon') or '')
        if not key or act.get('spell') or act.get('area') or RANGED.search(weapon):
            return False
        return key in (self.fight.get('apart') or ()) and key not in (self.fight.get('engaged') or ())

    def pc_approach(self, act):
        key = act.get('target')
        if key and self.active(key):
            self.engage(key)
            self.lines.append(f'You close on the {self.label(key)}.')
        else:
            self.lines.append('You move up.')

    def engage(self, key):
        engaged = self.fight.setdefault('engaged', [])
        if key not in engaged:
            engaged.append(key)
        if key in (self.fight.get('apart') or ()):
            self.fight['apart'] = [k for k in self.fight['apart'] if k != key]

    def in_reach(self, key):
        """Melee adjacency, tracked by default: whoever traded melee blows with the PC (either way)
        this fight, plus anyone the room says starts in reach."""
        if key in (self.fight.get('engaged') or ()):
            return True
        return key in (self.config.get('in_reach') or ()) and key not in (self.fight.get('apart') or ())

    def declined(self, family, stakes):
        """Kept for the window families: True only when every reaction this family could open was
        declined this round at no lower stakes (per reaction now: see fresh)."""
        return False

    def decline(self, waiting):
        """The player said no: each reaction offered is not offered again this round unless the
        stakes rise (the hit would now drop him, or a new damage type for a typed reaction)."""
        mark = self.fight.get('declined') or {}
        if mark.get('round') != self.fight.get('round') or 'reactions' not in mark:
            mark = {'round': self.fight.get('round'), 'reactions': {}}
        for key in waiting.get('options') or ():
            mark['reactions'][key] = {'stakes': waiting.get('stakes', 'normal'), 'damage': waiting.get('damage'),
                                      'type': waiting.get('type')}
        self.fight['declined'] = mark
        self.trace.append(f"PC declines {', '.join(waiting.get('options') or ())} ({waiting['trigger']}); not offered "
                          'again this round unless the stakes rise')

    def fresh(self, options, stakes, damage=None, dtype=None):
        """The options not declined this round, or declined at lower stakes than now."""
        mark = self.fight.get('declined') or {}
        if mark.get('round') != self.fight.get('round'):
            return list(options)
        out = []
        for key in options:
            before = (mark.get('reactions') or {}).get(key)
            if before is None:
                out.append(key)
                continue
            rose = (stakes == 'drop' and before.get('stakes') != 'drop') or \
                (key == 'absorb_elements' and dtype is not None and before.get('type') is not None and
                 dtype != before['type'])  # a new damage type matters only to a typed reaction
            if rose:
                out.append(key)
        return out

    def meaningful(self, dealt):
        """A hit worth a window for a reaction that only trims it: a quarter of his hit points, or 5+."""
        hp = int(self.pc_hp() or 0)
        return dealt >= max(5, hp // 4) if hp else True

    def break_contact(self, why):
        """The PC is out of every foe's reach (he moved away): engagement ends, and a foe the room put
        in reach is not either until blows are traded again."""
        self.fight['engaged'] = []
        self.fight['apart'] = sorted(set(self.fight.get('apart') or ()) | set(self.hostiles()))
        self.trace.append(f'PC out of reach ({why})')

    def pc_withdraw(self, why, provoke=True):
        """Combat movement away from foes in his reach: each one still up may make an opportunity
        attack (its first melee attack; the engine rolls the monsters' dice), then contact ends.
        Disengage (or a teleport) provokes none."""
        foes = [key for key in self.hostiles() if self.in_reach(key)]
        if provoke and not self.pc_surprised_now():
            for key in foes:
                attack = next((a for a in self.stats(key).get('attacks') or ()
                               if not a.get('ranged') and not RANGED.search(a['name']) and not a.get('spell')), None)
                if not attack or self.fight.get('pc_down'):
                    continue
                die = self.die(f'oa:{key}:r{self.fight["round"]}')
                total = die + attack['to_hit']
                hit = die == 20 or (die != 1 and kit_rolls.meets_or_beats(total, self.pc_ac()))
                dealt = attack['damage'] * (2 if die == 20 else 1)
                self.trace.append(f'{key} opportunity attack as the PC leaves: d20 {die} + {attack["to_hit"]} = '
                                  f'{total} vs AC {self.pc_ac()}: {"hit " + str(dealt) if hit else "miss"}')
                if hit:
                    self.lines.append(f"The {self.label(key)} lashes out as you go: {dealt} {attack['type']} damage.")
                    self.lines.extend(self.hurt_pc(dealt, crit=die == 20))
                else:
                    self.lines.append(f'The {self.label(key)} swings as you go and misses.')
        self.break_contact(why)

    def options_for(self, triggers, fit=None):
        """Reaction ids the event's trigger types open now (the inventory decides, any sheet)."""
        out = []
        for trigger in triggers:
            for key in kit_reactions.matching(self.resources, trigger, self.fight.get('reaction_used'), fit):
                if key not in out:
                    out.append(key)
        return out

    def important(self, key):
        """A kill worth a flourish: the leader, a foe the room marks important, or anyone who
        raises a story hook (room data). Not every mook."""
        if key == self.config.get('leader') or key in (self.config.get('important') or ()):
            return True
        for story in ((self.source or {}).get('story') or {}).values():
            hooks = story.get('hooks') if isinstance(story, dict) else None
            if any(isinstance(hook, dict) and hook.get('by') == key for hook in hooks or ()):
                return True
        return False

    def resume(self):
        """The player's answer to the checkpoint in ``fight['awaiting']``: finish what it
        deferred, then run on until the PC's turn or the next checkpoint. A reaction or flourish
        window takes Kit's structured read of the reply (``self.choice``); the engine only checks
        that the choice is legal."""
        waiting = self.fight['awaiting']
        kind = waiting['kind']
        try:
            if kind == 'reaction_window':
                react = self.legal_reaction(waiting)
                self.fight['awaiting'] = None
                if react == 'decline':
                    self.decline(waiting)
                    if (self.choice or {}).get('taken_as_no'):
                        self.lines.append('No clear answer, so that is taken as a no.')
                        self.trace.append('window asked twice without a clear answer: taken as a decline')
                self.resolve_window(waiting, react)
                self.route_rest(waiting, react)
            elif kind == 'roll_call' and (waiting['save'] == 'death' or waiting.get('repeat')):
                self.resume_save(waiting)  # his slot's own roll: the round runs on from there
            elif kind == 'roll_call':
                self.resume_save(waiting)
                self.after_save(waiting)
            elif kind == 'kit_call':
                self.fight['awaiting'] = None
                self.fight['vs_downed'] = self.default_vs_downed(waiting)
                self.trace.append(f"no call on the downed PC: {self.fight['vs_downed']} (default)")
                try:
                    self.run_npcs()
                except Checkpoint:
                    pass
                owed = self.fight.get('awaiting') or {}
                if owed.get('kind') == 'roll_call' and owed.get('save') == 'death' and \
                        save_total(self.action, 'death') is not None:
                    # A death save counts only once it is owed (#97 review): this one was typed
                    # before the foes' blows, which come first in the order.
                    self.lines.append('That death save was rolled before those blows; roll it again now.')
                    self.trace.append('early death save not counted: the foes act before his slot')
            else:  # flourish_window: the player's description; outcomes stand as committed
                read = (self.choice or {}).get('flourish')
                if read is None:
                    raise NeedsChoice(waiting)
                if read != 'describe':
                    raise Unclear('Kit could not tell a description from a new action.', 'unclear')
                self.fight['awaiting'] = None
                self.flourish_of = waiting.get('target')
                self.trace.append(f"flourish: the player's description stands as how {waiting.get('target')} "
                                  f"went {waiting.get('outcome', 'down')}; it changes no outcome")
                if self.fight['status'] == 'running':
                    self.advance_past_pc()
                    self.run_npcs()
        except Checkpoint:
            pass
        try:
            self.declared_turn()
        except Checkpoint:
            pass
        if self.fight.get('declared_next') and self.fight['status'] == 'running':
            self.lines.append(f"Held for your turn: {self.fight['declared_next'][:160]}")
        self.check_over()
        self.finish()
        if self.flourish_of and not self.public():
            self.lines.append('It is over.')
        return self.public(), self.events()

    def pass_flourish(self):
        """A new act instead of a description (Kit's read): the flourish is passed, the round runs on."""
        try:
            self.fight['awaiting'] = None
            if self.fight['status'] == 'running':
                self.advance_past_pc()
                self.run_npcs()
        except Checkpoint:
            pass
        self.finish()
        return self.public(), self.events()

    # -- reactions: the engine resolves the common SRD ones; Kit declares a closed effect for the rest --
    ATTACKING = ('opportunity_attack', 'riposte', 'mage_slayer', 'sentinel')

    def legal_reaction(self, waiting):
        """Kit's ``react`` for this window, checked: offered, still available, a spell cast in Avrae
        first (at a slot the PC has), an attack-making reaction rolled with a melee weapon, a rolled
        effect with the player's own roll, and a Kit-declared effect one the sheet text allows."""
        if self.choice is None or 'react' not in self.choice:
            raise NeedsChoice(waiting)
        react = self.choice['react']
        if react == 'unclear':
            # The bridge caps the asks (kit_agent.MAX_WINDOW_ASKS), then answers decline itself.
            raise Unclear('Kit could not tell which reaction, if any, the player takes.', 'unclear')
        if react == 'decline':
            return react
        if react not in waiting['options'] and react not in (waiting.get('eligible') or ()):
            # Prompted or not: the worth-it threshold decides only whether Kit asks (#101 P2).
            raise Unclear(f'{react} is not offered in this window (offered: {", ".join(waiting["options"])}).',
                          'not_offered')
        found = kit_reactions.entry(self.resources, react)
        if not found or self.fight.get('reaction_used') or not kit_reactions.payable(self.resources, found):
            raise Unclear(f'{react} is not available now (reaction spent, or no slot or use left).', 'not_available')
        if found['kind'] == 'spell':
            if not self.choice.get('cast_in_avrae'):
                raise Unclear(f"{found['name']} is cast in Avrae first.", 'needs_cast',
                              ask=f"!cast {found['name'].casefold()}")
            level = self.choice.get('slot_level')
            if level is not None:
                slot = (self.resources.get('slots') or {}).get(str(level))
                need = (found.get('cost') or {}).get('slot') or 1
                if int(level) < int(need) or not slot or slot['used'] >= slot['max']:
                    raise Unclear(f"There is no level {level} slot left for {found['name']} on the sheet.", 'no_slot',
                                  ask='which slot level the cast used')
        effect = found['effect']
        if effect in self.ATTACKING:
            if RANGED.search(narration(self.action).casefold()):
                raise Unclear(f"{found['name']} is a melee attack; a ranged weapon cannot make one.", 'ranged_weapon')
            if kit_rolls.attack_total(self.action) is None:
                raise Unclear(f"{found['name']} waits on its Avrae attack roll, with damage.", 'needs_roll',
                              ask='the attack roll and damage')
        if effect == kit_reactions.KIT:
            declared = (self.choice or {}).get('effect')
            allowed = kit_reactions.allowed_effects(found)
            if not declared:
                raise Unclear(f"{found['name']}: declare its effect (react.effect), one of {', '.join(allowed)}.",
                              'needs_effect')
            if declared['type'] not in allowed:
                raise Unclear(f"{found['name']}'s sheet text does not say it can {declared['type']} "
                              f"(it allows {', '.join(allowed)}).", 'effect_not_on_sheet')
            if declared['type'] in ('reduce_damage', 'deal_damage') and self.reaction_roll() is None:
                raise Unclear(f"{found['name']} waits on its roll in Avrae.", 'needs_roll', ask='the roll')
            if declared['type'] == 'succeed_save' and waiting['trigger'] != 'pc_save':
                raise Unclear(f"{found['name']} turns a failed save; this window is not a save.", 'effect_not_on_sheet')
        elif effect in kit_reactions.ROLLED and effect not in self.ATTACKING and self.reaction_roll() is None:
            if not (effect == 'counterspell' and int(waiting.get('level') or 0) <= 3):
                raise Unclear(f"{found['name']} waits on your roll in Avrae ({found.get('dice', 'its roll')}).",
                              'needs_roll', ask=found.get('dice') or 'the roll')
        if effect == 'counterspell' and int(waiting.get('level') or 0) > 3 and self.reaction_roll() is None:
            raise Unclear(f"Counterspell against a level {waiting['level']} spell is an ability check: roll it in "
                          'Avrae (your spellcasting ability).', 'needs_roll', ask='the spellcasting ability check')
        if effect in ('succeed_save', 'add_to_save') and found.get('save_only') and \
                found['save_only'] != waiting.get('save'):
            raise Unclear(f"{found['name']} answers only {found['save_only'].title()} saves.", 'not_offered')
        return react

    def reaction_roll(self):
        """The player's own roll for the reaction: Kit's react.roll (copied from the reply), else the
        reply's Avrae total. Never rolled here."""
        roll = (self.choice or {}).get('roll')
        if roll is not None:
            return int(roll)
        posted = kit_rolls.damage_total(self.action)[0]
        if posted:
            return int(posted)
        bare = re.search(r'(?:=|:|\btotal\b|\brolled?\b)\s*`?(\d{1,3})`?', self.action)
        return int(bare.group(1)) if bare else None

    def declared_effect(self, react):
        found = kit_reactions.entry(self.resources, react) or {}
        if found.get('effect') == kit_reactions.KIT:
            return (self.choice or {}).get('effect') or {'type': 'none'}
        return None

    def resolve_window(self, waiting, react):
        """Apply the reaction (or the decline) to the event the window holds, then run on."""
        trigger = waiting['trigger']
        if react != 'decline':
            self.spend_reaction(react, (self.choice or {}).get('slot_level'))
        if trigger == 'hit':
            self.resume_hit(waiting, react)
            self.npc_turn(waiting['attacker'], start=waiting['attack_index'] + 1)
            self.step()
            self.check_over()
            self.run_npcs()
        elif trigger in ('damaged', 'missed'):
            self.answer_attacker(waiting, react)
            self.npc_turn(waiting['attacker'], start=waiting['attack_index'] + 1)
            self.step()
            self.check_over()
            self.run_npcs()
        elif trigger == 'npc_spell':
            countered = react != 'decline' and self.answer_spell(waiting, react)
            index = waiting['attack_index']
            if self.active(waiting['attacker']):
                self.npc_turn(waiting['attacker'], start=index + 1 if countered else index,
                              cast_answered=not countered)
            self.step()
            self.check_over()
            self.run_npcs()
        elif trigger == 'npc_save':
            self.resume_spell_save(waiting, react)
            if self.fight['status'] == 'awaiting_initiative':
                self.fight['opener_spent'] = True  # the spell paused here was his opening blow
            self.after_pc_action(True)
        elif trigger == 'pc_save':
            saved = self.answer_failed_save(waiting, react)
            self.land_save(waiting['save_call'], saved, waiting['total'])
            self.after_save(waiting['save_call'])
        else:  # leaves_reach: an opportunity attack (Sentinel stops the foe too)
            key = waiting['actor']
            stays = False
            if react != 'decline':
                effect = (kit_reactions.entry(self.resources, react) or {}).get('effect')
                if effect in self.ATTACKING:
                    self.reaction_attack(key)
                    stays = effect == 'sentinel'
                    if stays and self.active(key):
                        self.lines.append(f'Sentinel: the {self.label(key)} is stopped where it stands.')
                else:
                    self.apply_declared(react, waiting, key)
            if self.active(key) and not stays:
                self.flee(key)
            self.step()
            self.check_over()
            self.run_npcs()

    def reaction_attack(self, key):
        """An attack-making reaction (the opportunity attack, Riposte, Mage Slayer, Sentinel): the
        player's Avrae attack and damage, made with the melee weapon the reply names."""
        weapon = re.search(r'\b(' + WEAPONS + r')\b', narration(self.action).casefold())
        self.pc_attack({'kind': 'attack', 'target': key, 'area': False,
                        'weapon': weapon.group(1) if weapon else 'attack', 'unarmed': not weapon})

    def apply_declared(self, react, waiting, key=None):
        """Kit's declared closed effect outside a hit (a foe leaving reach, a spell, a miss): the
        engine applies what applies there and says it."""
        found = kit_reactions.entry(self.resources, react) or {}
        effect = self.declared_effect(react) or {'type': 'none'}
        name = found.get('name', react)
        if effect['type'] == 'deal_damage' and key and self.active(key):
            self.reaction_damage(key, self.reaction_roll() or 0, effect.get('save'), found.get('type'), name)
        elif effect['type'] == 'move':
            feet = int(effect.get('feet') or 0)
            if feet >= 5:
                self.break_contact(f'{name}: {feet} feet')
            self.lines.append(f'{name}: you move {feet} feet.')
        elif effect['type'] == 'none':
            self.lines.append(f'{name}: it changes nothing here.')
        else:
            self.lines.append(f'{name}: no effect on this.')
        self.trace.append(f'{react}: Kit declared {effect}')

    def reaction_damage(self, key, amount, save, dtype, name):
        """Damage a reaction deals (the player's roll); a save named halves it on a success. The
        PC is the attacker: the creature's save that ties his DC fails."""
        dealt = int(amount)
        if save:
            dc = self.sheet.get('spell_save_dc') or _derived_save_dc(self.sheet) or 10
            bonus = self.stats(key).get('saves', {}).get(save)
            if bonus is None:
                bonus = _mod(((self.state['actors'][key].get('stats') or {}).get('abilities') or {}).get(save, 10))
            die = self.die(f'reaction_save:{key}:{name}:r{self.fight["round"]}')
            saved = not kit_rolls.attacker_wins(int(dc), die + bonus)
            dealt = dealt // 2 if saved else dealt
            self.trace.append(f'{key} {save} save vs {name}: d20 {die} + {bonus} vs DC {dc}: '
                              f'{"saved" if saved else "failed"}, {dealt}')
        self.lines.append(f'{name}: {dealt} {dtype or ""} damage to the {self.label(key)}.'.replace('  ', ' '))
        self.apply_damage(key, dealt, dtype)

    def answer_attacker(self, waiting, react):
        """After the hit landed (Hellish Rebuke) or after a melee miss (Riposte): the reaction answers
        the attacker."""
        if react == 'decline':
            return
        key = waiting['attacker']
        found = kit_reactions.entry(self.resources, react) or {}
        effect = found.get('effect')
        if not self.active(key):
            return
        if effect == 'hellish_rebuke':
            self.reaction_damage(key, self.reaction_roll() or 0, found.get('save', 'dex'), 'fire', found['name'])
        elif effect in self.ATTACKING:
            self.lines.append(f"{found['name']}: you strike back at the {self.label(key)}.")
            self.reaction_attack(key)
        else:
            self.apply_declared(react, waiting, key)

    def answer_spell(self, waiting, react):
        """A creature casting a spell: True when the reaction stops it (Counterspell)."""
        found = kit_reactions.entry(self.resources, react) or {}
        effect = found.get('effect')
        level = int(waiting.get('level') or 0)
        if effect == 'counterspell':
            if level <= 3:
                self.lines.append(f"Counterspell: the {waiting['name']} fails.")  # SRD: 3rd or lower simply fails
                return True
            check = self.reaction_roll()
            stopped = kit_rolls.meets_or_beats(check, 10 + level)  # the PC acts on the caster: meet or beat
            self.trace.append(f'counterspell check {check} vs DC {10 + level}: {"stopped" if stopped else "failed"}')
            self.lines.append(f"Counterspell: the {waiting['name']} " + ('fails.' if stopped else 'goes off anyway.'))
            return stopped
        if effect in self.ATTACKING:
            self.lines.append(f"{found['name']}: you strike the {self.label(waiting['attacker'])} mid-cast.")
            self.reaction_attack(waiting['attacker'])
            return False
        declared = self.declared_effect(react) or {'type': 'none'}
        if declared['type'] == 'negate_hit':
            self.lines.append(f"{found.get('name', react)}: the {waiting['name']} fails.")
            return True
        self.apply_declared(react, waiting, waiting['attacker'])
        return False

    def answer_failed_save(self, waiting, react):
        """The PC failed a save and a reaction answers it (Ring of Evasion, Lucky Footwork, or Kit's
        declared succeed_save): True when it now succeeds."""
        if react == 'decline':
            return False
        found = kit_reactions.entry(self.resources, react) or {}
        effect = found.get('effect')
        declared = self.declared_effect(react) or {}
        if effect == 'succeed_save' or declared.get('type') == 'succeed_save':
            self.lines.append(f"{found.get('name', react)}: you succeed instead.")
            return True
        if effect == 'add_to_save':
            total = int(waiting['total']) + int(self.reaction_roll() or 0)
            saved = not kit_rolls.attacker_wins(waiting['dc'], total)
            self.lines.append(f"{found['name']}: {total}, " + ('a success.' if saved else 'still a failure.'))
            return saved
        self.apply_declared(react, waiting)
        return False

    def resume_hit(self, waiting, react):
        name = waiting['name']
        dealt = waiting['damage']
        die = waiting['die']
        total = waiting['total']
        found = (kit_reactions.entry(self.resources, react) or {}) if react != 'decline' else {}
        effect = found.get('effect')
        declared = self.declared_effect(react) if react != 'decline' else None
        hit = True
        if effect == 'shield':
            self.fight['shield_up'] = True
            hit = not waiting.get('magic_missile') and (die == 20 or kit_rolls.meets_or_beats(total, self.pc_ac()))
            self.lines.append(f'Shield: the {name} ' + ('still gets through.' if hit else 'is turned.'))
        elif effect in ('silvery_barbs', 'chronal_shift') or (declared or {}).get('type') in (
                'force_reroll', 'impose_disadvantage'):
            again = self.die(f"{react}:{waiting['attacker']}:r{self.fight['round']}:{waiting['attack_index']}")
            low = effect == 'silvery_barbs' or (declared or {}).get('type') == 'impose_disadvantage'
            new = min(die, again) if low else again
            total = new + (total - die)
            hit = new == 20 or (new != 1 and kit_rolls.meets_or_beats(total, self.pc_ac()))
            dealt = waiting.get('base', dealt) * (2 if new == 20 else 1)
            self.trace.append(f'{react}: reroll d20 {again}, uses {new}: {total} vs AC {self.pc_ac()}')
            self.lines.append(f"The {name} is rerolled: {total}, {'a hit' if hit else 'a miss'}.")
        elif effect == 'absorb_elements':
            dealt //= 2
            self.fight['absorb_bonus'] = {'type': waiting['type'], 'dice': '1d6'}
            self.lines.append(f"Absorb Elements: resistance to the {waiting['type']}; your next melee hit "
                              f"adds 1d6 {waiting['type']}.")
        elif effect == 'uncanny_dodge':
            dealt //= 2
            self.lines.append('Uncanny Dodge: you take half.')
        elif effect in ('deflect_missiles', 'parry') or (declared or {}).get('type') == 'reduce_damage':
            cut = int(self.reaction_roll() or 0)
            before, dealt = dealt, max(0, dealt - cut)
            self.trace.append(f'{react}: reduces {before} by {cut} (the player\'s roll) to {dealt}')
            what = found.get('name', react)
            self.lines.append(f'{what}: you catch it.' if not dealt and effect == 'deflect_missiles' else
                              f'{what}: {before - dealt} less damage.')
            if not dealt:
                hit = False
        elif (declared or {}).get('type') == 'negate_hit':
            hit = False
            self.lines.append(f"{found.get('name', react)}: the {name} misses.")
        elif declared:
            self.apply_declared(react, waiting, waiting['attacker'] if declared['type'] == 'deal_damage' else None)
        self.trace.append(f"reaction {react}: {total} vs AC {self.pc_ac()}: {'hit' if hit else 'miss'}")
        if not hit:
            return
        self.lines.append(f"The {name} hits you: {dealt} {waiting['type']} damage.")
        self.lines.extend(self.hurt_pc(dealt, crit=bool(waiting.get('crit'))))
        if self.fight.get('pc_down'):
            return
        self.after_damage(waiting['attacker'], waiting['attack_index'], waiting.get('ranged'), dealt)
        if waiting.get('rider'):
            # Reaction before damage, then the save the hit carries.
            self.owe_save(waiting['attacker'], waiting['attack_index'], waiting['rider'])

    def after_damage(self, key, index, ranged, dealt, before=None):
        """The damage landed: a reaction that answers being damaged (Hellish Rebuke) opens now, after
        it, never before (SRD trigger), and only while he is up with his reaction unused."""
        if not dealt or not self.pc_can_react() or not self.active(key):
            return
        options = self.fresh(self.options_for(['creature_hits_you_within_range']), 'normal', dealt)
        if options and not self.meaningful(dealt):
            self.unprompted('damaged', options, attacker=key, damage=dealt)
        if options and self.meaningful(dealt):
            if before:
                before()
            self.wait_for('reaction_window', 'player_answer', trigger='damaged', options=options, attacker=key,
                          attack_index=index, damage=dealt, triggers=['creature_hits_you_within_range'],
                          stakes='normal')

    def resume_spell_save(self, waiting, react):
        """A creature saved against the PC's spell and the window let him answer it: the reroll (if
        taken), then every target's damage lands as the spell resolved. The PC is the attacker: a
        reroll that ties his DC fails (Brendon's save rule, kit_rolls.attacker_wins)."""
        results = [list(r) for r in waiting['results']]
        if react != 'decline':
            effect = (kit_reactions.entry(self.resources, react) or {}).get('effect')
            declared = self.declared_effect(react) or {}
            for row in results:
                key, saved, die, bonus = row[0], row[1], row[2], row[3]
                if key != waiting['target'] or die is None:
                    continue
                if effect in ('silvery_barbs', 'chronal_shift') or declared.get('type') in (
                        'force_reroll', 'impose_disadvantage'):
                    again = self.die(f"{react}:save:{key}:r{self.fight['round']}")
                    low = effect == 'silvery_barbs' or declared.get('type') == 'impose_disadvantage'
                    new = min(die, again) if low else again
                    row[1] = not kit_rolls.attacker_wins(int(waiting['dc']), new + bonus)
                    self.trace.append(f'{react}: {key} rerolls the save, d20 {again}, uses {new}: '
                                      f"{'saved' if row[1] else 'failed'}")
                else:
                    self.apply_declared(react, waiting, key)
        damage, half = int(waiting['damage']), bool(waiting.get('half'))
        for key, saved, *_ in results:
            if self.active(key):
                self.apply_damage(key, (damage // 2 if half else 0) if saved else damage, waiting.get('dtype'))
        self.fight['pending'] = None

    # -- the act that came with a window answer (#101 review P1-3): never dropped ----------
    _CLAUSES = re.compile(r'\bthen\b|\n+|(?<=[.!?])\s+(?=[A-Z])')
    _ANSWER_ONLY = re.compile(r"^\W*(?:no|nah|nope|yes|yeah|sure|ok(?:ay)?|pass|decline|skip|"
                              r"(?:i )?let (?:it|him|her|them) (?:hit|land|go|through)|don'?t|not now)\b"
                              r"(?:[\s,.!]*(?:let (?:it|him|her|them) (?:hit|land|go)|i take it|i'?ll take it))?\W*$", re.I)
    _AVRAE_LINE = re.compile(r'^\s*(?:spell slots|an invisible barrier|\+5 ac|you |[^\w]*\d+d\d+|\*\*|meta|effect)',
                             re.I)

    def route_rest(self, waiting, react):
        """Whatever else the player said with the answer ("Shield... then magic missile", a new act
        read as a decline) is his act: on his turn now, else held for it, and he is told."""
        if self.fight.get('declared_next'):
            return
        found = kit_reactions.entry(self.resources, react) or {}
        names = [n for n in (found.get('name', ''), react.replace('_', ' ')) if n and react != 'decline']
        attacking = found.get('effect') in self.ATTACKING
        kept, skipped_attack = [], False
        for part in self._CLAUSES.split(self.action):
            part = (part or '').strip(' ,;')
            if not part or self._AVRAE_LINE.match(part):
                continue
            low = part.casefold()
            if any(n.casefold() in low for n in names) or '!cast' in low:
                continue
            if attacking and not skipped_attack and kit_rolls.attack_total(part) is not None:
                skipped_attack = True  # the reaction's own attack
                continue
            if self._ANSWER_ONLY.match(part):
                continue  # the answer itself ('No, let it hit.')
            act = parse(part, self.source, self.state)
            if act and (act.get('kind') != 'attack' or act.get('spell') or kit_rolls.attack_total(part) is not None
                        or name_target(part, self.source, self.state, self.hostiles())):
                kept.append(part)
        if not kept:
            return
        rest = ' '.join(kept)
        self.fight['declared_next'] = rest
        self.trace.append(f'act with the window answer, held for his turn: {rest[:120]}')

    def after_pc_action(self, acted):
        """What follows the PC's act: the fight may end, a worthy kill hands the floor over (a
        flourish), and the round runs on to the PC's next turn."""
        self.check_over()
        if self.fight and acted:
            self.fight.pop('unprompted', None)  # an unprompted reaction is declared before his own act
        if self.fight and acted and self.fight['status'] in ('running', 'over'):
            worthy = [(key, chosen) for key, chosen in self.kills
                      if (self.status(key) == 'dead' or chosen) and
                      (self.important(key) or self.fight['status'] == 'over')]
            if worthy:
                # The kill (or the knockout the player chose) is committed first; the player owns how
                # it looks, never what happened.
                key = worthy[-1][0]
                self.wait_for('flourish_window', 'player_description', target=key, outcome=self.status(key),
                              deferred='continue_round' if self.fight['status'] == 'running' else 'none')
        if self.fight and (self.fight.get('absorb_bonus') or {}).get('armed') and acted:
            self.fight.pop('absorb_bonus', None)  # only the PC's next turn
        if self.fight and self.fight['status'] == 'running' and acted:
            self.advance_past_pc()
            self.run_npcs()
        elif self.fight and self.fight['status'] == 'awaiting_initiative':
            self.lines.append('Roll initiative.')

    def pc_hp(self):
        return self.sheet.get('hp')

    # -- the PC's act ----------------------------------------------------------------
    def resolve(self, act):
        try:
            self._resolve(act)
        except Checkpoint:
            pass
        try:
            self.declared_turn()  # an act held for his turn runs once it comes (and nothing waits)
        except Checkpoint:
            pass
        self.finish()
        return self.public(), self.events()

    def _resolve(self, act):
        waiting = (self.fight or {}).get('awaiting')
        if waiting and waiting.get('kind') == 'kit_call':
            # Kit's call on the downed PC's foes never came (a host that skipped it): the
            # creatures do what their stat line says (default: they keep attacking).
            choice = self.default_vs_downed(waiting)
            self.trace.append(f'no call on the downed PC: {choice} (default)')
            self.fight['awaiting'] = None
            self.fight['vs_downed'] = choice
            try:
                self.run_npcs()
            except Checkpoint:
                pass  # what the round now waits on is read below
            awaiting = self.fight.get('awaiting')
            if awaiting and awaiting.get('kind') == 'roll_call' and awaiting.get('save') == 'death' and \
                    save_total(self.action, 'death') is not None:
                # A death save counts only once it is owed (#97 review): this one was typed
                # before the foes' blows, which come first in the order. The round waits for
                # a fresh roll at his slot.
                self.lines.append('That death save was rolled before those blows; roll it again now.')
                self.trace.append('early death save not counted: the foes act before his slot')
                return
            if awaiting and not (awaiting.get('kind') == 'roll_call' and
                                 save_total(self.action, awaiting['save']) is not None):
                return
            if awaiting:
                self.resume_save(awaiting)
                self.after_save(awaiting)
                return
        init = kit_rolls.initiative(self.action)
        kind = (act or {}).get('kind')
        waiting = (self.fight or {}).get('awaiting')
        if waiting and waiting['kind'] == 'flourish_window':
            # A new act instead of a description: the flourish is passed, the round runs on.
            self.fight['awaiting'] = None
            if self.fight['status'] == 'running':
                self.advance_past_pc()
                if kind and not self.pc_turn_now():
                    # His action this turn was the kill: the new act is never dropped (#101 review
                    # P1-3, D1). It waits for his next turn, and he is told so.
                    self.fight['declared_next'] = self.action
                    self.trace.append(f'new act with the flourish, held for his turn: {self.action[:120]}')
                    self.lines.append('You have already acted this turn; that waits for your next turn.')
                    self.run_npcs()
                    return
        if kind == 'multi':
            if self.fight['status'] == 'running' and not self.pc_turn_now():
                self.run_npcs()  # whoever acts before the PC in the order
            self.run_clauses(act)
            return
        if kind == 'attack' and not self.hostiles() and not (self.fight and self.fight.get('status') != 'over'):
            # Nobody here to fight (a lurker not yet shown is not a target): no fight starts, and
            # the rest of the message (a feature disturbed) resolves on its own.
            self.trace.append('attack at nobody: no fight')
            return
        if kind == 'attack':
            self.ensure_fight('pc')
        if self.fight and self.fight['status'] == 'awaiting_initiative' and init is not None:
            self.set_order(init)
        if self.fight and self.fight['status'] == 'running' and not self.pc_turn_now():
            self.run_npcs()  # whoever acts before the PC in the order
        acted = False
        if kind == 'attack':
            if self.fight['status'] == 'awaiting_initiative' and self.fight['opener_spent']:
                self.lines.append('Your first blow is already struck; roll initiative before the next one.')
            else:
                if act.get('move_first') and self.pc_turn_now():
                    # 'I back away 30 feet and cast Fire Bolt': the move, then the attack (D5).
                    self.pc_move_away(act['move_first'])
                if self.out_of_reach(act):
                    self.lines.append(f"Your {act.get('weapon') or 'blow'} didn't happen because the "
                                      f"{self.label(act['target'])} is out of your reach now.")
                    acted = True
                else:
                    acted = self.pc_attack(act)
                self.needs_roll = not acted and init is None
                if self.fight['status'] == 'awaiting_initiative' and acted:
                    self.fight['opener_spent'] = True
        elif kind == 'late_reaction':
            self.pc_late_reaction(act)
        elif kind:
            acted = True
            {'grab': self.pc_grab, 'face': self.pc_face, 'flip': self.pc_flip, 'take': self.pc_take,
             'wait': self.pc_wait, 'own_shield': self.pc_own_shield, 'withdraw': self.pc_move_away,
             'approach': self.pc_approach}[kind](act)
        self.after_pc_action(acted)

    def pc_own_shield(self, act):
        """Shield is a reaction to being hit (or targeted by magic missile). Cast on his own turn,
        or after the hit it answers has landed, it has no trigger: it changes nothing, and the slot
        Avrae spent is counted so the session matches Avrae."""
        landed = int(self.fight.get('pc_damage') or 0) > 0
        on_sheet = any(r.get('id') == 'shield' for r in self.resources.get('reactions') or ())
        if not on_sheet:
            self.lines.append("Shield didn't happen because it is not on your sheet.")
            return
        if act.get('avrae') and on_sheet and kit_reactions.free_slot(self.resources, 1):
            self.resources, slot = kit_reactions.spend(self.resources, 'shield')
            self.resources_changed = True
            self.trace.append(f'PC casts Shield with no trigger (own turn): level {slot} slot counted, no effect')
        if landed:
            self.lines.append('That hit has already landed; Shield cannot undo it. It is a reaction to being '
                              'hit, so it does nothing on your own turn.')
        else:
            self.lines.append('Shield is a reaction to being hit; cast on your own turn it does nothing.')

    def pc_move_away(self, act):
        """He moves out of his foes' reach on his turn: each foe in reach may take its opportunity
        attack (none if he disengages), then engagement ends."""
        foes = [key for key in self.hostiles() if self.in_reach(key)]
        self.pc_withdraw('he moves away' + (' (Disengage)' if act.get('disengage') else ''),
                         provoke=not act.get('disengage'))
        self.lines.append('You fall back out of reach.' if foes else 'You move off.')

    def pc_wait(self, act):
        self.lines.append('You hold your ground and wait for them to come to you.')

    def pc_slot(self):
        order = self.fight['order']
        return bool(order) and order[self.fight['next'] % len(order)] == 'pc'

    def pc_cannot_act(self):
        return bool(self.fight.get('pc_down') or self.fight.get('pc_dead') or
                    any(c in INCAPACITATING for c in self.conditions))

    def pc_turn_now(self):
        """The PC's turn, and he can take it (a surprised PC loses his round-one turn; a PC at
        0 hit points or incapacitated takes none: his slot is a death save, or a repeat save)."""
        return self.pc_slot() and not self.pc_surprised_now() and not self.pc_cannot_act()

    def set_order(self, pc_init):
        entries = [('pc', pc_init, 99)]
        for key in self.hostiles():
            bonus = self.stats(key).get('initiative', 0)
            entries.append((key, 10 + bonus, bonus))
        entries.sort(key=lambda e: (-e[1], -e[2]))
        self.fight.update(status='running', order=[e[0] for e in entries], pc_initiative=pc_init,
                          round=1, next=0)
        self.trace.append('initiative: ' + ', '.join(f'{k} {v}' for k, v, _ in entries))
        order_text = ', '.join('you' if k == 'pc' else f'the {self.label(k)}' for k, _, _ in entries)
        self.lines.append(f'Turn order: {order_text}.')
        if self.fight['opener_spent']:
            # The blow declared before initiative was the PC's first action this round.
            index = self.fight['order'].index('pc')
            self.fight['next'] = index
            self.advance_past_pc()

    def advance_past_pc(self):
        order = self.fight['order']
        if not order:
            return
        index = self.fight['next'] % len(order)
        if order[index] == 'pc':
            self.step()

    def step(self):
        order = self.fight['order']
        if self.pc_slot():
            self.end_pc_turn()
        self.fight['next'] += 1
        if self.fight['next'] >= len(order):
            self.fight['next'] = 0
            self.fight['round'] += 1

    def run_npcs(self):
        """Every turn up to the PC's. A surprised PC's round-one turn passes; a save the
        player must roll (a monster's rider, a death save, a repeat save) stops the round until
        he rolls it; foes acting while he is down wait on Kit's call (attack him or turn away)."""
        guard = 0
        while self.fight['status'] == 'running' and not self.pc_turn_now() and \
                not self.fight.get('awaiting') and guard < 24:
            guard += 1
            key = self.fight['order'][self.fight['next']]
            if key == 'pc':
                self.fight['vs_downed'] = None  # a fresh call for the next stretch
                if self.pc_surprised_now():
                    self.lines.append('You are surprised and lose your first turn.')
                    self.trace.append('PC surprised: round 1 turn lost')
                    self.fight['surprise_spent'] = True
                elif not self.pc_slot_passes():
                    break
            elif self.fight.get('pc_down') and self.active(key) and self.fight.get('vs_downed') is None and \
                    not (key in self.fight.get('surprised', []) and self.fight['round'] == 1):
                foes = self.foes_before_pc()
                self.fight['awaiting'] = {'kind': 'kit_call', 'call': 'downed', 'foes': foes}
                self.trace.append(f'the PC is down: Kit calls what {", ".join(foes)} do')
                break
            elif self.active(key):
                self.npc_turn(key)  # may stop at a checkpoint (the order stays on this NPC)
            self.step()
            self.check_over()
        if self.fight['status'] == 'running' and self.pc_turn_now():
            self.start_pc_turn()
        if self.fight['status'] == 'over' and self.dying():
            self.ask_death_save()

    def foes_before_pc(self):
        order, at = self.fight['order'], self.fight['next']
        out = []
        for offset in range(len(order)):
            key = order[(at + offset) % len(order)]
            if key == 'pc':
                break
            if self.active(key):
                out.append(key)
        return out

    def default_vs_downed(self, awaiting=None):
        foes = (awaiting or {}).get('foes') or []
        said = [self.stats(k).get('vs_downed') for k in foes if k in self.config.get('actors', {})]
        return 'turn_away' if said and all(c == 'turn_away' for c in said) else 'attack'

    def dying(self):
        return bool(self.fight.get('pc_down') and not self.fight.get('pc_stable') and not self.fight.get('pc_dead'))

    def ask_death_save(self):
        if not self.fight.get('awaiting'):
            self.fight['awaiting'] = {'kind': 'roll_call', 'awaits': 'player_roll', 'save': 'death'}
            self.lines.append(save_prompt(self.fight['awaiting']))

    def pc_slot_passes(self):
        """The PC's slot when he cannot act. False: it waits on his roll (death save, repeat
        save); True: it passes (stable at 0 hp, or incapacitated with no save to repeat)."""
        if self.fight.get('pc_dead'):
            return False
        if self.dying():
            self.ask_death_save()
            return False
        repeat = self.repeat_save_due()
        if repeat:
            name, save = repeat
            self.fight['awaiting'] = {'kind': 'roll_call', 'awaits': 'player_roll', 'save': save['ability'],
                                      'dc': save['dc'], 'repeat': name, 'damage': 0, 'type': name,
                                      **({'from': save['from']} if save.get('from') else {})}
            self.lines.append(save_prompt(self.fight['awaiting']))
            return False
        why = 'down' if self.fight.get('pc_down') else next(c for c in self.conditions if c in INCAPACITATING)
        self.lines.append('You lie still.' if why == 'down' else f'You are {why} and cannot act.')
        self.trace.append(f'PC turn passes ({why})')
        return True

    def repeat_save_due(self):
        for name in self.conditions:
            save = (self.terms.get(name) or {}).get('save')
            if save and save.get('when') == 'end_of_turn':
                return name, save
        return None

    def end_pc_turn(self):
        """The end of the PC's turn: durations in rounds tick (SRD), the free object
        interaction comes back next turn."""
        self.fight.pop('interaction_used', None)
        for name in list(self.conditions):
            term = self.terms.get(name) or {}
            if 'rounds' in term:
                term['rounds'] = int(term['rounds']) - 1
                if term['rounds'] <= 0:
                    self.remove_condition(name, 'its duration runs out')
                    self.lines.append('The paralysis wears off.' if name == 'paralyzed' else f'You are no longer {name}.')

    # -- the PC's conditions ------------------------------------------------------------
    def add_condition(self, name, term=None):
        if name not in self.conditions:
            self.conditions.append(name)
        term = dict(term or {})
        if 'until_s_in' in term:
            term['until_s'] = int(self.state.get('elapsed_seconds') or 0) + int(term.pop('until_s_in'))
        self.terms[name] = term
        self.conditions_changed = True
        self.trace.append(f'PC {name} ({term or "until it ends by rule"})')

    def remove_condition(self, name, why=''):
        gone = [name] + [n for n in self.conditions if (self.terms.get(n) or {}).get('while') == name]
        for item in gone:
            if item in self.conditions:
                self.conditions.remove(item)
                self.terms.pop(item, None)
                self.conditions_changed = True
        self.trace.append(f'PC {", ".join(gone)} ends{": " + why if why else ""}')

    # -- the PC's hit points (SRD: dropping to 0, death saves, massive damage) ----------
    def hurt_pc(self, dealt, crit=False, at_zero=None):
        """Damage to the PC; lines for what it does. At 0 hit points a hit is a failed death
        save (two on a critical); damage at least his hit point maximum kills outright."""
        hp = self.pc_hp()
        if hp is None:
            self.fight['pc_damage'] += dealt
            return []
        hp = int(hp)
        if self.fight.get('pc_down'):
            if dealt >= hp:
                return self.pc_dies(f'massive damage at 0 hp ({dealt} >= {hp})')
            self.fight['pc_stable'] = False
            return self.death_failures(2 if crit else 1, 'hit at 0 hp' + (' (critical)' if crit else ''))
        left = hp - int(self.fight['pc_damage'])
        self.fight['pc_damage'] += dealt
        if self.fight['pc_damage'] < hp:
            return []
        self.fight['pc_damage'] = hp
        if dealt - left >= hp:
            return self.pc_dies(f'massive damage ({dealt - left} past 0 >= {hp})')
        self.fight['pc_down'] = True
        self.fight['death_saves'] = {'successes': 0, 'failures': 0}
        self.add_condition('unconscious', {'while': 'down'})
        if at_zero:
            for name in at_zero:
                self.add_condition(name, (at_zero_terms(at_zero)).get(name))
            self.fight['pc_stable'] = True
            return [f"You drop, stable but {' and '.join(at_zero)}."]
        self.fight['pc_stable'] = False
        return ['You go down.']

    def death_failures(self, count, why):
        saves = self.fight.setdefault('death_saves', {'successes': 0, 'failures': 0})
        saves['failures'] += count
        self.trace.append(f'death save failure x{count} ({why}): {saves}')
        if saves['failures'] >= 3:
            return self.pc_dies('three failed death saves')
        return [f"That is {saves['failures']} failed death save{'s' if saves['failures'] != 1 else ''}."]

    def pc_dies(self, why):
        self.fight.update(pc_dead=True, pc_down=True, pc_stable=False, awaiting=None, status='over')
        self.fight.pop('saves_queued', None)
        self.trace.append(f'PC dies: {why}')
        return ['You die.']

    def revive(self, hit_points, why):
        """Healing at 0 hit points: he comes to (SRD), death saves reset."""
        hp = int(self.pc_hp() or 0)
        self.fight['pc_damage'] = max(0, hp - int(hit_points)) if hp else 0
        self.fight.update(pc_down=False, pc_stable=False, death_saves={'successes': 0, 'failures': 0})
        if (self.fight.get('awaiting') or {}).get('save') == 'death' or \
                (self.fight.get('awaiting') or {}).get('kind') == 'kit_call':
            self.fight['awaiting'] = None
        self.fight['vs_downed'] = None
        if 'unconscious' in self.conditions and (self.terms.get('unconscious') or {}).get('while') == 'down':
            self.remove_condition('unconscious', why)
        self.trace.append(f'PC revived with {hit_points} hp ({why})')

    def heal(self, amount, why, own_action=False):
        """Hit points regained (a potion, an ally's spell, an effect): the amount the player
        reports from Avrae. Healing at 0 hit points revives him."""
        if not self.fight:
            self.lines.append('You are not hurt.')
            return False
        if self.fight.get('pc_dead'):
            self.lines.append('You are dead; healing does not bring you back.')
            return False
        if self.fight.get('pc_down'):
            self.revive(amount, why)
            self.lines.append(f'You come to with {amount} hit point{"s" if amount != 1 else ""}.')
        else:
            before = int(self.fight.get('pc_damage') or 0)
            self.fight['pc_damage'] = max(0, before - int(amount))
            self.lines.append(f'You regain {before - self.fight["pc_damage"]} hit points.')
            self.trace.append(f'PC heals {amount} ({why})')
        if own_action and self.fight['status'] == 'running':
            if self.pc_turn_now():
                self.advance_past_pc()
                try:
                    self.run_npcs()
                except Checkpoint:
                    pass
        self.finish()
        return True

    def resume_downed(self, choice):
        """Kit's call on the foes acting while the PC is down (runtime/kit_acts.py downed)."""
        awaiting = self.fight.get('awaiting') or {}
        if awaiting.get('kind') == 'kit_call':
            self.fight['awaiting'] = None
        self.fight['vs_downed'] = choice
        self.trace.append(f'Kit: the foes {"attack the downed PC" if choice == "attack" else "turn away from him"}')
        if choice == 'turn_away' and self.fight.get('pc_stable'):
            for key in self.foes_before_pc():
                self.lines.append(f'The {self.label(key)} leaves you where you fell.')
            self.fight['status'] = 'over'
            self.fight['ended'] = 'foes turned from the downed PC'
            self.trace.append('fight over: nobody fights a stable, downed PC')
        else:
            try:
                self.run_npcs()
            except Checkpoint:
                pass
        self.finish()
        return self.public(), self.events()

    # -- a save the player rolls (a monster attack's rider) ---------------------------
    def owe_save(self, key, index, rider):
        """Stop at a roll call: the player rolls his own save in Avrae (never shown the DC).
        Order with a reaction window: the reaction first (before damage), then the save."""
        self.lines.append(save_prompt({'save': rider['ability']}))
        self.wait_for('roll_call', 'player_roll', trigger='save_rider', save=rider['ability'], dc=rider['dc'],
                      damage=rider.get('damage', 0), type=rider.get('type', 'poison'), half=bool(rider.get('half')),
                      at_zero=list(rider.get('at_zero') or ()), attacker=key, attack_index=index,
                      **({'condition': rider['condition']} if rider.get('condition') else {}))

    def resume_save(self, waiting):
        """The player's save total answers the roll call; the rider's damage lands or not. Anything he
        declared with it ('Con save 14, then I cast magic missile') waits for his turn (declared_next)."""
        total = save_total(self.action, waiting['save'])
        if total is None:
            command = '!g ds' if waiting['save'] == 'death' else f"!save {waiting['save']}"
            raise Unclear(f"{save_prompt(waiting)[:-1]} in Avrae first ({command}). "
                          'No turn was committed.')
        if waiting['save'] == 'death':
            return self.resume_death(total)
        if waiting.get('repeat'):
            return self.resume_repeat(waiting, total)
        # Brendon's save rule: the attacker meets or beats, so a save that ties the DC fails.
        saved = not kit_rolls.attacker_wins(waiting['dc'], total)
        self.fight['awaiting'] = None
        if not saved and self.pc_can_react():
            # A failed save a reaction can answer (Ring of Evasion, Lucky Footwork: Dex saves).
            options = self.fresh(self.options_for(
                ['self_fails_save'], fit=lambda r: not r.get('save_only') or r['save_only'] == waiting['save']),
                'normal')
            if options:
                self.lines.append(f"{save_prompt(waiting)[len('Roll a '):-1].capitalize()}: {total}, a failure.")
                self.wait_for('reaction_window', 'player_answer', trigger='pc_save', options=options,
                              save=waiting['save'], dc=waiting['dc'], total=total, save_call=dict(waiting),
                              triggers=['self_fails_save'], stakes='normal',
                              **({'attacker': attacker(waiting)} if attacker(waiting) else {}))
        self.land_save(waiting, saved, total)

    def land_save(self, waiting, saved, total):
        """The save's outcome: the rider's damage and condition land, or not."""
        damage = int(waiting['damage'])
        dealt = (damage // 2 if waiting.get('half') else 0) if saved else damage
        self.trace.append(f"PC {waiting['save']} save {total} vs DC {waiting['dc']} "
                          f"({attacker(waiting)}): {'saved' if saved else 'failed'}, {dealt} {waiting['type']}")
        condition = waiting.get('condition')
        immune = condition and any(str(word).casefold() in str(self.sheet.get('ancestry') or '').casefold()
                                   for word in condition.get('immune') or ())
        if condition and not saved and not immune:
            term = {'rounds': int(condition['rounds'])} if condition.get('rounds') else {}
            if condition.get('repeat') == 'end_of_turn':
                term['save'] = {'ability': waiting['save'], 'dc': int(waiting['dc']), 'when': 'end_of_turn',
                                **({'from': attacker(waiting)} if attacker(waiting) else {})}
            self.add_condition(condition['name'], term)
            self.lines.append(f"You are {condition['name']}.")
        elif condition:
            self.lines.append(f"You shake off the {condition['name'] if condition['name'] != 'paralyzed' else 'paralysis'}.")
        if not dealt and not condition:
            self.lines.append(f"You shake off the {waiting['type']}.")
        elif dealt:
            self.lines.append(f"You {'resist some of' if saved else 'fail to resist'} the {waiting['type']}: "
                              f"{dealt} {waiting['type']} damage.")
            # Conditions live on the PC, not the fight: they outlast it (runtime state).
            self.lines.extend(self.hurt_pc(dealt, at_zero=waiting.get('at_zero')))
        rest = after_save_clause(self.action) or self.fight.get('declared_next') or ''
        self.fight.pop('declared_next', None)
        if rest:
            self.fight['declared_next'] = rest
        queued = list(self.fight.get('saves_queued') or ())
        if queued and not self.fight.get('pc_down'):
            # A save queued behind this one (a #97-era save): asked next, one at a time.
            self.fight['awaiting'] = queued.pop(0)
            self.fight['saves_queued'] = queued
            self.lines.append(save_prompt(self.fight['awaiting']))
            raise Checkpoint()
        self.fight.pop('saves_queued', None)

    def after_save(self, waiting):
        """The round runs on from the attack whose rider was saved against."""
        who = attacker(waiting)  # #97-era prompts say "from", #101's "attacker"
        if not self.fight.get('pc_down') and who and waiting.get('attack_index') is not None:
            self.npc_turn(who, start=waiting['attack_index'] + 1)
        self.step()
        self.check_over()
        self.run_npcs()

    def declared_turn(self):
        """What the player declared with a save ('..., then I cast magic missile') is his act when
        his turn comes and nothing else waits."""
        rest = (self.fight or {}).get('declared_next')
        if not rest or self.fight['status'] != 'running' or self.fight.get('pc_down') or \
                self.fight.get('awaiting') or not self.pc_turn_now():
            return
        self.fight.pop('declared_next', None)
        follow = parse(rest, self.source, self.state)
        if follow:
            self.trace.append(f'his declared act after the save: {rest[:120]}')
            self.action = rest
            self._resolve(follow)

    def resume_death(self, roll):
        """His death save (rolled in Avrae, reported): 10 or more succeeds (no attacker, so no
        tie rule), a 1 is two failures, a 20 brings him back with 1 hit point. Three successes:
        stable; three failures: dead. Then his turn passes."""
        self.fight['awaiting'] = None
        saves = self.fight.setdefault('death_saves', {'successes': 0, 'failures': 0})
        if roll >= 20:
            self.revive(1, 'natural 20 on a death save')
            self.lines.append('Natural 20: you come to with 1 hit point.')
            return
        if roll <= 1:
            self.lines.extend(self.death_failures(2, 'natural 1 on a death save'))
        elif roll >= 10:
            saves['successes'] += 1
            self.trace.append(f'death save {roll}: success ({saves})')
            if saves['successes'] >= 3:
                self.fight['pc_stable'] = True
                self.fight['death_saves'] = {'successes': 0, 'failures': 0}
                self.lines.append('You are stable.')
            else:
                self.lines.append(f"Death save {roll}: {saves['successes']} success"
                                  f"{'es' if saves['successes'] != 1 else ''}, {saves['failures']} failure"
                                  f"{'s' if saves['failures'] != 1 else ''}.")
        else:
            self.lines.extend(self.death_failures(1, f'death save {roll}'))
        if self.fight.get('pc_dead'):
            return
        if self.fight['status'] == 'running':
            if self.pc_slot():
                self.step()
            self.run_npcs()
        elif self.dying():
            self.ask_death_save()

    def resume_repeat(self, awaiting, total):
        """The save he repeats at the end of his turn against a condition (the ghoul's
        paralysis): beating the DC ends it (a tie is the attacker's)."""
        self.fight['awaiting'] = None
        name = awaiting['repeat']
        if not kit_rolls.attacker_wins(awaiting['dc'], total):
            self.remove_condition(name, f'repeat save {total} vs DC {awaiting["dc"]}')
            self.lines.append(f"You shake off the {'paralysis' if name == 'paralyzed' else name}.")
        else:
            self.trace.append(f'repeat save {total} vs DC {awaiting["dc"]}: still {name}')
            self.lines.append(f'You are still {name}.')
        if self.fight['status'] == 'running':
            if self.pc_slot():
                self.step()
            self.run_npcs()

    def check_over(self):
        if self.fight and self.fight['status'] != 'over' and not self.hostiles():
            self.fight['status'] = 'over'
            self.lines.append('Nobody is left in the room to fight you.')
            self.trace.append('fight over')

    # -- attacks ---------------------------------------------------------------------
    def pc_attack(self, act):
        """True when the blow resolved (it counts as the PC's action)."""
        spell = act.get('spell')
        weapon = act.get('weapon') or 'attack'
        targets = self.hostiles() if act.get('area') else [act['target']] if act.get('target') else []
        targets = [key for key in targets if key and self.active(key)]
        damage, dtype = kit_rolls.damage_total(self.action)
        dtype = dtype or ('fire' if spell else None)
        posted = kit_rolls.avrae(self.action) or {}
        if not targets:
            self.lines.append('There is nobody there to hit.')
            return True
        self.fight['last_target'] = targets[0]
        if spell in SPELL_SAVE:
            dc = posted.get('dc') or self.sheet.get('spell_save_dc') or _derived_save_dc(self.sheet)
            if dc is None:
                self.fight['pending'] = {'kind': 'attack', 'target': targets[0], 'weapon': weapon, 'needs': 'save_dc'}
                self.lines.append(f'Your {spell.title()} needs your spell save DC from your sheet; say it and it lands.')
                return False
            if not damage:
                self.fight['pending'] = {'kind': 'attack', 'target': targets[0], 'weapon': weapon, 'needs': 'damage',
                                         'spell': spell, 'area': act.get('area')}
                self.lines.append(f'Roll the {spell.title()} damage in Avrae.')
                return False
            ability, half, _ = SPELL_SAVE[spell]
            hits, rows = [], []
            # Avrae's own per-target results count when a target there is one of these NPCs.
            posted_targets = {}
            for name, result in (posted.get('targets') or {}).items():
                key = name_target(name, self.source, self.state, targets)
                if key:
                    posted_targets[key] = result
            for key in targets:
                result = posted_targets.get(key) or {}
                if result.get('save') and (result['save'][2] is not None or result['save'][1] is not None):
                    # The tie is the attacker's (Brendon): with the total and the DC known the
                    # engine decides, not Avrae's own success line.
                    saved = not kit_rolls.attacker_wins(dc, result['save'][1]) if result['save'][1] is not None \
                        else result['save'][2]
                    dealt = result['damage'][0] if result.get('damage') else \
                        ((damage // 2 if half else 0) if saved else damage)
                    if result['save'][2] is True and not saved:
                        # Avrae counted a tie as a save (5e); at this table the tie fails: the
                        # full damage (Avrae's half, doubled, when that is all it showed).
                        # The full rolled total (the dice Avrae shows), never Avrae's half
                        # doubled: that loses 1 on an odd total (#97 review P2).
                        shown = result['damage'][0] if result.get('damage') else damage
                        dealt = (unhalved_damage(self.action, shown) or shown * 2) if half else damage
                        self.trace.append(f'{key} tied the DC: Avrae said saved, the table rule says failed')
                    self.trace.append(f'{key} {ability} save from Avrae: {result["save"][1]} '
                                      f'{"saved" if saved else "failed"}, {dealt} damage')
                    hits.append((key, dealt))
                    rows.append([key, saved, None, None])
                    continue
                bonus = self.stats(key).get('saves', {}).get(ability)
                if bonus is None:
                    bonus = _mod(((self.state['actors'][key].get('stats') or {}).get('abilities') or {}).get(ability, 10))
                die = self.die(f'save:{key}:{spell}')
                saved = not kit_rolls.attacker_wins(dc, die + bonus)  # a tie is the PC's (the attacker)
                dealt = (damage // 2 if half else 0) if saved else damage
                self.trace.append(f'{key} {ability} save d20 {die} + {bonus} vs DC {dc}: '
                                  f'{"saved" if saved else "failed"}, {dealt} damage')
                hits.append((key, dealt))
                rows.append([key, saved, die, bonus])
            self.spend_own_slot(spell)
            saver = next((row[0] for row in rows if row[1] and row[2] is not None), None)
            options = self.fresh(self.options_for(['creature_succeeds']), 'normal') if saver else []
            if options:
                # A creature the PC can see succeeded on a save against his spell: a reroll may answer it
                # (Silvery Barbs, Chronal Shift). The spell's damage waits on the answer.
                self.lines.append(f'Your {spell.title()} {"bursts over them" if act.get("area") else "takes hold"}; '
                                  f'the {self.label(saver)} resists it.')
                self.wait_for('reaction_window', 'player_answer', trigger='npc_save', options=options, target=saver,
                              results=rows, damage=damage, half=half, dtype=dtype, dc=int(dc), spell=spell,
                              triggers=['creature_succeeds'], stakes='normal')
            self.lines.append(f'Your {spell.title()} {"bursts over the table" if act.get("area") else "takes hold"}.')
            for key, dealt in hits:
                self.apply_damage(key, dealt, dtype)
            self.fight['pending'] = None
            return True
        total = kit_rolls.attack_total(self.action)
        natural = next((roll.die for roll in kit_rolls.rolls(self.action) if roll.label == 'attack'), None)
        pending = self.fight.get('pending') if isinstance(self.fight.get('pending'), dict) else None
        if total is None and spell not in SPELL_AUTO:
            if pending and pending.get('needs') == 'damage' and damage:
                self.apply_damage(pending['target'], damage, dtype)
                self.fight['pending'] = None
                return True
            self.fight['pending'] = {'kind': 'attack', 'target': targets[0], 'weapon': weapon, 'needs': 'attack'}
            what = 'stomp' if weapon == 'stomp' else spell.title() if spell else weapon
            self.lines.append(f'Roll the attack for your {what} in Avrae, with its damage.')
            return False
        key = targets[0]
        if spell:
            self.spend_own_slot(spell)
        self.melee(key, weapon)  # melee blows engage (default, no room data needed)
        ac = self.stats(key)['ac']
        hit = spell in SPELL_AUTO or natural == 20 or (natural != 1 and kit_rolls.meets_or_beats(total, ac))
        self.trace.append(f'PC {weapon} vs {key}: {total} vs AC {ac}: {"hit" if hit else "miss"}')
        what = 'stomp' if weapon == 'stomp' else spell.title() if spell else weapon
        if not hit:
            self.lines.append(f'Your {what} misses the {self.label(key)}.')
            self.fight['pending'] = None
            return True
        if not damage:
            self.fight['pending'] = {'kind': 'attack', 'target': key, 'weapon': weapon, 'needs': 'damage'}
            self.lines.append(f'Your {what} hits the {self.label(key)}. Roll damage in Avrae.')
            return True
        self.lines.append(f'Your {what} hits the {self.label(key)}.')
        self.apply_damage(key, damage, dtype, nonlethal=act.get('nonlethal'))
        self.fight['pending'] = None
        bonus = self.fight.get('absorb_bonus') or {}
        if bonus.get('armed') and not spell and not RANGED.search(str(weapon)):
            # Absorb Elements: the first melee hit on the PC's next turn adds 1d6 of the absorbed type.
            self.fight.pop('absorb_bonus', None)
            if bonus['type'] not in self.action.casefold():
                self.fight['pending'] = {'kind': 'attack', 'target': key, 'weapon': weapon, 'needs': 'damage',
                                         'type': bonus['type'], 'absorb': True}
                self.lines.append(f"Absorb Elements adds {bonus['dice']} {bonus['type']} to this hit: roll it in Avrae.")
            self.trace.append(f"absorb elements: +{bonus['dice']} {bonus['type']} on this melee hit")
        return True

    def spend_own_slot(self, spell):
        """A leveled spell the PC cast on his turn uses a slot (his Avrae cast is the truth; the engine
        keeps the session count from the sheet). An unknown level spends nothing and says so."""
        known = kit_reactions.spells(self.sheet).get(kit_reactions.ident(spell)) or {}
        if not known.get('level'):
            self.trace.append(f'{spell}: no slot level on the sheet, none counted')
            return
        self.resources, slot = kit_reactions.spend_slot(self.resources, known['level'])
        self.resources_changed = True
        self.trace.append(f'{spell}: level {slot} slot used' if slot else f'{spell}: no slot left by the count')

    def melee(self, key, weapon):
        if weapon and not RANGED.search(str(weapon)) and weapon not in SPELLS:
            self.engage(key)

    def apply_damage(self, key, amount, dtype=None, nonlethal=False):
        if amount <= 0:
            self.lines.append(f'The {self.label(key)} comes through it unhurt.')
            return
        hp = self.fight['hp']
        hp[key] = max(0, hp[key] - amount)
        self.trace.append(f'{key} takes {amount} {dtype or ""} damage: {hp[key]}/{self.fight["max_hp"][key]} hp')
        if hp[key] == 0:
            status = 'unconscious' if nonlethal else 'dead'
            self.statuses[key] = status
            self.kills.append((key, bool(nonlethal)))  # (who, a knockout the player chose)
            self.lines.append(f'The {self.label(key)} goes down and does not get up.' if status == 'dead' else
                              f'The {self.label(key)} drops, out cold.')
        elif hp[key] <= self.fight['max_hp'][key] // 2:
            self.lines.append(f'The {self.label(key)} is badly hurt.')
        else:
            self.lines.append(f'The {self.label(key)} is hurt.')
        self.crack('fire' if dtype == 'fire' else 'blood', key)

    def npc_turn(self, key, start=0, cast_answered=False):
        """The NPC's attacks from ``start`` (a resumed turn after a reaction window). An attack the
        stat block marks ``"spell": true`` is a spell cast first (Counterspell, Mage Slayer)."""
        stats = self.stats(key)
        if start == 0:
            if key in self.fight.get('surprised', []) and self.fight['round'] == 1:
                self.lines.append(f'The {self.label(key)} is still reeling.')
                return
            if self.should_retreat(key):
                options = self.opportunity_options(key)
                if options:
                    self.lines.append(f'The {self.label(key)} breaks away, leaving your reach.')
                    self.wait_for('reaction_window', 'player_answer', trigger='leaves_reach', actor=key,
                                  options=options, triggers=['foe_leaves_reach'], stakes='normal')
                self.flee(key)
                return
        if self.fight.get('pc_dead'):
            return
        down = bool(self.fight.get('pc_down'))
        if down and self.fight.get('vs_downed') == 'turn_away':
            self.lines.append(f'The {self.label(key)} leaves you where you fell.')
            self.trace.append(f'{key} turns away from the downed PC (Kit)')
            return
        helpless = down or any(c in ADVANTAGE_AGAINST for c in self.conditions)
        attacks = stats.get('attacks') or []
        if start >= len(attacks):
            return
        hits, misses, after = [], 0, []
        who = f'The {self.label(key)}'

        def say_so_far(swings):
            if hits:
                self.say_hits(who, hits, swings)
            self.lines.extend(after)
            after.clear()

        for index in range(start, len(attacks)):
            attack = attacks[index]
            if attack.get('spell') and not (cast_answered and index == start) and self.pc_can_react() \
:
                options = self.fresh(self.options_for(
                    ['spell_cast_within_range'],
                    fit=lambda r: r['effect'] != 'mage_slayer' or self.in_reach(key)), 'normal')
                if options:
                    say_so_far(2)
                    self.lines.append(f"{who} begins casting: {attack['name']}.")
                    self.wait_for('reaction_window', 'player_answer', trigger='npc_spell', options=options,
                                  attacker=key, attack_index=index, name=attack['name'],
                                  level=attack.get('level'), triggers=['spell_cast_within_range'], stakes='normal')
            die = self.die(f'npc:{key}:r{self.fight["round"]}:{index}')
            if helpless:
                die = max(die, self.die(f'npc:{key}:r{self.fight["round"]}:{index}:advantage'))
            total = die + attack['to_hit']
            ac = self.pc_ac()
            missile = bool(attack.get('auto_hit'))  # magic missile: no roll, Shield blocks it
            hit = missile or die == 20 or (die != 1 and kit_rolls.meets_or_beats(total, ac))
            ranged = bool(RANGED.search(attack['name']) or attack.get('ranged'))
            crit = not missile and (die == 20 or (hit and not ranged and
                                                  (down or any(c in AUTO_CRIT for c in self.conditions))))
            dealt = attack['damage'] * (2 if crit else 1)
            self.trace.append(f'{key} {attack["name"]}: d20 {die}{" (advantage)" if helpless else ""} + '
                              f'{attack["to_hit"]} = {total} vs AC {ac}: '
                              f'{("crit " if crit else "hit ") + str(dealt) if hit else "miss"}')
            if not ranged:
                self.engage(key)  # a melee attack on the PC: they are in each other's reach
            if not hit:
                misses += 1
                if not ranged and not missile and self.pc_can_react():
                    # A melee miss: Riposte (or a reaction whose text answers one) opens after it.
                    options = self.fresh(self.options_for(['missed_by_melee']), 'normal')
                    if options:
                        say_so_far(2)
                        self.lines.append(f"{who}'s {attack['name']} misses you.")
                        self.wait_for('reaction_window', 'player_answer', trigger='missed', options=options,
                                      attacker=key, attack_index=index, triggers=['missed_by_melee'],
                                      stakes='normal')
                continue
            stakes = 'drop' if self.pc_hp() is not None and not down and \
                self.fight['pc_damage'] + dealt >= int(self.pc_hp()) else 'normal'
            triggers = self.hit_triggers(attack, missile)
            options = [] if not self.pc_can_react() else self.fresh(
                self.options_for(triggers, fit=lambda r: self.turns_hit(r, die, total, ac, attack, missile, dealt,
                                                                         stakes)),
                stakes, dealt, attack.get('type'))
            eligible = [] if not self.pc_can_react() else self.fresh(
                self.options_for(triggers, fit=lambda r: self.turns_hit(r, die, total, ac, attack, missile, dealt,
                                                                         stakes, need_worth=False)),
                stakes, dealt, attack.get('type'))
            if not options and eligible:
                self.unprompted('hit', eligible, attacker=key, damage=dealt, type=attack.get('type'),
                                name=attack['name'])
            if options:
                say_so_far(2)
                self.lines.append(f"{who}'s {attack['name']} comes at you: {'it never misses' if missile else f'that is a {total}, a hit'}.")
                self.wait_for('reaction_window', 'player_answer', trigger='hit', options=options, attacker=key,
                              attack_index=index, die=die, total=total, damage=dealt, base=attack['damage'],
                              eligible=[e for e in eligible if e not in options],
                              type=attack.get('type'), name=attack['name'], triggers=triggers, stakes=stakes,
                              crit=crit, ranged=ranged, **({'magic_missile': True} if missile else {}),
                              **({'rider': attack['save']} if attack.get('save') else {}))
            hits.append((dealt, attack['type']))
            was_down = bool(self.fight.get('pc_down'))
            after.extend(self.hurt_pc(dealt, crit=crit))
            if self.fight.get('pc_dead') or (self.fight.get('pc_down') and not was_down):
                break
            if not self.fight.get('pc_down'):
                self.after_damage(key, index, ranged, dealt,
                                  before=lambda: (say_so_far(1 if len(attacks) == 1 else 2), hits.clear()))
            if attack.get('save') and not was_down:
                say_so_far(1 if len(attacks) == 1 else 2)
                hits.clear()
                self.owe_save(key, index, attack['save'])
        swings = len(attacks) - start
        if start and not hits and not after:
            self.lines.append(f"{who}'s other {'attack misses' if swings == 1 else 'attacks miss'}.")
        else:
            self.say_hits(who, hits, swings if not start else 2)
        self.lines.extend(after)

    def say_hits(self, who, hits, swings):
        if not hits:
            self.lines.append(f'{who} {"attacks and misses" if swings == 1 else "swings at you and misses every time"}.')
            return
        count = {1: 'once', 2: 'twice'}.get(len(hits), f'{len(hits)} times')
        by_type = {}
        for dealt, dtype in hits:
            by_type[dtype] = by_type.get(dtype, 0) + dealt
        amounts = ' and '.join(f'{amount} {dtype}' for dtype, amount in by_type.items())
        self.lines.append(f'{who} hits you {count}: {amounts} damage.' if swings > 1 else
                          f'{who} hits you: {amounts} damage.')

    def hit_triggers(self, attack, missile):
        """The typed events one NPC hit is: an attack that hit (a creature succeeding on an attack
        roll), elemental damage, a ranged weapon hit, being damaged by a creature in range."""
        if missile:
            return ['self_targeted_by_magic_missile']
        # Being damaged (Hellish Rebuke) is its own window, after the damage lands (after_damage).
        out = ['self_hit_by_attack', 'creature_succeeds']
        if not (RANGED.search(attack['name']) or attack.get('ranged')):
            out.append('damaged_by_melee')  # Parry
        if attack.get('type') in ELEMENTS:
            out.append('elemental_damage_taken')
        if RANGED.search(attack['name']) or attack.get('ranged'):
            out.append('self_hit_by_ranged_weapon')
        return out

    def turns_hit(self, entry, die, total, ac, attack, missile, dealt=0, stakes='normal', need_worth=True):
        """Whether offering this reaction can change the outcome now (#101 review pacing): Shield only
        when +5 AC turns it (never a natural 20) or it is a magic missile; a reroll only on a hit worth
        one (it would drop him, or it is meaningful) and never a natural 20 Silvery Barbs cannot
        undo; a halving reaction only when half no longer drops him and the hit matters."""
        effect = entry['effect']
        hp = int(self.pc_hp() or 0)
        left = hp - int(self.fight.get('pc_damage') or 0) if hp else None
        worth = not need_worth or stakes == 'drop' or self.meaningful(dealt)
        if effect == 'shield':
            return missile or (die != 20 and total < ac + 5)
        if effect == 'absorb_elements':
            return attack.get('type') in ELEMENTS and worth and (left is None or dealt // 2 < left or stakes != 'drop')
        if effect in ('uncanny_dodge',):
            return worth and (left is None or dealt // 2 < left)
        if effect in ('silvery_barbs', 'chronal_shift'):
            return worth and not missile
        if effect in ('deflect_missiles',):
            return bool(RANGED.search(attack['name']) or attack.get('ranged')) and not missile
        if effect == 'parry':
            return worth
        return worth

    def opportunity_options(self, key):
        """The reactions a foe leaving the PC's reach opens (the opportunity attack, Sentinel...):
        he is up, not surprised, his reaction unused, and the foe was in melee reach."""
        if not self.pc_can_react() or not self.in_reach(key) or self.pc_hp() is None:
            return []
        return self.fresh(self.options_for(['foe_leaves_reach']), 'normal')

    def can_opportunity(self, key):
        """A foe leaving the PC's reach: the PC's reaction is unused and they are up."""
        return (not self.fight.get('reaction_used') and self.pc_can_react() and
                self.in_reach(key) and self.pc_hp() is not None)

    def should_retreat(self, key):
        rule = self.stats(key).get('retreat') or {}
        when = rule.get('when') or ()
        hp, max_hp = self.fight['hp'], self.fight['max_hp']
        if 'damaged' in when and hp.get(key, 0) < max_hp.get(key, 0):
            return True
        if 'underling_down' in when and any(self.status(u) in ('dead', 'unconscious')
                                            for u in self.config.get('underlings', ()) if u in self.state['actors']):
            return True
        leader = self.config.get('leader')
        if 'leader_gone' in when and leader and self.status(leader) != 'alive':
            return True
        return False

    def flee(self, key):
        rule = self.stats(key).get('retreat') or {}
        self.statuses[key] = 'fled'
        self.fled_toward = getattr(self, 'fled_toward', {})
        self.fled_toward[key] = rule.get('toward')
        self.lines.append(rule.get('text') or f'The {self.label(key)} runs.')
        if self.scene.get('grappled') == key:
            self.scene['grappled'] = None
        if (self.config.get('loose_money') or {}).get(key, {}).get('does') == 'take_ring' and \
                self.scene.get('ring') in ('on_table', 'floor', key):
            self.scene['ring'] = f'gone with the {self.label(key)}'
        self.trace.append(f'{key} flees toward {rule.get("toward")}')
        self.crack('flee', key)

    # -- other physical acts ---------------------------------------------------------------
    def pc_grab(self, act):
        key = act['target']
        if not key:
            self.lines.append('There is nobody within reach to grab.')
            return
        dc = 10 + self.stats(key).get('grapple', 0)
        result = self.check('athletics', dc, f'grab:{key}')
        self.trace.append(f'grab {key}: {result}')
        self.scene['provocations'] += 1
        if not result['success']:
            self.lines.append(f'The {self.label(key)} twists out of your grip.')
            return
        self.scene['grappled'] = key
        where = 'by the wrist' if act.get('wrist') else 'by the collar'
        self.lines.append(f'You have the {self.label(key)} {where}, and he cannot pull free.')
        if act.get('teeth'):
            self.crack('teeth', key)

    def pc_face(self, act):
        key = act['target']
        if not key:
            return
        self.scene['provocations'] += 1
        self.lines.append(f'Your hand reaches the {self.label(key)}\'s face before he can stop it.')
        self.crack('teeth' if act.get('teeth') else 'face', key)

    def pc_flip(self, act):
        if self.scene['table'] == 'overturned':
            self.lines.append('The table is already on its side.')
            return
        self.scene.update(table='overturned', pot='scattered on the floor',
                          ring='floor' if self.scene.get('ring') == 'on_table' else self.scene.get('ring'))
        self.scene['provocations'] += 1
        self.lines.append('The table goes over with a crash. Cards, coins, and the silver ring spill across the floor.')
        for key, instinct in (self.config.get('loose_money') or {}).items():
            if key.startswith('_') or key not in self.state['actors'] or not self.active(key):
                continue
            self.lines.append(instinct['text'])
            if instinct['does'] == 'grovel':
                self.scene['grovelling'] = key
                self.crack('grovel', key)
            elif instinct['does'] == 'take_ring' and self.scene.get('ring') == 'floor':
                self.scene['ring'] = key
        self.trace.append('table overturned; pot scattered')

    def pc_take(self, act):
        what = act['what']
        watchers = [key for key in self.hostiles()]
        loot = 'the silver ring' if what == 'ring' else ('a handful of the table coins' if act.get('handful')
                                                         else 'the table coins')
        if what == 'ring' and self.scene.get('ring') not in ('on_table', 'floor'):
            self.lines.append('The ring is not there to take.')
            return
        if not watchers:
            self.take(loot, what)
            self.lines.append(f'You take {loot}.')
            return
        best = max(_passive_perception(self.state['actors'][key]) for key in watchers)
        result = self.check('sleight_of_hand', best, 'take')
        self.trace.append(f'take {what}: {result}')
        seen = not (act.get('covert') and result['success'])
        if result['success']:
            self.take(loot, what)
            self.lines.append(f'You come away with {loot}.')
        else:
            loot = 'a few coins' if what == 'coins' else None
            if loot:
                self.take(loot, what)
            self.lines.append('A hand slaps down over the pot before you get much: ' + (
                'you come away with a few coins.' if loot else 'the ring stays where it was.'))
        self.scene['provocations'] += 1
        if seen:
            self.lines.append('That is the line they will not let go: chairs scrape back and blades come out.')
            if self.ensure_fight('npcs'):
                pass

    def take(self, loot, what):
        self.scene['pc_took'] = (self.scene['pc_took'] + [loot])[-12:]
        if what == 'ring':
            self.scene['ring'] = 'you'
        elif self.scene.get('pot') == 'on_table':
            self.scene['pot'] = 'on_table, short what you took'

    # -- the act --------------------------------------------------------------------
    def crack(self, cause, key):
        act = self.config.get('act') or {}
        if self.scene.get('act') == 'cracked' or not act:
            return
        known = self.state.get('known_facts') or []
        texts = act.get('cracks') or {}
        text = texts.get(cause)
        if cause == 'flee':
            return  # running is not proof; it only follows a crack or a wound here
        if not text:
            return
        self.scene.update(act='cracked', cracked_by=cause)
        self.lines.append(text)
        if act.get('fact') and act['fact'] not in known:
            self.reveals.append(act['fact'])
        self.trace.append(f'the act cracks: {cause} ({key})')

    # -- output ---------------------------------------------------------------------
    def finish(self):
        if self.fight and self.fight['status'] != 'running' and self.fight.get('declared_next'):
            # The fight ended before his held act came up: say so rather than drop it silently.
            held = self.fight.pop('declared_next')
            self.trace.append(f'held act moot, the fight is over: {held[:120]}')
            self.lines.append('The fight is over before your held act comes up, so it does not happen.')
        if self.fight and self.fight['status'] == 'running':
            order = self.fight['order']
            if order and self.pc_turn_now() and not self.fight.get('awaiting'):
                self.lines.append('Your turn.')

    def public(self):
        return ' '.join(line for line in self.lines if line).strip()

    def events(self):
        evidence = f'Player declared: {self.action[:300]}. ' + ('; '.join(self.trace) or 'physical act') + '.'
        events = [{'type': 'scene_state', 'state': self.scene, 'evidence': evidence}]
        if self.fight:
            events.append({'type': 'combat_state', 'state': self.fight, 'evidence': evidence})
        if self.resources_changed:
            events.append({'type': 'pc_resources', 'resources': self.resources, 'evidence': evidence})
        if self.conditions_changed:
            events.append({'type': 'pc_conditions', 'conditions': list(self.conditions),
                           'terms': copy.deepcopy(self.terms), 'evidence': evidence})
        for key, status in self.statuses.items():
            event = {'type': 'actor_status', 'actor': key, 'status': status, 'evidence': evidence}
            toward = getattr(self, 'fled_toward', {}).get(key)
            if toward:
                event['toward'] = toward
            events.append(event)
        return events


ABILITY_NAMES = {'str': 'Strength', 'dex': 'Dexterity', 'con': 'Constitution', 'int': 'Intelligence',
                 'wis': 'Wisdom', 'cha': 'Charisma'}
BARE_NUMBER = re.compile(r'^\W*(\d{1,2})\W*$')
ABILITY_WORDS = {'str': 'str|strength', 'dex': 'dex|dexterity', 'con': 'con|constitution',
                 'int': 'int|intelligence', 'wis': 'wis|wisdom', 'cha': 'cha|charisma'}
# "Con save 14", "Con: 14", "Constitution 14", "con save: 14" (the ability, then the total).
_SAVE_CLAUSE = r"\b(?:{words})\b(?:\s+sav(?:e|ing throw))?\s*[:=]?\s*(?:is\s+|of\s+)?(\d{{1,2}})\b"


def attacker(awaiting):
    """Who a save rider came from: ``from`` (#97), or ``attacker`` (#101's name for it)."""
    awaiting = awaiting or {}
    return awaiting.get('attacker') or awaiting.get('from')


def after_save_clause(action):
    """What the player declared after his save total ('Con save 14, then I cast...'), or ''."""
    found = re.search(r'\b\d{1,2}\b\s*(?:[,;.!]+\s*|\s+)(?:and\s+|then\s+|and then\s+)?(?=\w)(.+)$',
                      action or '', re.S)
    if not found:
        return ''
    rest = found.group(1).strip()
    return rest if re.search(r'\b(?:i|nik|he|she|they)\b', rest, re.I) or re.match(r'(?i)(?:cast|attack|stab|hit|run|move)\b', rest) else ''


def save_prompt(awaiting):
    """The roll call for a save the player owes (never the DC)."""
    if awaiting['save'] == 'death':
        return 'Roll a death saving throw.'
    if awaiting.get('repeat'):
        return f"Roll a {ABILITY_NAMES.get(awaiting['save'], awaiting['save'])} saving throw (end of your turn, against the {'paralysis' if awaiting['repeat'] == 'paralyzed' else awaiting['repeat']})."
    return f"Roll a {ABILITY_NAMES.get(awaiting['save'], awaiting['save'])} saving throw."


def at_zero_terms(names):
    """SRD Giant Centipede: dropped to 0 by its poison, the target is stable but poisoned for
    1 hour, even after regaining hit points, and paralyzed while poisoned in this way."""
    out = {}
    for name in names:
        out[name] = {'until_s_in': 3600} if name == 'poisoned' else {'while': 'poisoned'} \
            if name == 'paralyzed' and 'poisoned' in names else {}
    return out


def unhalved_damage(action, shown):
    """The full total behind Avrae's halved damage line ("8d6 (4, 3, 5, ...) [fire] = `14`"): the
    dice it shows, summed, when that sum halves (rounded down) to ``shown``; else None."""
    for line in str(action or '').splitlines():
        if not re.search(r'\bdamage\b', line, re.I):
            continue
        found = re.search(r'\(([\d,\s~]+)\)[^=]*=\s*`?(\d+)`?', line)
        if not found or int(found.group(2)) != shown:
            continue
        dice = [int(d) for d in re.findall(r'\d+', found.group(1))]
        total = sum(dice)
        if dice and total // 2 == shown:
            return total
    return None


def death_save_total(action):
    """The d20 he reports for a death save (Avrae's ``!g ds`` line, "Death save 12", "nat 20",
    or the bare number answering the roll call), 1-20, else None."""
    text = action or ''
    avrae = re.search(r'\b\d*d20\s*\((\d{1,2})\)[^=\n]*=\s*`?\*{0,2}(\d{1,2})', text)
    if avrae:
        value = int(avrae.group(2))
    else:
        named = re.search(r'\bdeath\s+sav(?:e|es|ing\s+throws?)\b\D{0,15}?(\d{1,2})\b', text, re.I) or \
            re.search(r'\b(?:natural|nat)\s*(\d{1,2})\b', text, re.I) or BARE_NUMBER.match(text)
        if not named:
            return None
        value = int(named.group(named.lastindex))
    return value if 1 <= value <= 30 else None


def save_total(action, ability):
    """The player's total for an ``ability`` save: a roll labelled as that save, else an
    unlabelled one, else a bare number (the answer to the roll call)."""
    if ability == 'death':
        return death_save_total(action)
    try:
        found = kit_rolls.rolls(action)
    except Exception:
        found = []
    for roll in found:
        if roll.label == f'{ability}_save':
            return roll.total
    named = re.search(_SAVE_CLAUSE.format(words=ABILITY_WORDS.get(ability, ability)), action or '', re.I)
    if named:
        return int(named.group(1))
    loose = [roll for roll in found if roll.label in (None, ABILITY_NAMES.get(ability, '').casefold(), ability)]
    if loose:
        return loose[0].total
    bare = BARE_NUMBER.match(action or '')
    return int(bare.group(1)) if bare else None


def _derived_save_dc(sheet):
    """8 + proficiency + the best mental ability modifier, when a sheet has abilities but no
    spell save DC written down (5e's spell save DC formula with the likeliest casting ability)."""
    abilities = (sheet or {}).get('abilities') or {}
    if not abilities or not sheet.get('proficiency_bonus'):
        return None
    return 8 + int(sheet['proficiency_bonus']) + max(_mod(abilities.get(a, 10)) for a in ('int', 'wis', 'cha'))


def _mod(score):
    return (int(score) - 10) // 2


def _passive_perception(actor):
    from .kit_claims import npc_passive
    return npc_passive(actor, 'perception')


def public_view(source, state):
    """What the player can see of the fight and the room's loose things (no numbers)."""
    out = {}
    current = state.get('combat')
    if current:
        lab = labels(source)
        wounds = {}
        for key, hp in (current.get('hp') or {}).items():
            actor = (state.get('actors') or {}).get(key) or {}
            if actor.get('status') in ('fled',):
                wounds[lab.get(key, key)] = 'fled'
            elif actor.get('status') in ('dead', 'unconscious'):
                wounds[lab.get(key, key)] = 'down'
            else:
                full = (current.get('max_hp') or {}).get(key) or hp
                wounds[lab.get(key, key)] = 'unhurt' if hp >= full else 'badly hurt' if hp <= full // 2 else 'hurt'
        order = current.get('order') or []
        out['fight'] = {'status': current['status'], 'round': current.get('round'),
                        'order': ['you' if k == 'pc' else lab.get(k, k) for k in order],
                        'whose_turn': ('you' if order and order[current.get('next', 0) % len(order)] == 'pc' else None)
                        if current['status'] == 'running' else None,
                        'wounds': wounds, 'damage_you_took': current.get('pc_damage', 0)}
        if (current.get('awaiting') or {}).get('kind') == 'roll_call':
            out['fight']['roll_needed'] = save_prompt(current['awaiting'])[len('Roll a '):-1]
        if current['status'] == 'running':
            out['fight']['your_reaction'] = 'spent' if current.get('reaction_used') else 'available'
        if current.get('pc_dead'):
            out['fight']['you_are'] = 'dead'
        elif current.get('pc_down'):
            out['fight']['you_are'] = 'down, stable' if current.get('pc_stable') else 'down, dying'
            if not current.get('pc_stable'):
                out['fight']['death_saves'] = dict(current.get('death_saves') or {'successes': 0, 'failures': 0})
        if (current.get('awaiting') or {}).get('kind') == 'kit_call':
            out['fight']['waiting_on'] = 'what your foes do while you are down'
        if current['status'] != 'over' and 'pc' in (current.get('surprised') or ()) and current.get('round') == 1:
            out['fight']['you_are_surprised'] = True  # no reactions until your first turn ends
    if pc_conditions(state):
        out['your_conditions'] = pc_conditions(state)
    sc = state.get('scene')
    if sc and table_scene(source):
        out['room_now'] = {'table': sc.get('table'), 'coins': sc.get('pot'), 'ring': _ring_text(source, sc.get('ring')),
                           'you_took': list(sc.get('pc_took') or []),
                           **({'you_hold': labels(source).get(sc['grappled'], sc['grappled'])} if sc.get('grappled') else {})}
    return out


def _ring_text(source, where):
    if where in (None, 'on_table'):
        return 'on the table'
    if where == 'floor':
        return 'on the floor'
    if where == 'you':
        return 'yours'
    if where in ((source or {}).get('actors') or {}):
        return f'in the {labels(source).get(where, where).lower()}\'s hand'
    return where

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


def parse(action, source, state):
    """What the player physically does, or None. A dict with ``kind`` (attack, grab,
    face, flip, take, wait), ``target`` (actor id or None), and the details each needs."""
    if not config(source) or state.get('area') != config(source).get('area', state.get('area')):
        return None
    text = narration(action).casefold()
    here = present(source, state)
    sc = scene(state)
    named = name_target(text, source, state, here)
    spell = _SPELL.search(text)
    in_fight = bool((state.get('combat') or {}).get('status') in ('awaiting_initiative', 'running'))
    if spell:
        name = spell.group(1)
        area = name in SPELL_SAVE and SPELL_SAVE[name][2]
        return {'kind': 'attack', 'spell': name, 'weapon': name, 'area': bool(area),
                'target': None if area else (named or _default_target(text, source, state, here))}
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
        return {'kind': 'attack', 'weapon': weapon.group(1) if weapon else 'unarmed strike',
                'target': named or _default_target(text, source, state, here), 'area': False,
                'unarmed': not weapon, 'nonlethal': bool(NONLETHAL.search(text))}
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
    if grab and (named or _creature_words(text)) and here and not VALUABLES.search(text[grab.end():grab.end() + 30]) \
            and not GAZE.search(text[grab.end():grab.end() + 20]):
        return {'kind': 'grab', 'target': named or _default_target(text, source, state, here),
                'teeth': bool(TEETH.search(text)), 'wrist': bool(re.search(r'\b(wrist|hand|arm)\b', text))}
    if in_fight and WAIT.search(text):
        return {'kind': 'wait', 'target': None}
    return None


def table_scene(source):
    """True for a room whose combat block keys loose loot on a table (``loose_money``): only
    there do coins and a ring lie about to be taken, and only there is ``room_now`` shown."""
    return bool(((source or {}).get('combat') or {}).get('loose_money'))


# Conditions that stop the PC moving and acting (SRD: incapacitated, and every condition that
# includes it), and the 0 HP state.
INCAPACITATING = ('incapacitated', 'paralyzed', 'petrified', 'stunned', 'unconscious')


def pc_conditions(state):
    """The PC's conditions now: they persist past the fight until they end by rule."""
    return list((state or {}).get('pc_conditions') or [])


def pc_incapacitated(state):
    """Why the PC cannot move or act now ('down', or the condition), else None."""
    current = (state or {}).get('combat') or {}
    if current.get('status') in ('awaiting_initiative', 'running') and current.get('pc_down'):
        return 'down'
    for name in pc_conditions(state):
        if name in INCAPACITATING:
            return name
    return None


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
        return not self.pc_surprised_now() and not any(c in INCAPACITATING for c in pc_conditions(self.state))

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
        self.resources, slot = kit_reactions.spend(self.resources, key, slot_level)
        self.resources_changed = True
        self.trace.append(f'PC uses {key}' + (f' (level {slot} slot, cast in Avrae)' if slot else ''))

    def engage(self, key):
        engaged = self.fight.setdefault('engaged', [])
        if key not in engaged:
            engaged.append(key)

    def in_reach(self, key):
        """Melee adjacency, tracked by default: whoever traded melee blows with the PC (either way)
        this fight, plus anyone the room says starts in reach."""
        return key in (self.config.get('in_reach') or ()) or key in (self.fight.get('engaged') or ())

    def declined(self, family, stakes):
        """A window of this family the player declined this round, at stakes no lower than now."""
        mark = self.fight.get('declined') or {}
        if mark.get('round') != self.fight.get('round'):
            return False
        before = (mark.get('families') or {}).get(family)
        return before is not None and not (before == 'normal' and stakes == 'drop')

    def decline(self, waiting):
        mark = self.fight.get('declined') or {}
        if mark.get('round') != self.fight.get('round'):
            mark = {'round': self.fight.get('round'), 'families': {}}
        mark['families'][waiting['trigger']] = waiting.get('stakes', 'normal')
        self.fight['declined'] = mark
        self.trace.append(f"PC declines the {waiting['trigger']} window (not offered again this round "
                          'unless the stakes rise)')

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
                if waiting['trigger'] == 'hit':
                    self.resume_hit(waiting, react)
                    self.npc_turn(waiting['attacker'], start=waiting['attack_index'] + 1)
                    self.step()
                    self.check_over()
                    self.run_npcs()
                elif waiting['trigger'] == 'npc_spell':
                    countered = False
                    if react != 'decline':
                        effect = (kit_reactions.entry(self.resources, react) or {}).get('effect')
                        self.spend_reaction(react, (self.choice or {}).get('slot_level'))
                        if react == 'counterspell' and int(waiting.get('level') or 0) <= 3:
                            countered = True  # SRD: a spell of 3rd level or lower simply fails
                            self.lines.append(f"Counterspell: the {waiting['name']} fails.")
                        elif effect not in kit_reactions.EFFECTS:
                            self.adjudicate(react, waiting)
                    index = waiting['attack_index']
                    self.npc_turn(waiting['attacker'], start=index + 1 if countered else index,
                                  cast_answered=not countered)
                    self.step()
                    self.check_over()
                    self.run_npcs()
                elif waiting['trigger'] == 'npc_save':
                    self.resume_spell_save(waiting, react)
                    if self.fight['status'] == 'awaiting_initiative':
                        self.fight['opener_spent'] = True  # the spell paused here was his opening blow
                    self.after_pc_action(True)
                else:  # leaves_reach: an opportunity attack
                    key = waiting['actor']
                    if react != 'decline':
                        self.spend_reaction(react)
                        if react == 'opportunity_attack':
                            weapon = re.search(r'\b(' + WEAPONS + r')\b', narration(self.action).casefold())
                            self.pc_attack({'kind': 'attack', 'target': key, 'area': False,
                                            'weapon': weapon.group(1) if weapon else 'attack', 'unarmed': not weapon})
                        else:
                            self.adjudicate(react, waiting)
                    if self.active(key):
                        self.flee(key)
                    self.step()
                    self.check_over()
                    self.run_npcs()
            elif kind == 'roll_call':
                self.resume_save(waiting)
                who = attacker(waiting)  # #97-era prompts say "from", #101's "attacker"
                if not self.fight.get('pc_down') and who and waiting.get('attack_index') is not None:
                    self.npc_turn(who, start=waiting['attack_index'] + 1)
                self.step()
                self.check_over()
                self.run_npcs()
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

    def legal_reaction(self, waiting):
        """Kit's ``react`` for this window, checked: offered, still available, a spell cast in Avrae
        first, an opportunity attack rolled and made with a melee weapon."""
        if self.choice is None or 'react' not in self.choice:
            raise NeedsChoice(waiting)
        react = self.choice['react']
        if react == 'unclear':
            raise Unclear('Kit could not tell which reaction, if any, the player takes.', 'unclear')
        if react == 'decline':
            return react
        if react not in waiting['options']:
            raise Unclear(f'{react} is not offered in this window (offered: {", ".join(waiting["options"])}).',
                          'not_offered')
        found = kit_reactions.entry(self.resources, react)
        if not found or self.fight.get('reaction_used') or not kit_reactions.payable(self.resources, found):
            raise Unclear(f'{react} is not available now (reaction spent, or no slot or use left).', 'not_available')
        if found['kind'] == 'spell' and not self.choice.get('cast_in_avrae'):
            raise Unclear(f"{found['name']} is cast in Avrae first.", 'needs_cast',
                          ask=f"!cast {found['name'].casefold()}")
        if found['effect'] == 'opportunity_attack':
            if RANGED.search(narration(self.action).casefold()):
                raise Unclear('An opportunity attack is a melee attack; a ranged weapon cannot make one.',
                              'ranged_weapon')
            if kit_rolls.attack_total(self.action) is None:
                raise Unclear('The opportunity attack waits on its Avrae roll, with damage.', 'needs_roll',
                              ask='the attack roll and damage')
        return react

    def adjudicate(self, react, waiting):
        """A reaction the engine does not model: its cost is paid, the event stands as rolled, and Kit
        rules the effect (flagged on the fight for her packet)."""
        found = kit_reactions.entry(self.resources, react) or {}
        self.fight.setdefault('adjudicate', []).append({'reaction': react, 'name': found.get('name', react),
                                                        'window': waiting['trigger'],
                                                        'round': self.fight.get('round')})
        self.lines.append(f"{found.get('name', react)}: its effect is Kit's ruling.")
        self.trace.append(f'{react}: Kit adjudicates the effect')

    def resume_hit(self, waiting, react):
        name = waiting['name']
        dealt = waiting['damage']
        die = waiting['die']
        total = waiting['total']
        effect = (kit_reactions.entry(self.resources, react) or {}).get('effect') if react != 'decline' else None
        if react != 'decline':
            self.spend_reaction(react, (self.choice or {}).get('slot_level'))
        hit = True
        if effect == 'shield':
            self.fight['shield_up'] = True
            hit = not waiting.get('magic_missile') and (die == 20 or total >= self.pc_ac())
            self.lines.append(f'Shield: the {name} ' + ('still gets through.' if hit else 'is turned.'))
        elif effect in ('silvery_barbs', 'chronal_shift'):
            again = self.die(f"{react}:{waiting['attacker']}:r{self.fight['round']}:{waiting['attack_index']}")
            new = min(die, again) if effect == 'silvery_barbs' else again
            total = new + (total - die)
            hit = new == 20 or (new != 1 and total >= self.pc_ac())
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
        elif react != 'decline':
            self.adjudicate(react, waiting)
        self.trace.append(f"reaction {react}: {total} vs AC {self.pc_ac()}: {'hit' if hit else 'miss'}")
        if not hit:
            return
        self.fight['pc_damage'] += dealt
        self.lines.append(f"The {name} hits you: {dealt} {waiting['type']} damage.")
        if self.pc_hp() is not None and self.fight['pc_damage'] >= int(self.pc_hp()):
            self.fight['pc_down'] = True
            self.lines.append('You go down.')
        elif waiting.get('rider'):
            # Reaction before damage, then the save the hit carries.
            self.owe_save(waiting['attacker'], waiting['attack_index'], waiting['rider'])

    def resume_spell_save(self, waiting, react):
        """A creature saved against the PC's spell and the window let him answer it: the reroll (if
        taken), then every target's damage lands as the spell resolved."""
        results = [list(r) for r in waiting['results']]
        if react != 'decline':
            effect = (kit_reactions.entry(self.resources, react) or {}).get('effect')
            self.spend_reaction(react, (self.choice or {}).get('slot_level'))
            for row in results:
                key, saved, die, bonus = row[0], row[1], row[2], row[3]
                if key != waiting['target'] or die is None:
                    continue
                if effect in ('silvery_barbs', 'chronal_shift'):
                    again = self.die(f"{react}:save:{key}:r{self.fight['round']}")
                    new = min(die, again) if effect == 'silvery_barbs' else again
                    row[1] = new + bonus >= int(waiting['dc'])
                    self.trace.append(f'{react}: {key} rerolls the save, d20 {again}, uses {new}: '
                                      f"{'saved' if row[1] else 'failed'}")
                else:
                    self.adjudicate(react, waiting)
        damage, half = int(waiting['damage']), bool(waiting.get('half'))
        for key, saved, *_ in results:
            if self.active(key):
                self.apply_damage(key, (damage // 2 if half else 0) if saved else damage, waiting.get('dtype'))
        self.fight['pending'] = None

    def after_pc_action(self, acted):
        """What follows the PC's act: the fight may end, a worthy kill hands the floor over (a
        flourish), and the round runs on to the PC's next turn."""
        self.check_over()
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
        self.finish()
        return self.public(), self.events()

    def _resolve(self, act):
        init = kit_rolls.initiative(self.action)
        kind = (act or {}).get('kind')
        waiting = (self.fight or {}).get('awaiting')
        if waiting and waiting['kind'] == 'flourish_window':
            # A new act instead of a description: the flourish is passed, the round runs on.
            self.fight['awaiting'] = None
            if self.fight['status'] == 'running':
                self.advance_past_pc()
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
                acted = self.pc_attack(act)
                self.needs_roll = not acted and init is None
                if self.fight['status'] == 'awaiting_initiative' and acted:
                    self.fight['opener_spent'] = True
        elif kind:
            acted = True
            {'grab': self.pc_grab, 'face': self.pc_face, 'flip': self.pc_flip, 'take': self.pc_take,
             'wait': self.pc_wait}[kind](act)
        self.after_pc_action(acted)

    def pc_wait(self, act):
        self.lines.append('You hold your ground and wait for them to come to you.')

    def pc_turn_now(self):
        """The PC's turn, and he can take it (a surprised PC loses his round-one turn)."""
        order = self.fight['order']
        return bool(order) and order[self.fight['next'] % len(order)] == 'pc' and not self.pc_surprised_now()

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
        self.fight['next'] += 1
        if self.fight['next'] >= len(order):
            self.fight['next'] = 0
            self.fight['round'] += 1

    def run_npcs(self):
        """Every turn up to the PC's. A surprised PC's round-one turn passes; a save the
        player must roll (a monster's rider) stops the round until he rolls it."""
        guard = 0
        while self.fight['status'] == 'running' and not self.pc_turn_now() and \
                not self.fight.get('awaiting') and guard < 12:
            guard += 1
            key = self.fight['order'][self.fight['next']]
            if key == 'pc':
                self.lines.append('You are surprised and lose your first turn.')
                self.trace.append('PC surprised: round 1 turn lost')
                self.fight['surprise_spent'] = True
            elif self.active(key):
                self.npc_turn(key)  # may stop at a checkpoint (the order stays on this NPC)
            self.step()
            self.check_over()
        if self.fight['status'] == 'running' and self.pc_turn_now():
            self.start_pc_turn()

    # -- a save the player rolls (a monster attack's rider) ---------------------------
    def owe_save(self, key, index, rider):
        """Stop at a roll call: the player rolls his own save in Avrae (never shown the DC).
        Order with a reaction window: the reaction first (before damage), then the save."""
        self.lines.append(save_prompt({'save': rider['ability']}))
        self.wait_for('roll_call', 'player_roll', trigger='save_rider', save=rider['ability'], dc=rider['dc'],
                      damage=rider['damage'], type=rider['type'], half=bool(rider.get('half')),
                      at_zero=list(rider.get('at_zero') or ()), attacker=key, attack_index=index)

    def resume_save(self, waiting):
        """The player's save total answers the roll call; the rider's damage lands or not. Anything he
        declared with it ('Con save 14, then I cast magic missile') waits for his turn (declared_next)."""
        total = save_total(self.action, waiting['save'])
        if total is None:
            raise Unclear(f"{save_prompt(waiting)[:-1]} in Avrae first (!save {waiting['save']}). "
                          'No turn was committed.')
        self.fight['awaiting'] = None
        saved = kit_rolls.meets_or_beats(total, waiting['dc'])  # meeting the DC saves
        damage = int(waiting['damage'])
        dealt = (damage // 2 if waiting.get('half') else 0) if saved else damage
        self.trace.append(f"PC {waiting['save']} save {total} vs DC {waiting['dc']} "
                          f"({attacker(waiting)}): {'saved' if saved else 'failed'}, {dealt} {waiting['type']}")
        if not dealt:
            self.lines.append(f"You shake off the {waiting['type']}.")
        else:
            self.lines.append(f"You {'resist some of' if saved else 'fail to resist'} the {waiting['type']}: "
                              f"{dealt} {waiting['type']} damage.")
            self.fight['pc_damage'] += dealt
            hp = self.pc_hp()
            if hp is not None and self.fight['pc_damage'] >= int(hp):
                self.fight['pc_down'] = True
                self.fight['pc_damage'] = int(hp)
                if waiting.get('at_zero'):
                    # Conditions live on the PC, not the fight: they outlast it (runtime state).
                    self.fight['pc_conditions'] = list(dict.fromkeys(list(self.fight.get('pc_conditions') or ()) +
                                                                     list(waiting['at_zero'])))
                    self.lines.append(f"You drop, stable but {' and '.join(waiting['at_zero'])}.")
                else:
                    self.lines.append('You go down.')
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

    def declared_turn(self):
        """What the player declared with a save ('..., then I cast magic missile') is his act when
        his turn comes and nothing else waits."""
        rest = self.fight.get('declared_next')
        if not rest or self.fight['status'] != 'running' or self.fight.get('pc_down') or \
                self.fight.get('awaiting') or not self.pc_turn_now():
            return
        self.fight.pop('declared_next', None)
        follow = parse(rest, self.source, self.state)
        if follow:
            self.trace.append(f'his declared act after the save: {rest[:120]}')
            self.action = rest
            self._resolve(follow)

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
                if result.get('save') and result['save'][2] is not None:
                    saved = result['save'][2]
                    dealt = result['damage'][0] if result.get('damage') else \
                        ((damage // 2 if half else 0) if saved else damage)
                    self.trace.append(f'{key} {ability} save from Avrae: {result["save"][1]} '
                                      f'{"saved" if saved else "failed"}, {dealt} damage')
                    hits.append((key, dealt))
                    rows.append([key, saved, None, None])
                    continue
                bonus = self.stats(key).get('saves', {}).get(ability)
                if bonus is None:
                    bonus = _mod(((self.state['actors'][key].get('stats') or {}).get('abilities') or {}).get(ability, 10))
                die = self.die(f'save:{key}:{spell}')
                saved = die + bonus >= int(dc)
                dealt = (damage // 2 if half else 0) if saved else damage
                self.trace.append(f'{key} {ability} save d20 {die} + {bonus} vs DC {dc}: '
                                  f'{"saved" if saved else "failed"}, {dealt} damage')
                hits.append((key, dealt))
                rows.append([key, saved, die, bonus])
            self.spend_own_slot(spell)
            saver = next((row[0] for row in rows if row[1] and row[2] is not None), None)
            options = self.options_for(['creature_succeeds']) if saver and not self.declined('npc_save', 'normal') \
                else []
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
        if self.fight.get('pc_down'):
            return
        attacks = stats.get('attacks') or []
        if start >= len(attacks):
            return
        hits, misses = [], 0
        who = f'The {self.label(key)}'
        for index in range(start, len(attacks)):
            attack = attacks[index]
            if attack.get('spell') and not (cast_answered and index == start) and self.pc_can_react() \
                    and not self.fight.get('pc_down') and not self.declined('npc_spell', 'normal'):
                options = self.options_for(['spell_cast_within_range'])
                if options:
                    if hits:
                        self.say_hits(who, hits, 2)
                    self.lines.append(f"{who} begins casting: {attack['name']}.")
                    self.wait_for('reaction_window', 'player_answer', trigger='npc_spell', options=options,
                                  attacker=key, attack_index=index, name=attack['name'],
                                  level=attack.get('level'), triggers=['spell_cast_within_range'], stakes='normal')
            die = self.die(f'npc:{key}:r{self.fight["round"]}:{index}')
            total = die + attack['to_hit']
            ac = self.pc_ac()
            missile = bool(attack.get('auto_hit'))  # magic missile: no roll, Shield blocks it
            hit = missile or die == 20 or (die != 1 and kit_rolls.meets_or_beats(total, ac))
            dealt = attack['damage'] * (2 if die == 20 and not missile else 1)
            self.trace.append(f'{key} {attack["name"]}: d20 {die} + {attack["to_hit"]} = {total} vs AC {ac}: '
                              f'{"hit " + str(dealt) if hit else "miss"}')
            if not RANGED.search(attack['name']) and not attack.get('ranged'):
                self.engage(key)  # a melee attack on the PC: they are in each other's reach
            if not hit:
                misses += 1
                continue
            stakes = 'drop' if self.pc_hp() is not None and \
                self.fight['pc_damage'] + dealt >= int(self.pc_hp()) else 'normal'
            triggers = self.hit_triggers(attack, missile)
            options = [] if not self.pc_can_react() or self.declined('hit', stakes) else \
                self.options_for(triggers, fit=lambda r: self.turns_hit(r, die, total, ac, attack, missile))
            if options and not self.fight.get('pc_down'):
                if hits:
                    self.say_hits(who, hits, 2)
                self.lines.append(f"{who}'s {attack['name']} comes at you: {'it never misses' if missile else f'that is a {total}, a hit'}.")
                self.wait_for('reaction_window', 'player_answer', trigger='hit', options=options, attacker=key,
                              attack_index=index, die=die, total=total, damage=dealt, base=attack['damage'],
                              type=attack.get('type'), name=attack['name'], triggers=triggers, stakes=stakes,
                              **({'magic_missile': True} if missile else {}),
                              **({'rider': attack['save']} if attack.get('save') else {}))
            self.fight['pc_damage'] += dealt
            hits.append((dealt, attack['type']))
            if self.pc_hp() is not None and self.fight['pc_damage'] >= int(self.pc_hp()):
                self.fight['pc_down'] = True
                break
            if attack.get('save'):
                self.say_hits(who, hits, 1 if len(attacks) == 1 else 2)
                self.owe_save(key, index, attack['save'])
        swings = len(attacks) - start
        if start and not hits:
            self.lines.append(f"{who}'s other {'attack misses' if swings == 1 else 'attacks miss'}.")
        else:
            self.say_hits(who, hits, swings if not start else 2)
        if self.fight.get('pc_down'):
            self.lines.append('You go down.')

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
        out = ['self_hit_by_attack', 'creature_succeeds', 'creature_hits_you_within_range']
        if attack.get('type') in ELEMENTS:
            out.append('elemental_damage_taken')
        if RANGED.search(attack['name']) or attack.get('ranged'):
            out.append('self_hit_by_ranged_weapon')
        return out

    def turns_hit(self, entry, die, total, ac, attack, missile):
        """Whether offering this reaction can matter for this hit: Shield only when +5 AC turns it
        (never a natural 20) or it is a magic missile; the rest whenever their trigger matches."""
        if entry['effect'] == 'shield':
            return missile or (die != 20 and total < ac + 5)
        if entry['effect'] == 'absorb_elements':
            return attack.get('type') in ELEMENTS
        return True

    def opportunity_options(self, key):
        """The reactions a foe leaving the PC's reach opens (the opportunity attack, Sentinel...):
        he is up, not surprised, his reaction unused, and the foe was in melee reach."""
        if not self.pc_can_react() or not self.in_reach(key) or \
                self.pc_hp() is None or self.declined('leaves_reach', 'normal'):
            return []
        return self.options_for(['foe_leaves_reach'])

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
        if self.fight and self.fight['status'] == 'running':
            order = self.fight['order']
            if order and self.pc_turn_now() and not self.fight.get('pc_down') and not self.fight.get('awaiting'):
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
    return f"Roll a {ABILITY_NAMES.get(awaiting['save'], awaiting['save'])} saving throw."


def save_total(action, ability):
    """The player's total for an ``ability`` save: a roll labelled as that save, else an
    unlabelled one, else a bare number (the answer to the roll call)."""
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

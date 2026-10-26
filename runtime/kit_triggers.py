"""Room triggers: monster-initiated combat from room data alone (PR-M).

A room's ``triggers`` list says what wakes something up. Each entry is data:

    {"id": "carcass_disturbed",
     "on": {"disturb": "<fact id>"} | {"enter": "<area id>"},
     "starts_combat": true,                       # default true
     "actors": ["<actor id>", ...],               # status "hidden" until it fires
     "surprise": {"stealth": <bonus>} | {"stealth": null} | {"dc": <n>},   # optional
     "reveal": "<public line when they show themselves>"}

``disturb`` fires only when Kit's decision declares ``handles: {target, act}`` on that feature (a
part, or what it holds, names it too) and the declaration checks against the turn's offer
(runtime/kit_acts.py). The words alone never fire it: a regex only puts a ``hint`` in the
offer. ``enter`` fires when the PC arrives in the area, or on his first resolved turn there
(he started there, or a room_link mounted the room with him in it). A trigger fires once; one
whose actors are all dead, gone or already fighting is spent quietly (no fight restarted).
Firing commits a ``trigger_fired`` event (the actors go from hidden to alive and visible) and,
with ``starts_combat``, the fight starts awaiting initiative with the reveal line read first.

Surprise follows the SRD: each ambusher's Dexterity (Stealth) check (a seeded d20 plus the
bonus given, else the stat block's ``stealth``, else Dex 0) against the PC's passive
Perception; the PC is surprised only if he notices none of them. Ties go to the actor
(kit_rolls.meets_or_beats): a Stealth total equal to the passive is not noticed.
A flat ``dc`` stands in for the group's check. The ambushers are never surprised. A PC already
in a fight is never surprised.

Hidden actors (``status: "hidden"``) are in dm_only and nowhere else Kit or the player can see
until their trigger fires (state_context, kit_brief, kit_agenda, kit_attitude, kit_claims,
scene_discernment and the bridge's speakers all skip them).
"""
import hashlib
import re

from . import kit_rolls
from .state_context import InvalidChange, require

KINDS = ('disturb', 'enter')
FEATURE_KINDS = ('move_feature', 'inspect_feature', 'enter_feature')
FIELDS = {'id', 'on', 'starts_combat', 'actors', 'surprise', 'reveal'}


def compile_triggers(source):
    """The room's triggers, checked against its facts, areas and actors (InvalidChange names
    the first problem)."""
    triggers = source.get('triggers') or []
    require(isinstance(triggers, list), 'triggers must be a list')
    seen = set()
    for trigger in triggers:
        require(isinstance(trigger, dict), 'each trigger is an object')
        tid = trigger.get('id')
        require(isinstance(tid, str) and tid.strip() and tid not in seen, 'each trigger needs a unique id')
        seen.add(tid)
        extra = set(trigger) - FIELDS - {k for k in trigger if str(k).startswith('_')}
        require(not extra, f'trigger {tid}: unknown fields {sorted(extra)}')
        on = trigger.get('on')
        require(isinstance(on, dict) and len(on) == 1 and next(iter(on)) in KINDS,
                f'trigger {tid}: on must be one of {{"disturb": fact}} or {{"enter": area}}')
        kind, target = next(iter(on.items()))
        if kind == 'disturb':
            fact = (source.get('facts') or {}).get(target)
            require(isinstance(fact, dict), f'trigger {tid}: unknown fact {target!r}')
            require(bool(fact.get('handling')), f'trigger {tid}: fact {target!r} has no handling to disturb')
        else:
            require(target in (source.get('areas') or {}), f'trigger {tid}: unknown area {target!r}')
        actors = trigger.get('actors')
        require(isinstance(actors, list) and actors, f'trigger {tid}: actors must list who it wakes')
        for key in actors:
            require(key in (source.get('actors') or {}), f'trigger {tid}: unknown actor {key!r}')
        require(isinstance(trigger.get('starts_combat', True), bool), f'trigger {tid}: starts_combat is true or false')
        surprise = trigger.get('surprise')
        if surprise is not None:
            require(isinstance(surprise, dict) and len(surprise) == 1 and (
                ('stealth' in surprise and (surprise['stealth'] is None or type(surprise['stealth']) is int)) or
                ('dc' in surprise and type(surprise['dc']) is int)),
                f'trigger {tid}: surprise is {{"stealth": bonus or null}} or {{"dc": n}}')
        reveal = trigger.get('reveal')
        require(reveal is None or (isinstance(reveal, str) and 0 < len(reveal) <= 300),
                f'trigger {tid}: reveal is one public line (up to 300 characters)')
    return triggers


def pending(source, state):
    """Triggers that have not fired yet."""
    fired = set(state.get('triggers_fired') or ())
    return [t for t in (source.get('triggers') or []) if t['id'] not in fired]


def apply_event(state, source, event):
    key = event.get('trigger')
    trigger = next((t for t in (source.get('triggers') or []) if t.get('id') == key), None)
    require(trigger is not None, 'Unknown trigger')
    fired = state.setdefault('triggers_fired', [])
    require(key not in fired, 'That trigger has already fired')
    for actor_key in trigger['actors']:
        actor = state['actors'].get(actor_key)
        require(actor is not None, 'Unknown actor')
        if actor.get('status') == 'hidden':
            actor['status'] = 'alive'
            actor['visible'] = True
    fired.append(key)


def _known(fact_key, source, state):
    fact = (source.get('facts') or {}).get(fact_key) or {}
    return bool(fact.get('visible')) or fact_key in (state.get('known_facts') or ())


def disturb_targets(source, state, area=None):
    """{feature id: {'words': [nouns], 'parts': [parts and the held id, if known]}} for each
    feature in the area whose ``disturb`` trigger has not fired and that the PC knows is there
    (visible, or found since: known_facts). An unfound trapdoor is never offered and cannot
    fire until it is found (#97 review C)."""
    area = area or state.get('area')
    facts = source.get('facts') or {}
    out = {}
    for trigger in pending(source, state):
        kind, key = next(iter(trigger['on'].items()))
        fact = facts.get(key) or {}
        if kind != 'disturb' or fact.get('area') != area or key in out or not _known(key, source, state):
            continue
        handling = fact.get('handling') or {}
        words = [str(n).casefold() for n in handling.get('nouns') or ()]
        parts = [str(p).casefold() for p in handling.get('parts') or ()]
        held = handling.get('holds')
        if held and _known(held, source, state):
            # Only an item the PC has seen names it: an unseen orb is not a handle.
            parts.append(held)
            words += [str(n).casefold() for n in ((facts.get(held) or {}).get('handling') or {}).get('nouns') or ()]
        out[key] = {'words': words + parts, 'parts': parts, 'held': held if held in parts else None,
                    'held_words': [str(n).casefold() for n in ((facts.get(held) or {}).get('handling') or {}).get('nouns') or ()]
                    if held in parts else []}
    return out


# Hands-on verbs beyond the hint's (kit_acts.HINT_VERBS): any of them, or a verb with "it",
# "them", "this" or "that" as its own object, makes a turn physical (#97 review P1-E).
PHYSICAL_EXTRA = (r'set|sets|put|puts|place|places|lean|leans|press|presses|jam|jams|wedge|wedges|knock|knocks|'
                  r'bang|bangs|throw|throws|toss|tosses|drop|drops|hold|holds|carry|carries|tear|tears|rip|rips|'
                  r'slide|slides|swing|swings|bash|bashes|turn|turns|wrestle|wrestles|jump|jumps|step on|'
                  r'steps on|brace|braces|haul|hauls|hammer|hammers|chip|chips|scrape|scrapes|unlock|unlocks|'
                  r'close|closes|shut|shuts|slam|slams|tilt|tilts|topple|topples|budge|budges|dig|digs|'
                  r'reach|reaches|thrust|thrusts|empty|empties|loot|loots|steal|steals|use|uses')
PRONOUN_OBJECT = re.compile(r"\b([a-z]+)\s+(?:it|them|this|that)\b")
NOT_HANDS = re.compile(r'^(?:at|to|toward|towards|near|by|beside|behind|around|past|from|about|of|on|over|'
                       r'into|through|look|looks|watch|watches|see|sees|hear|hears|listen|listens|smell|smells|'
                       r'sniff|sniffs|study|studies|examine|examines|inspect|inspects|check|checks|eye|eyes|'
                       r'consider|considers|ignore|ignores|leave|leaves|is|was|and|or|if|but|do|does|think|say|'
                       r'says|ask|asks|tell|tells|mean|means|wait|waits)$')
# The engine's own perception reads: never a hands-on turn.
LOOK_KINDS = ('observe', 'threshold_look')


# Perception or idling only ("I look at the lid", "I listen at it", "I wait"): no hands go on
# anything. The line's lead verb decides, plus no second clause ("and", "then", a comma).
PERCEIVING = re.compile(r"^\s*(?:i\s+)?(?:\w+ly\s+)?(?:look|looks|glance|glances|peer|peers|peek|peeks|gaze|gazes|"
                        r"stare|stares|watch|watches|listen|listens|sniff|sniffs|smell|smells|study|studies|"
                        r"examine|examines|inspect|inspects|eye|eyes|wait|waits|pause|pauses|stand|stands|"
                        r"take a step|take a look|have a look)\b")
FURTHER = re.compile(r"\b(?:and|then|before|after|while)\b|[,;]")


def physical(action):
    """A turn that is not table talk, not only speech or a question, and not only a look, a
    listen or a wait (#97 review P1-E). It says nothing about verbs: whether the PC's hands go
    on a feature is Kit's call on the offer (E')."""
    from .kit_agent import QUOTED_SPEECH, asked_away, is_ooc  # local: kit_agent imports this module
    if is_ooc(action or ''):
        return False
    words = asked_away(QUOTED_SPEECH.sub(' ', action or '')).casefold().strip()
    if not re.search(r'[a-z]{2}', words):
        return False
    if PERCEIVING.search(words) and not FURTHER.search(words.rstrip('.!')):
        return False
    return True


def refers(action, targets):
    """True when the line names a watched feature (its nouns, parts or held thing) or refers
    to one with a pronoun object ("I shoulder it")."""
    from .kit_agent import QUOTED_SPEECH  # local
    text = QUOTED_SPEECH.sub(' ', action or '').casefold()
    for info in targets.values():
        if any(re.search(r'\b' + re.escape(w) + r'(?:s|es)?\b', text) for w in info['words']):
            return True
    return bool(re.search(r'\b(?:it|them)\b', text))


def handles_offer(source, state, action, area=None, kind=None):
    """The ``handles`` act offer (runtime/kit_acts.py) on any physical turn in an area with a
    known feature that a pending disturb trigger watches, else None: {targets: {feature:
    [parts]}, hint?}. Kit resolves pronouns and other words for it ("I push it open", "the
    stone slab"); the hint is only the regex's guess at a hands-on act on a named feature. It
    never fires anything."""
    from . import kit_acts
    from .kit_agent import QUOTED_SPEECH, asked_away  # local: kit_agent imports this module
    targets = disturb_targets(source, state, area)
    # E': structure, not verbs. Any turn beside a watched, found feature that is not a look,
    # a listen or a wait (the engine's read, or the line's lead verb with nothing after it).
    # Unnamed synonyms ("the stone slab") reach Kit too; none needs a reason, so a turn whose
    # hands go elsewhere costs one field.
    if not targets or kind in LOOK_KINDS or not physical(action):
        return None
    text = QUOTED_SPEECH.sub(' ', action or '').casefold()
    offer = {'targets': {feature: info['parts'] for feature, info in targets.items()}}
    nouns = {}
    for feature, info in targets.items():
        for word in info['words']:
            nouns[word] = feature
    guess = kit_acts.hint(asked_away(text), list(nouns))
    if guess:
        feature = nouns[guess['word']]
        info = targets[feature]
        part = guess['word'] if guess['word'] in info['parts'] else (
            info['held'] if guess['word'] in info['held_words'] else None)
        offer['hint'] = {'target': part or feature, 'act': guess['act']}
    return offer


def named_feature(source, state, action, area=None):
    """The watched feature the words name (for routing an engine feature read), else None."""
    from .kit_agent import QUOTED_SPEECH
    text = QUOTED_SPEECH.sub(' ', action or '').casefold()
    best = None
    for feature, info in disturb_targets(source, state, area).items():
        for word in info['words']:
            found = re.search(r'\b' + re.escape(word) + r's?\b', text)
            if found and (best is None or found.start() < best[0]):
                best = (found.start(), feature)
    return best[1] if best else None


def arrived(source, state, result):
    """The area a move in this resolution lands in, or None."""
    area = state.get('area')
    for event in result.events:
        if event.get('type') == 'move':
            edge = (source.get('exits') or {}).get(event.get('exit')) or {}
            area = next((a for a in edge.get('areas', ()) if a != area), area)
            return area
    return None


def wakes(trigger, state):
    """The trigger's actors it would still change: hidden ones, and live ones not already in
    a running fight. Empty: firing it is a no-op (they are dead, gone, or already fighting)."""
    fight = state.get('combat') or {}
    in_fight = set(fight.get('hp') or {}) if fight.get('status') in ('awaiting_initiative', 'running') else set()
    out = []
    for key in trigger['actors']:
        status = (state.get('actors', {}).get(key) or {}).get('status')
        if status == 'hidden' or (status == 'alive' and key not in in_fight):
            out.append(key)
    return out


def entered(source, state, result):
    """(trigger, area) for a pending ``enter`` trigger this resolution sets off: the PC moves
    into its area, or is already there (he started there, or a room_link mounted the room
    with him in it) when the engine resolves his first turn there."""
    landed = arrived(source, state, result)
    here = landed or state.get('area')
    for trigger in pending(source, state):
        kind, target = next(iter(trigger['on'].items()))
        if kind == 'enter' and target == here:
            return trigger, here
    return None


def disturb_trigger(source, state, feature):
    """The pending disturb trigger on ``feature``, or None."""
    for trigger in pending(source, state):
        if trigger['on'] == {'disturb': feature}:
            return trigger
    return None


def surprise_roll(source, state, revision, trigger, actor_key, npc_roll=None):
    if npc_roll:
        return npc_roll()
    material = f"{state.get('roll_seed', '')}:{revision}:trigger:{trigger['id']}:{actor_key}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1


def pc_surprised(source, state, revision, trigger, passive, npc_roll=None):
    """(surprised?, trace) by the SRD: each ambusher's Stealth check against the PC's passive
    Perception; the actor wins ties (``kit_rolls.meets_or_beats``), and the PC is surprised only
    if he notices none of them. Precedence per ambusher: the trigger's ``stealth`` bonus, else its
    stat block's ``stealth`` (both rolled, d20 + bonus); a flat ``dc`` stands in only for an
    ambusher whose Stealth is unknown (a compiled stat block that states none); with neither,
    Stealth +0 is rolled, as before."""
    rule = trigger.get('surprise')
    if not rule or (state.get('combat') or {}).get('status') in ('awaiting_initiative', 'running'):
        return False, 'no surprise'
    from . import kit_combat
    stats = kit_combat.config(source).get('actors') or {}
    checks = []
    for key in trigger['actors']:
        bonus = rule.get('stealth')
        if bonus is None:
            bonus = (stats.get(key) or {}).get('stealth')
        if bonus is None and 'dc' in rule:
            checks.append((key, f"stealth DC {rule['dc']}", rule['dc']))
            continue
        die = surprise_roll(source, state, revision, trigger, key, npc_roll)
        bonus = int(bonus or 0)
        checks.append((key, f'stealth d20 {die} + {bonus} = {die + bonus}', die + bonus))
    surprised = all(kit_rolls.meets_or_beats(total, passive) for *_, total in checks)
    trace = 'surprise: ' + ', '.join(f'{k} {how}' for k, how, _ in checks) + \
        f' vs passive Perception {passive}: {"surprised" if surprised else "noticed"}'
    return surprised, trace


def handoff_trace(trigger, surprised):
    """The seam for PR-H's per-turn handoff log: what fired and why. Telemetry only."""
    return {'type': 'monster_initiative', 'trigger': trigger['id'], 'on': dict(trigger['on']),
            'starts_combat': trigger.get('starts_combat', True), 'pc_surprised': bool(surprised)}

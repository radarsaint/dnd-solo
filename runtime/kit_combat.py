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
COVERT = re.compile(r'\b(quietly|unnoticed|unseen|without (?:anyone|them) (?:seeing|noticing)|slip|slips|palm|palms|'
                    r'secretly|on the sly|while (?:no one|nobody) is looking)\b')
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


def narration(action):
    """The action without its quoted speech (double or single quotes): only what the PC
    does with their body decides a physical act."""
    text = (action or '').translate(str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"'}))
    text = QUOTED.sub(' ', text)
    return SPEECH_SINGLE.sub(' ', text)


def config(source):
    return (source or {}).get('combat') or {}


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
    attack = ATTACK.search(text)
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
    face = FACE.search(text)
    part = FACE_PARTS.search(text)
    if face and part and not OWN.search(text[max(0, part.start() - 20):part.end()]) and \
            (named or _creature_words(text) or here):
        return {'kind': 'face', 'target': named or _default_target(text, source, state, here),
                'teeth': bool(TEETH.search(text))}
    take = TAKE.search(text)
    loot = VALUABLES.search(text)
    if take and loot and not OWN.search(text[max(0, loot.start() - 25):loot.end() + 16]):
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

    def __init__(self, source, state, revision, action, check, roll=None):
        self.source = source
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
        hp = {key: self.stats(key)['hp'] for key in self.config['actors'] if key in self.state['actors']}
        self.fight = {'status': 'awaiting_initiative', 'round': 1, 'order': [], 'next': 0,
                      'pc_initiative': None, 'surprised': list(self.surprised()), 'hp': hp, 'max_hp': dict(hp),
                      'pc_damage': 0, 'pending': None, 'opener_spent': False, 'started_by': started_by,
                      'last_target': None}
        self.trace.append(f'fight starts ({started_by}); surprised: {self.fight["surprised"] or "nobody"}')
        self.scene['pc_hidden'] = False  # the first blow gives the PC away
        return True

    def surprised(self):
        """Nobody is surprised unless the PC is hidden from everyone when it starts."""
        return [key for key in self.hostiles()] if self.scene.get('pc_hidden') else []

    def pc_ac(self):
        return int(self.sheet.get('ac') or 10)

    def pc_hp(self):
        return self.sheet.get('hp')

    # -- the PC's act ----------------------------------------------------------------
    def resolve(self, act):
        init = kit_rolls.initiative(self.action)
        kind = (act or {}).get('kind')
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
        self.check_over()
        if self.fight and self.fight['status'] == 'running' and acted:
            self.advance_past_pc()
            self.run_npcs()
        elif self.fight and self.fight['status'] == 'awaiting_initiative':
            self.lines.append('Roll initiative.')
        self.finish()
        return self.public(), self.events()

    def pc_wait(self, act):
        self.lines.append('You hold your ground and wait for them to come to you.')

    def pc_turn_now(self):
        order = self.fight['order']
        return bool(order) and order[self.fight['next'] % len(order)] == 'pc'

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
        guard = 0
        while self.fight['status'] == 'running' and not self.pc_turn_now() and guard < 12:
            guard += 1
            key = self.fight['order'][self.fight['next']]
            if key != 'pc' and self.active(key):
                self.npc_turn(key)
            self.step()
            self.check_over()

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
            hits = []
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
        ac = self.stats(key)['ac']
        hit = spell in SPELL_AUTO or natural == 20 or (natural != 1 and total >= ac)
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
        return True

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
            self.lines.append(f'The {self.label(key)} goes down and does not get up.' if status == 'dead' else
                              f'The {self.label(key)} drops, out cold.')
        elif hp[key] <= self.fight['max_hp'][key] // 2:
            self.lines.append(f'The {self.label(key)} is badly hurt.')
        else:
            self.lines.append(f'The {self.label(key)} is hurt.')
        self.crack('fire' if dtype == 'fire' else 'blood', key)

    def npc_turn(self, key):
        stats = self.stats(key)
        if key in self.fight.get('surprised', []) and self.fight['round'] == 1:
            self.lines.append(f'The {self.label(key)} is still reeling.')
            return
        if self.should_retreat(key):
            self.flee(key)
            return
        if self.fight.get('pc_down'):
            return
        hits, misses = [], 0
        for index, attack in enumerate(stats.get('attacks') or []):
            die = self.die(f'npc:{key}:r{self.fight["round"]}:{index}')
            total = die + attack['to_hit']
            hit = die == 20 or (die != 1 and total >= self.pc_ac())
            dealt = attack['damage'] * (2 if die == 20 else 1)
            self.trace.append(f'{key} {attack["name"]}: d20 {die} + {attack["to_hit"]} = {total} vs AC {self.pc_ac()}: '
                              f'{"hit " + str(dealt) if hit else "miss"}')
            if not hit:
                misses += 1
                continue
            self.fight['pc_damage'] += dealt
            hits.append((dealt, attack['type']))
            if self.pc_hp() is not None and self.fight['pc_damage'] >= int(self.pc_hp()):
                self.fight['pc_down'] = True
                break
        who = f'The {self.label(key)}'
        swings = len(stats.get('attacks') or [])
        if not hits:
            self.lines.append(f'{who} {"attacks and misses" if swings == 1 else "swings at you and misses every time"}.')
        else:
            count = {1: 'once', 2: 'twice'}.get(len(hits), f'{len(hits)} times')
            by_type = {}
            for dealt, dtype in hits:
                by_type[dtype] = by_type.get(dtype, 0) + dealt
            amounts = ' and '.join(f'{amount} {dtype}' for dtype, amount in by_type.items())
            self.lines.append(f'{who} hits you {count}: {amounts} damage.' if swings > 1 else
                              f'{who} hits you: {amounts} damage.')
        if self.fight.get('pc_down'):
            self.lines.append('You go down.')

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
            if order and self.pc_turn_now() and not self.fight.get('pc_down'):
                self.lines.append('Your turn.')

    def public(self):
        return ' '.join(line for line in self.lines if line).strip()

    def events(self):
        evidence = f'Player declared: {self.action[:300]}. ' + ('; '.join(self.trace) or 'physical act') + '.'
        events = [{'type': 'scene_state', 'state': self.scene, 'evidence': evidence}]
        if self.fight:
            events.append({'type': 'combat_state', 'state': self.fight, 'evidence': evidence})
        for key, status in self.statuses.items():
            event = {'type': 'actor_status', 'actor': key, 'status': status, 'evidence': evidence}
            toward = getattr(self, 'fled_toward', {}).get(key)
            if toward:
                event['toward'] = toward
            events.append(event)
        return events


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
    sc = state.get('scene')
    if sc:
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

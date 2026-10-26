"""Companions: allied characters who fight on the engine, run by deterministic tactics (priority 3).

Brendon's companion research (t347u) asks for a benchmarked deterministic baseline before any
model plays an ally: Dragon Age's ordered tactics (first rule whose condition holds wins) with
Pillars-style resource permissions (a spending policy says which resources a rule may use).

Three isolations, each enforced here rather than promised in a prompt:

* Capability. A companion's legal actions come only from its own sheet (``check_sheet``):
  its weapon attacks with their stated numbers, its spells (mechanics from the SRD 5.1 table
  below, slots from the sheet), its listed features with uses, its items with counts. The
  engine validates every decision against ``legal`` and spends the resource itself.
* Knowledge. ``decide`` reads only ``observe``: its own sheet and ledger, the creatures the
  PC's side can see (revealed and present), visible conditions, and qualitative injury
  ('unhurt', 'hurt', 'bloodied', 'down'). Never AC, exact hit points, DCs, vulnerabilities,
  hidden creatures or room facts. ``decide`` is a pure function of that dict.
* Turn ownership. Companions act only in their own initiative slots; nothing here acts for,
  or commits on behalf of, the player's character (the loop stops at the PC's slot).

Sheets come from the player. Nothing is guessed: a missing number is refused, an unknown spell
is listed as not castable, a caster with slots and no prepared spells is flagged to ask.
Stdlib only, no model calls.
"""
import copy
import re

from .state_context import require

RANGED_WEAPON = re.compile(r'bow|crossbow|sling|dart|javelin', re.I)
ROLES = ('defender', 'striker', 'healer')
POLICIES = ('conserve', 'balanced', 'aggressive')
INCAPACITATING = ('incapacitated', 'paralyzed', 'petrified', 'stunned', 'unconscious')
VISIBLE_CONDITIONS = ('prone', 'poisoned', 'blinded', 'frightened', 'grappled', 'restrained', 'paralyzed',
                      'stunned', 'unconscious', 'dodging', 'stable')
DICE = re.compile(r'^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$')
# SRD 5.1 spell mechanics (CC-BY-4.0, Wizards of the Coast): data only, no rules text.
# kind attack: spell attack roll; save: target's save; heal: hit points; auto: no roll.
# cantrip scaling: the dice double at 5th level and triple at 11th.
SPELLS = {
    'fire bolt': {'level': 0, 'kind': 'attack', 'dice': '1d10', 'type': 'fire'},
    'ray of frost': {'level': 0, 'kind': 'attack', 'dice': '1d8', 'type': 'cold'},
    'eldritch blast': {'level': 0, 'kind': 'attack', 'dice': '1d10', 'type': 'force'},
    'sacred flame': {'level': 0, 'kind': 'save', 'save': 'dex', 'half': False, 'dice': '1d8', 'type': 'radiant'},
    'toll the dead': {'level': 0, 'kind': 'save', 'save': 'wis', 'half': False, 'dice': '1d8', 'type': 'necrotic'},
    'guiding bolt': {'level': 1, 'kind': 'attack', 'dice': '4d6', 'type': 'radiant', 'upcast': '1d6'},
    'magic missile': {'level': 1, 'kind': 'auto', 'dice': '3d4+3', 'type': 'force', 'upcast': '1d4+1'},
    'inflict wounds': {'level': 1, 'kind': 'attack', 'dice': '3d10', 'type': 'necrotic', 'upcast': '1d10',
                       'melee': True},
    'cure wounds': {'level': 1, 'kind': 'heal', 'dice': '1d8', 'upcast': '1d8', 'touch': True},
    'healing word': {'level': 1, 'kind': 'heal', 'dice': '1d4', 'upcast': '1d4'},
}
# Features and items the engine can run, by name (from the SRD). Anything else on a sheet is
# kept, shown as not run, and never used.
FEATURES = {'second wind': {'kind': 'self_heal', 'dice': '1d10', 'plus_level': True}}
ITEMS = {'potion of healing': {'kind': 'self_heal', 'dice': '2d4+2'}}


def _mod(score):
    return (int(score) - 10) // 2


def average(expr):
    match = DICE.match(str(expr))
    require(bool(match), f'damage {expr!r} is dice like 1d8+3')
    count, size, sign, bonus = match.groups()
    total = int(count) * (int(size) + 1) // 2
    return total + (int(bonus or 0) * (-1 if sign == '-' else 1))


def check_sheet(sheet):
    """(sheet, asks): the sheet as supplied, and what is missing or not run (never filled in).
    Refuses (InvalidChange) a sheet without the numbers a combatant needs."""
    require(isinstance(sheet, dict), 'A companion sheet is an object')
    asks = []
    for field in ('name', 'ac', 'hp', 'level'):
        require(field in sheet, f'companion sheet needs {field} (supplied by the player, never guessed)')
    require(isinstance(sheet.get('abilities'), dict) and 'dex' in sheet['abilities'],
            f"companion {sheet.get('name')}: abilities with dex are needed for initiative")
    for attack in sheet.get('attacks') or []:
        require({'name', 'to_hit', 'damage', 'type'} <= set(attack),
                f"companion {sheet['name']}: each attack states name, to_hit, damage dice and type")
        average(attack['damage'])
    spells = sheet.get('spells') or {}
    slots = {str(k): int(v) for k, v in (sheet.get('slots') or {}).items()}
    known = [s for group in spells.values() for s in group]
    if known:
        for field in ('spell_attack', 'spell_save_dc', 'spell_ability'):
            require(field in sheet, f"companion {sheet['name']}: a caster's sheet states {field}")
    if slots and not any(spells.get(level) for level in spells if level != 'cantrips'):
        asks.append(f"{sheet['name']} has spell slots but no prepared spells: which are prepared?")
    for name in known:
        if name.lower() not in SPELLS:
            asks.append(f"{sheet['name']}: {name} is not run by the engine (never cast)")
    for feature in sheet.get('features') or []:
        if feature.get('name', '').lower() not in FEATURES:
            asks.append(f"{sheet['name']}: feature {feature.get('name')} is not run by the engine")
        elif not isinstance(feature.get('uses'), int):
            asks.append(f"{sheet['name']}: how many uses of {feature['name']} remain?")
    for item in sheet.get('items') or []:
        if item.get('name', '').lower() not in ITEMS:
            asks.append(f"{sheet['name']}: item {item.get('name')} is not run by the engine")
    if not sheet.get('attacks') and not spells.get('cantrips'):
        asks.append(f"{sheet['name']}: no attacks or cantrips listed; it can only Dodge")
    return sheet, asks


def member(sheet, role, policy):
    """A roster entry: the sheet, its tactics, and a resource ledger the engine owns."""
    sheet, asks = check_sheet(sheet)
    require(role in ROLES, f'role is one of {ROLES}')
    require(policy in POLICIES, f'policy is one of {POLICIES}')
    ledger = {'slots': {str(k): int(v) for k, v in (sheet.get('slots') or {}).items()},
              'uses': {f['name'].lower(): f['uses'] for f in sheet.get('features') or []
                       if f.get('name', '').lower() in FEATURES and isinstance(f.get('uses'), int)},
              'items': {i['name'].lower(): int(i.get('count', 1)) for i in sheet.get('items') or []
                        if i.get('name', '').lower() in ITEMS}}
    return {'sheet': copy.deepcopy(sheet), 'role': role, 'policy': policy, 'asks': asks,
            'hp': int(sheet['hp']), 'max_hp': int(sheet['hp']), 'status': 'standing', 'conditions': [],
            'death_saves': {'successes': 0, 'failures': 0}, 'ledger': ledger}


def check_party(party):
    require(isinstance(party, dict) and len(party) <= 5, 'the party is up to five companions')
    for key, entry in party.items():
        require(key != 'pc' and isinstance(entry, dict) and entry.get('role') in ROLES and
                entry.get('policy') in POLICIES and isinstance(entry.get('ledger'), dict) and
                entry.get('status') in ('standing', 'dying', 'stable', 'dead'),
                f'party member {key} needs a sheet, role, policy, status and ledger')


def injury(hp, max_hp):
    if hp <= 0:
        return 'down'
    return 'unhurt' if hp >= max_hp else 'bloodied' if hp <= max_hp // 2 else 'hurt'


# -- the observation view: what a companion knows ------------------------------------------
def observe(fight, key):
    """The decision input. Built from the fight, but only of things the party can see."""
    me = fight.party[key]
    sheet = me['sheet']
    combat = fight.fight
    foes = []
    for foe in fight.hostiles():  # active: present, alive, revealed (hidden actors are not)
        actor = fight.state['actors'][foe]
        if actor.get('visible') is False or foe not in combat['hp']:
            continue
        foes.append({'id': foe, 'name': fight.labels.get(foe, foe),
                     'injury': injury(combat['hp'][foe], combat['max_hp'][foe]),
                     'engaged_with': sorted(w for w, f in (combat.get('marks') or {}).items() if f == foe)})
    allies = [{'id': 'pc', 'name': (fight.sheet or {}).get('name', 'you'),
               'injury': 'down' if combat.get('pc_down') else injury(
                   int(fight.pc_hp() or 1) - combat.get('pc_damage', 0), int(fight.pc_hp() or 1)),
               'conditions': [c for c in fight.conditions if c in VISIBLE_CONDITIONS]}]
    for other, entry in fight.party.items():
        if other != key and entry['status'] != 'dead':
            allies.append({'id': other, 'name': entry['sheet']['name'], 'injury': injury(entry['hp'], entry['max_hp']),
                           'conditions': [c for c in entry['conditions'] if c in VISIBLE_CONDITIONS]})
    return {'me': {'id': key, 'name': sheet['name'], 'role': me['role'], 'policy': me['policy'],
                   'injury': injury(me['hp'], me['max_hp']),
                   'conditions': [c for c in me['conditions'] if c in VISIBLE_CONDITIONS],
                   'options': legal_options(me)},
            'allies': allies, 'foes': foes, 'round': combat.get('round')}


def legal_options(me):
    """Every action its own sheet and ledger allow right now (names only, no numbers of foes)."""
    sheet, ledger = me['sheet'], me['ledger']
    out = [{'act': 'attack', 'with': a['name'], 'kind': 'damage', 'resource': None} for a in sheet.get('attacks') or []]
    spells = sheet.get('spells') or {}
    for name in spells.get('cantrips') or []:
        if name.lower() in SPELLS:
            out.append({'act': 'cast', 'with': name.lower(), 'kind': _kind(name), 'resource': None})
    open_slots = sorted(int(l) for l, n in ledger['slots'].items() if n > 0)
    for level, names in spells.items():
        if level == 'cantrips':
            continue
        for name in names:
            spell = SPELLS.get(name.lower())
            if spell and any(s >= spell['level'] for s in open_slots):
                out.append({'act': 'cast', 'with': name.lower(), 'kind': _kind(name), 'resource': 'slot'})
    for name, uses in ledger['uses'].items():
        if uses > 0:
            out.append({'act': 'feature', 'with': name, 'kind': 'self_heal', 'resource': 'use'})
    for name, count in ledger['items'].items():
        if count > 0:
            out.append({'act': 'item', 'with': name, 'kind': 'self_heal', 'resource': 'item'})
    out.append({'act': 'dodge', 'with': None, 'kind': 'defend', 'resource': None})
    return out


def _kind(name):
    return 'heal' if SPELLS[name.lower()]['kind'] == 'heal' else 'damage'


# -- ordered tactics --------------------------------------------------------------------------
# Each role is an ordered list of rule names; the first rule that yields a legal choice wins.
TACTICS = {
    'healer': ('heal_downed_ally', 'heal_bloodied_ally', 'self_heal_bloodied', 'finish_bloodied_foe',
               'hit_marked_foe', 'hit_any_foe'),
    'defender': ('self_heal_bloodied', 'guard_bloodied_ally', 'hit_marked_foe', 'hit_any_foe'),
    'striker': ('self_heal_bloodied', 'finish_bloodied_foe', 'hit_any_foe'),
}


def may_spend(policy, option, urgent):
    """Pillars-style permission: may this rule spend this option's resource?"""
    if option['resource'] is None:
        return True
    if policy == 'aggressive':
        return True
    if policy == 'balanced':
        return option['resource'] != 'slot' or urgent or option['kind'] == 'heal'
    return urgent  # conserve: only for a downed ally or its own life


def decide(obs):
    """A pure function of the observation: (decision, the rule that chose it)."""
    me, foes, allies = obs['me'], obs['foes'], obs['allies']
    options, policy = me['options'], me['policy']

    def pick(kind, urgent=False):
        fits = [o for o in options if o['kind'] == kind and may_spend(policy, o, urgent)]
        # spent resources first when allowed (strongest), else the free ones
        fits.sort(key=lambda o: (o['resource'] is None, o['act'] != 'cast'))
        if kind == 'damage' and policy != 'aggressive':
            fits.sort(key=lambda o: o['resource'] is not None)
        return fits[0] if fits else None

    marked = [f for f in foes if f['engaged_with']]
    for rule in TACTICS[me['role']]:
        if rule == 'heal_downed_ally':
            down = [a for a in allies if a['injury'] == 'down']
            choice = down and pick('heal', urgent=True)
            if choice:
                return {**choice, 'target': down[0]['id']}, rule
        elif rule == 'heal_bloodied_ally':
            hurt = [a for a in allies if a['injury'] == 'bloodied'] + ([me] if me['injury'] == 'bloodied' else [])
            choice = hurt and pick('heal')
            if choice:
                return {**choice, 'target': hurt[0]['id']}, rule
        elif rule == 'self_heal_bloodied':
            if me['injury'] == 'bloodied':
                choice = pick('self_heal', urgent=True)
                if choice:
                    return {**choice, 'target': me['id']}, rule
        elif rule == 'guard_bloodied_ally':
            hurt = {a['id'] for a in allies if a['injury'] in ('bloodied', 'down')}
            threats = [f for f in foes if hurt & set(f['engaged_with'])]
            choice = threats and pick('damage')
            if choice:
                return {**choice, 'target': threats[0]['id']}, rule
        elif rule == 'finish_bloodied_foe':
            weak = [f for f in foes if f['injury'] == 'bloodied']
            choice = weak and pick('damage')
            if choice:
                return {**choice, 'target': weak[0]['id']}, rule
        elif rule == 'hit_marked_foe':
            choice = marked and pick('damage')
            if choice:
                return {**choice, 'target': marked[0]['id']}, rule
        elif rule == 'hit_any_foe':
            choice = foes and pick('damage', urgent=len(foes) > 1 and policy == 'balanced')
            if choice:
                return {**choice, 'target': foes[0]['id']}, rule
    return {'act': 'dodge', 'with': None, 'kind': 'defend', 'resource': None, 'target': me['id']}, 'fallback'


# -- the engine side: validate, spend, resolve ------------------------------------------------
def validate(fight, key, decision):
    """The decision as the engine will run it, or the legal fallback with the reason."""
    me = fight.party[key]
    legal = legal_options(me)
    same = [o for o in legal if o['act'] == decision.get('act') and o['with'] == decision.get('with')]
    if not same:
        return {'act': 'dodge', 'with': None, 'target': key}, f"not on {me['sheet']['name']}'s sheet or spent"
    target = decision.get('target')
    if same[0]['kind'] == 'damage':
        if target not in [f['id'] for f in observe(fight, key)['foes']]:
            return {'act': 'dodge', 'with': None, 'target': key}, 'no such visible foe'
    elif same[0]['kind'] in ('heal', 'self_heal'):
        if same[0]['kind'] == 'self_heal':
            target = key
        elif target != 'pc' and target not in fight.party:
            return {'act': 'dodge', 'with': None, 'target': key}, 'no such ally'
    return {**same[0], 'target': target}, None


def companion_turn(fight, key):
    """One companion's slot: death save if down, skip if incapacitated, else tactics."""
    me = fight.party[key]
    name = me['sheet']['name']
    me['conditions'] = [c for c in me['conditions'] if c != 'dodging']
    if me['status'] == 'dead':
        return
    if me['status'] == 'dying':
        death_save(fight, key)
        return
    if me['status'] == 'stable' or any(c in INCAPACITATING for c in me['conditions']):
        fight.trace.append(f'{key} cannot act')
        return
    obs = observe(fight, key)
    decision, rule = decide(obs)
    action, refused = validate(fight, key, decision)
    fight.trace.append(f'{key} tactics {rule}: {action["act"]} {action.get("with") or ""} '
                       f'-> {action.get("target")}' + (f' (refused: {refused})' if refused else ''))
    resolve(fight, key, action)


def _upcast_dice(spell, level):
    dice = spell['dice']
    extra = level - spell['level']
    if extra <= 0 or not spell.get('upcast'):
        return [dice]
    return [dice] + [spell['upcast']] * extra


def _cantrip_mult(level):
    return 3 if level >= 11 else 2 if level >= 5 else 1


def resolve(fight, key, action):
    fight.acting = key  # damage it deals is credited to it (Fight.apply_damage)
    try:
        _resolve(fight, key, action)
    finally:
        fight.acting = None


def _resolve(fight, key, action):
    me = fight.party[key]
    sheet, ledger, name = me['sheet'], me['ledger'], me['sheet']['name']
    act, what, target = action['act'], action.get('with'), action.get('target')
    if act == 'dodge':
        me['conditions'].append('dodging')
        fight.lines.append(f'{name} takes the Dodge action.')
        return
    if act in ('feature', 'item'):
        table = FEATURES if act == 'feature' else ITEMS
        gain = average(table[what]['dice']) + (int(sheet['level']) if table[what].get('plus_level') else 0)
        (ledger['uses'] if act == 'feature' else ledger['items'])[what] -= 1
        heal(fight, key, gain)
        fight.lines.append(f'{name} uses {what.title()}' + (' and looks steadier.' if act == 'feature' else ' and drinks it down.'))
        return
    spell = SPELLS.get(what) if act == 'cast' else None
    slot = None
    if spell and spell['level'] > 0:
        slot = min(int(l) for l, n in ledger['slots'].items() if n > 0 and int(l) >= spell['level'])
        ledger['slots'][str(slot)] -= 1
        fight.trace.append(f'{key} spends a level {slot} slot on {what}: {ledger["slots"]}')
    if spell and spell['kind'] == 'heal':
        mod = _mod(sheet['abilities'].get(sheet['spell_ability'], 10))
        gain = sum(average(d) for d in _upcast_dice(spell, slot)) + mod
        heal(fight, target, gain, by=name)
        who = 'you' if target == 'pc' else fight.party[target]['sheet']['name']
        fight.lines.append(f'{name} casts {what.title()} on {who}.')
        return
    # damage
    foe_name = fight.labels.get(target, target).lower()
    stats = fight.stats(target)
    if spell:
        mult = _cantrip_mult(int(sheet['level'])) if spell['level'] == 0 else 1
        damage = sum(average(d) for d in _upcast_dice(spell, slot or 0)) * mult
        dtype = spell['type']
        if spell['kind'] == 'save':
            bonus = (stats.get('saves') or {}).get(spell['save'], 0)
            die = fight.die(f'party:{key}:save:{target}:r{fight.fight["round"]}')
            saved = die + bonus >= int(sheet['spell_save_dc'])
            fight.trace.append(f'{target} {spell["save"]} save d20 {die} + {bonus} vs DC {sheet["spell_save_dc"]}: '
                               f'{"saved" if saved else "failed"}')
            if saved and not spell['half']:
                fight.lines.append(f'{name} casts {what.title()} at the {foe_name}, who shrugs it off.')
                return
            damage = damage // 2 if saved else damage
            fight.lines.append(f'{name} casts {what.title()} at the {foe_name}.')
            fight.apply_damage(target, damage, dtype)
            return
        if spell['kind'] == 'auto':
            fight.lines.append(f'{name} casts {what.title()} at the {foe_name}.')
            fight.apply_damage(target, damage, dtype)
            return
        to_hit, verb = int(sheet['spell_attack']), f'casts {what.title()} at'
    else:
        attack = next(a for a in sheet['attacks'] if a['name'] == what)
        to_hit, damage, dtype, verb = int(attack['to_hit']), average(attack['damage']), attack['type'], \
            f'attacks the {foe_name} with'
        if not RANGED_WEAPON.search(what):
            fight.fight.setdefault('marks', {})[key] = target  # in melee with it: foes answer this
    die = fight.die(f'party:{key}:attack:{target}:r{fight.fight["round"]}')
    if 'poisoned' in me['conditions']:
        die = min(die, fight.die(f'party:{key}:attack:{target}:r{fight.fight["round"]}:dis'))
    ac = int(stats['ac'])
    hit = die == 20 or (die != 1 and die + to_hit >= ac)
    if die == 20:
        damage *= 2
    fight.trace.append(f'{key} {what}: d20 {die} + {to_hit} = {die + to_hit} vs AC {ac}: '
                       f'{"hit " + str(damage) if hit else "miss"}')
    line = f'{name} {verb} the {foe_name}' if spell else f'{name} {verb} {what}'
    if not hit:
        fight.lines.append(line + ' and misses.')
        return
    fight.lines.append(line + '.')
    fight.apply_damage(target, damage, dtype)


def heal(fight, target, amount, by=None):
    if target == 'pc':
        fight.heal(amount, f'{by or "an ally"} heals you')
        return
    entry = fight.party[target]
    entry['hp'] = min(entry['max_hp'], max(0, entry['hp']) + amount)
    if entry['status'] in ('dying', 'stable'):
        entry['status'] = 'standing'
        entry['death_saves'] = {'successes': 0, 'failures': 0}
        entry['conditions'] = [c for c in entry['conditions'] if c not in ('unconscious', 'stable')]
        fight.lines.append(f"{entry['sheet']['name']} gets back up.")
    fight.trace.append(f'{target} healed {amount}: {entry["hp"]}/{entry["max_hp"]}')


def death_save(fight, key):
    entry = fight.party[key]
    die = fight.die(f'party:{key}:death:r{fight.fight["round"]}')
    saves = entry['death_saves']
    name = entry['sheet']['name']
    if die == 20:
        heal(fight, key, 1)
        return
    saves['failures' if die < 10 else 'successes'] += 2 if die == 1 else 1
    fight.trace.append(f'{key} death save d20 {die}: {saves}')
    if saves['failures'] >= 3:
        entry['status'] = 'dead'
        fight.lines.append(f'{name} stops breathing.')
    elif saves['successes'] >= 3:
        entry['status'] = 'stable'
        entry['conditions'] = list(dict.fromkeys(entry['conditions'] + ['stable']))
        fight.lines.append(f'{name} is still down, but stable.')


def standing(fight):
    return [k for k, e in fight.party.items() if e['status'] == 'standing']


def foe_target(fight, foe):
    """Who a foe attacks, deterministically: a standing companion in melee with it (a defender
    first); else whoever visibly hurt it last, if that is a standing companion (a ranged or
    spellcasting attacker draws it too); else the PC. Downed companions are left alone. With
    the PC down, Kit's call (kit_acts downed) still decides: ``attack`` keeps each foe on its
    own fight as above, ``turn_away`` sends it at the standing companions instead."""
    up = standing(fight)
    marks = fight.fight.get('marks') or {}
    engaged = [k for k, f in marks.items() if f == foe and k in up]
    defenders = [k for k in engaged if fight.party[k]['role'] == 'defender']
    if defenders or engaged:
        return (defenders or engaged)[0]
    last = (fight.fight.get('attackers') or {}).get(foe)
    if last in up:
        return last
    if fight.fight.get('pc_down') and fight.fight.get('vs_downed') == 'turn_away' and up:
        return up[0]
    return 'pc'


def foe_attacks_companion(fight, foe, key):
    """The foe's attacks at a companion: Kit's d20 against the companion's AC, average damage."""
    entry = fight.party[key]
    name = entry['sheet']['name']
    who = fight.labels.get(foe, foe).lower()
    for index, attack in enumerate(fight.stats(foe).get('attacks') or []):
        if entry['status'] != 'standing':
            break
        die = fight.die(f'npc:{foe}:r{fight.fight["round"]}:{index}:{key}')
        if 'dodging' in entry['conditions']:
            die = min(die, fight.die(f'npc:{foe}:r{fight.fight["round"]}:{index}:{key}:dodge'))
        total = die + attack['to_hit']
        hit = die == 20 or (die != 1 and total >= int(entry['sheet']['ac']))
        dealt = attack['damage'] * (2 if die == 20 else 1)
        fight.trace.append(f'{foe} {attack["name"]} at {key}: d20 {die} + {attack["to_hit"]} = {total} vs AC '
                           f'{entry["sheet"]["ac"]}: {"hit " + str(dealt) if hit else "miss"}')
        if not hit:
            fight.lines.append(f"The {who}'s {attack['name']} misses {name}.")
            continue
        hurt_companion(fight, key, dealt)
        fight.lines.append(f"The {who}'s {attack['name']} hits {name}" +
                           (', who goes down.' if entry['status'] == 'dying' else '.'))


def hurt_companion(fight, key, dealt):
    entry = fight.party[key]
    if entry['status'] in ('dying', 'stable'):
        entry['status'] = 'dying'
        entry['death_saves']['failures'] += 1
        if entry['death_saves']['failures'] >= 3:
            entry['status'] = 'dead'
        return
    if dealt - entry['hp'] >= entry['max_hp']:
        entry['hp'], entry['status'] = 0, 'dead'  # massive damage (SRD)
        return
    entry['hp'] = max(0, entry['hp'] - dealt)
    if entry['hp'] == 0:
        entry['status'] = 'dying'
        entry['conditions'] = list(dict.fromkeys(entry['conditions'] + ['unconscious']))


def initiative(fight, key):
    entry = fight.party[key]
    bonus = entry['sheet'].get('initiative', _mod(entry['sheet']['abilities']['dex']))
    return fight.die(f'party:{key}:initiative') + int(bonus), int(bonus)


def summary(fight):
    """The short party line for the packet: who is up, hurt or down (no numbers)."""
    return {e['sheet']['name']: injury(e['hp'], e['max_hp']) if e['status'] == 'standing' else e['status']
            for e in fight.party.values()}

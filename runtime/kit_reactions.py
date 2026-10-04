"""The PC's reaction inventory, built from the sheet (PR-H; Brendon's requirement).

Any sheet, any class: spells with a casting time of 1 reaction, class/subclass/race features,
feats and items that use a reaction, and the opportunity attack every creature has. Each entry
says what event can open it (a small typed set, TRIGGERS), what it costs (a spell slot, uses per
short or long rest, or nothing), and its effect: an engine handler (EFFECTS) or "kit_adjudicates"
(the window opens and Kit rules the effect, flagged).

The inventory is engine state, like HP: ``state['pc_resources']`` holds it with the live slot and
use counts. It is built when the sheet loads and rebuilt on a rest (short: short-rest uses; long:
everything). Whether the reaction is spent this round lives on the fight (``reaction_used``) and
comes back at the start of the PC's turn. Spell reactions are cast by the player in Avrae
(``!cast shield``); the engine records the slot the cast used, never spends one silently.

Nothing is invented: a sheet entry the catalog does not know and whose own text does not say it
uses a reaction is not a reaction. ``gaps(sheet)`` lists what the sheet does not say.
"""
import copy
import hashlib
import json
import re

TRIGGERS = (
    'self_hit_by_attack',          # an attack roll hits the PC
    'self_targeted_by_magic_missile',
    'self_hit_by_ranged_weapon',   # Deflect Missiles
    'creature_succeeds',           # a creature the PC can see succeeds on an attack, check or save
    'self_fails_save',             # the PC fails a saving throw (Lucky Footwork: Dex)
    'ally_attacked_within_5ft',    # Protection, Sentinel
    'spell_cast_within_range',     # Counterspell, Mage Slayer
    'falling',                     # Feather Fall
    'foe_leaves_reach',            # the opportunity attack
    'elemental_damage_taken',      # Absorb Elements
    'creature_hits_you_within_range',  # Hellish Rebuke
    'custom',                      # the sheet's own words; Kit reads the trigger
)
EFFECTS = ('shield', 'silvery_barbs', 'absorb_elements', 'opportunity_attack', 'uncanny_dodge', 'chronal_shift')
ELEMENTS = ('acid', 'cold', 'fire', 'lightning', 'thunder')
KIT = 'kit_adjudicates'

# What the SRD (and the common published options) say about each known reaction. Names only:
# the sheet decides whether the PC has it.
CATALOG = {
    'shield': {'name': 'Shield', 'kind': 'spell', 'level': 1, 'effect': 'shield',
               'trigger': ['self_hit_by_attack', 'self_targeted_by_magic_missile']},
    'silvery_barbs': {'name': 'Silvery Barbs', 'kind': 'spell', 'level': 1, 'effect': 'silvery_barbs',
                      'trigger': ['creature_succeeds'], 'range_ft': 60},
    'absorb_elements': {'name': 'Absorb Elements', 'kind': 'spell', 'level': 1, 'effect': 'absorb_elements',
                        'trigger': ['elemental_damage_taken']},
    'counterspell': {'name': 'Counterspell', 'kind': 'spell', 'level': 3, 'effect': KIT,
                     'trigger': ['spell_cast_within_range'], 'range_ft': 60},
    'feather_fall': {'name': 'Feather Fall', 'kind': 'spell', 'level': 1, 'effect': KIT, 'trigger': ['falling']},
    'hellish_rebuke': {'name': 'Hellish Rebuke', 'kind': 'spell', 'level': 1, 'effect': KIT,
                       'trigger': ['creature_hits_you_within_range'], 'range_ft': 60},
    'uncanny_dodge': {'name': 'Uncanny Dodge', 'kind': 'feature', 'effect': 'uncanny_dodge',
                      'trigger': ['self_hit_by_attack']},
    'deflect_missiles': {'name': 'Deflect Missiles', 'kind': 'feature', 'effect': KIT,
                         'trigger': ['self_hit_by_ranged_weapon']},
    'protection': {'name': 'Protection (fighting style)', 'kind': 'feature', 'effect': KIT,
                   'trigger': ['ally_attacked_within_5ft'], 'needs': 'a shield'},
    # Chronurgy: after seeing a roll succeed or fail, force a reroll; the new roll stands.
    'chronal_shift': {'name': 'Chronal Shift', 'kind': 'feature', 'effect': 'chronal_shift',
                      'trigger': ['creature_succeeds'],
                      'range_ft': 30, 'recharge': 'long', 'uses': 2},
    'lucky_footwork': {'name': 'Lucky Footwork', 'kind': 'feature', 'effect': KIT, 'trigger': ['self_fails_save'],
                       'note': 'Dexterity saves: add 1d4'},
    'sentinel': {'name': 'Sentinel', 'kind': 'feat', 'effect': KIT,
                 'trigger': ['ally_attacked_within_5ft', 'foe_leaves_reach']},
    'mage_slayer': {'name': 'Mage Slayer', 'kind': 'feat', 'effect': KIT, 'trigger': ['spell_cast_within_range'],
                    'range_ft': 5},
    # Not a reaction of its own: it changes what the opportunity attack may be.
    'war_caster': {'name': 'War Caster', 'kind': 'feat', 'modifies': 'opportunity_attack',
                   'note': 'War Caster: may cast a 1-action, single-target spell instead (Kit adjudicates)'},
}
# Spells with a casting time other than a reaction (SRD and common options), so a sheet that lists them
# without a casting_time is not reported as a gap. Anything else unlisted is.
NOT_REACTIONS = frozenset('''alarm burning_hands charm_person color_spray comprehend_languages cure_wounds detect_magic
disguise_self expeditious_retreat false_life find_familiar fog_cloud grease healing_word identify jump longstrider
mage_armor magic_missile protection_from_evil_and_good ray_of_sickness sleep tasha_s_hideous_laughter
tenser_s_floating_disk thunderwave unseen_servant witch_bolt chromatic_orb ice_knife magic_weapon arcane_lock
blindness_deafness blur darkness darkvision detect_thoughts dragon_s_breath enlarge_reduce flaming_sphere
gentle_repose hold_person invisibility knock levitate locate_object magic_mouth mind_spike mirror_image misty_step
ray_of_enfeeblement rope_trick scorching_ray see_invisibility shatter spider_climb suggestion web animate_dead
bestow_curse blink clairvoyance dispel_magic fear fireball fly gaseous_form glyph_of_warding haste
hypnotic_pattern leomund_s_tiny_hut lightning_bolt magic_circle major_image nondetection phantom_steed
remove_curse sending sleet_storm slow stinking_cloud tongues vampiric_touch water_breathing'''.split())
OPPORTUNITY = {'id': 'opportunity_attack', 'name': 'Opportunity attack', 'kind': 'basic',
               'effect': 'opportunity_attack', 'trigger': ['foe_leaves_reach'], 'cost': None}
# Section names a sheet may use for features, feats and items (any of them, any format).
FEATURE_KEYS = ('features', 'class_features', 'subclass_features', 'racial_traits', 'traits', 'species_traits')
FEAT_KEYS = ('feats',)
ITEM_KEYS = ('magic_items', 'items', 'equipment', 'gear')
USES = re.compile(r'\((\d+)\s*/\s*(short|long)(?: or long)? rest\)', re.I)
REACTION_WORDS = re.compile(r'\b(?:1 reaction|as a reaction|use your reaction|uses? (?:its|their|your) reaction|'
                            r'reaction,? which you take)\b', re.I)


def ident(name):
    base = USES.sub('', str(name or '')).split('(')[0]
    return re.sub(r'[^a-z0-9]+', '_', base.casefold()).strip('_')


def _entries(value):
    """A sheet section as [(name, dict)] whether it is a list of names, a list of dicts or a dict."""
    if isinstance(value, dict):
        return [(str(k), v if isinstance(v, dict) else {'text': v}) for k, v in value.items()]
    out = []
    for item in value or ():
        if isinstance(item, dict) and item.get('name'):
            out.append((str(item['name']), item))
        elif isinstance(item, str):
            out.append((item, {}))
    return out


def spells(sheet):
    """{id: {'name', 'level', 'casting_time'?}} for leveled spells, from a {level: [names]} dict or
    a list of names or dicts (``level`` read from the dict; unknown otherwise)."""
    raw = (sheet or {}).get('spells') or {}
    out = {}
    if isinstance(raw, dict):
        groups = raw.items()
    else:
        groups = [(None, raw)]
    for level, names in groups:
        if str(level).casefold() in ('cantrips', 'cantrip', '0'):
            continue
        for name, detail in _entries(names if isinstance(names, (list, tuple, dict)) else [names]):
            spell_level = detail.get('level', level)
            if str(spell_level).casefold() in ('cantrip', '0'):
                continue
            entry = {'name': name, 'level': int(spell_level) if str(spell_level or '').isdigit() else None}
            if detail.get('casting_time'):
                entry['casting_time'] = str(detail['casting_time'])
            out[ident(name)] = entry
    return out


def slots(sheet):
    """{level: {'max', 'used'}} from {level: n}, {level: {max, used}} or [n1, n2, ...]."""
    raw = (sheet or {}).get('slots', (sheet or {}).get('spell_slots')) or {}
    if isinstance(raw, (list, tuple)):
        raw = {str(i + 1): n for i, n in enumerate(raw)}
    out = {}
    for level, value in (raw.items() if isinstance(raw, dict) else ()):
        if not str(level).isdigit():
            continue
        if isinstance(value, dict):
            top = int(value.get('max', value.get('total', 0)) or 0)
            used = int(value.get('used', top - int(value.get('remaining', top)) if 'remaining' in value else 0) or 0)
        else:
            top, used = int(value or 0), 0
        out[str(int(level))] = {'max': top, 'used': min(max(used, 0), top)}
    return out


def _uses(name, detail, known):
    match = USES.search(name) or USES.search(str(detail.get('uses') or ''))
    if isinstance(detail.get('uses'), int):
        return {'max': detail['uses'], 'used': 0, 'recharge': str(detail.get('recharge') or 'long').split()[0]}
    if match:
        return {'max': int(match.group(1)), 'used': 0, 'recharge': match.group(2).casefold()}
    if known.get('uses'):
        return {'max': known['uses'], 'used': 0, 'recharge': known['recharge'], 'assumed': True}
    return None


def _says_reaction(detail):
    words = ' '.join(str(detail.get(k) or '') for k in ('casting_time', 'activation', 'action_type', 'action',
                                                          'text', 'description'))
    return bool(REACTION_WORDS.search(words) or re.search(r'\breaction\b', str(detail.get('activation') or
                                                                                  detail.get('action_type') or
                                                                                  detail.get('casting_time') or '')))


def build(sheet):
    """The inventory for this sheet: {'v', 'sheet', 'reactions': [...], 'slots', 'uses'}."""
    reactions, uses, modifiers = [], {}, []
    for key, spell in spells(sheet).items():
        known = CATALOG.get(key)
        casting = spell.get('casting_time')
        if known and known['kind'] == 'spell':
            level = spell['level'] or known['level']
        elif casting and re.search(r'\breaction\b', casting, re.I):
            known, level = {'name': spell['name'], 'effect': KIT, 'trigger': ['custom']}, spell['level']
        else:
            continue
        reactions.append({'id': key, 'name': known['name'], 'source': f'spell (level {level})', 'kind': 'spell',
                          'trigger': list(known['trigger']), 'cost': {'slot': level or 1}, 'effect': known['effect'],
                          **({'range_ft': known['range_ft']} if known.get('range_ft') else {})})
    for keys, kind in ((FEATURE_KEYS, 'feature'), (FEAT_KEYS, 'feat'), (ITEM_KEYS, 'item')):
        for section in keys:
            for name, detail in _entries((sheet or {}).get(section)):
                key = ident(name)
                known = CATALOG.get(key)
                if known and known['kind'] == 'spell':
                    known = None
                if not known and not _says_reaction(detail):
                    continue
                if any(r['id'] == key for r in reactions):
                    continue
                if known and known.get('modifies'):
                    modifiers.append(known)
                    continue
                known = known or {'name': name, 'effect': KIT, 'trigger': ['custom'],
                                  'when': str(detail.get('text') or detail.get('description') or '')[:200]}
                use = _uses(name, detail, known)
                if use:
                    uses[key] = use
                reactions.append({'id': key, 'name': known['name'], 'kind': known.get('kind', kind),
                                  'source': f"{known.get('kind', kind)} ({section})", 'trigger': list(known['trigger']),
                                  'cost': {'uses': key} if use else None, 'effect': known['effect'],
                                  **{k: known[k] for k in ('range_ft', 'note', 'when', 'needs') if known.get(k)}})
    opportunity = dict(OPPORTUNITY, source='every creature (SRD)')
    notes = [m['note'] for m in modifiers if m['modifies'] == 'opportunity_attack']
    if notes:
        opportunity['note'] = '; '.join(notes)
    reactions.append(opportunity)
    return {'v': 1, 'sheet': _digest(sheet), 'reactions': reactions, 'slots': slots(sheet), 'uses': uses}


def _digest(sheet):
    return hashlib.sha256(json.dumps(sheet or {}, sort_keys=True).encode()).hexdigest()[:12]


def current(state):
    """The session's inventory: the committed one, or one built now from the sheet (an older
    session, or a sheet loaded before inventories existed)."""
    sheet = state.get('player_sheet') or {}
    held = state.get('pc_resources')
    if isinstance(held, dict) and held.get('sheet') == _digest(sheet):
        return held
    return build(sheet)


def check(resources):
    from .state_context import require
    require(isinstance(resources, dict) and isinstance(resources.get('reactions'), list) and
            isinstance(resources.get('slots'), dict) and isinstance(resources.get('uses'), dict),
            'pc_resources needs reactions, slots and uses')
    for level, slot in resources['slots'].items():
        require(isinstance(slot, dict) and 0 <= int(slot.get('used', 0)) <= int(slot.get('max', 0)),
                f'slot level {level} used must be within 0..max')
    return resources


def free_slot(resources, level=1):
    """The lowest slot level >= ``level`` with one left, or None."""
    for key in sorted(resources.get('slots') or {}, key=int):
        slot = resources['slots'][key]
        if int(key) >= int(level or 1) and slot['used'] < slot['max']:
            return key
    return None


def payable(resources, entry):
    cost = entry.get('cost') or {}
    if 'slot' in cost:
        return free_slot(resources, cost['slot']) is not None
    if 'uses' in cost:
        use = (resources.get('uses') or {}).get(cost['uses']) or {}
        return use.get('used', 0) < use.get('max', 0)
    return True


def entry(resources, key):
    return next((r for r in resources.get('reactions') or () if r['id'] == key), None)


def matching(resources, trigger, reaction_used=False, fit=None):
    """Ids of the reactions an event of type ``trigger`` can open now: the reaction unused, the cost
    payable, and ``fit(entry)`` (the event's own test: Shield only turns a hit it can turn)."""
    if reaction_used:
        return []
    return [r['id'] for r in resources.get('reactions') or ()
            if trigger in r['trigger'] and payable(resources, r) and (fit is None or fit(r))]


def spend(resources, key, slot_level=None):
    """A copy with the reaction's cost paid. A spell spends ``slot_level`` (the slot the Avrae cast
    used) or the lowest free one at its level. Returns (resources, slot level or None)."""
    out = copy.deepcopy(resources)
    found = entry(out, key)
    cost = (found or {}).get('cost') or {}
    if 'slot' in cost:
        level = str(slot_level) if slot_level and str(slot_level) in out['slots'] and \
            out['slots'][str(slot_level)]['used'] < out['slots'][str(slot_level)]['max'] else \
            free_slot(out, cost['slot'])
        if level:
            out['slots'][level]['used'] += 1
        return out, level
    if 'uses' in cost:
        use = out['uses'][cost['uses']]
        use['used'] = min(use['max'], use['used'] + 1)
    return out, None


def spend_slot(resources, level):
    """A leveled spell the PC cast on his own turn (Avrae is the truth; the engine keeps count)."""
    out = copy.deepcopy(resources)
    key = free_slot(out, level)
    if key:
        out['slots'][key]['used'] += 1
    return out, key


def rest(resources, sheet, kind):
    """A long rest restores everything; a short rest restores short-rest uses (and nothing else)."""
    if kind == 'long':
        return build(sheet)
    out = copy.deepcopy(resources)
    for use in out['uses'].values():
        if use.get('recharge') == 'short':
            use['used'] = 0
    return out


def line(resources):
    """The compact 'available reactions' line Kit sees in the session manifest. It changes only when
    something is spent or restored, so the cached manifest is resent only then."""
    parts = []
    for r in resources.get('reactions') or ():
        cost = r.get('cost') or {}
        if 'slot' in cost:
            what = f"spell, L{cost['slot']}+ slot, cast in Avrae: !cast {r['name'].casefold()}"
        elif 'uses' in cost:
            use = resources['uses'][cost['uses']]
            what = f"{use['max'] - use['used']}/{use['max']} per {use['recharge']} rest"
        else:
            what = 'no cost'
        flag = '' if r['effect'] in EFFECTS else ', Kit adjudicates'
        note = f"; {r['note']}" if r.get('note') and r['kind'] == 'basic' else ''
        parts.append(f"{r['name']} ({what}{flag}{note})")
    left = ', '.join(f"L{k} {s['max'] - s['used']}/{s['max']}" for k, s in sorted(resources.get('slots', {}).items(),
                                                                                  key=lambda kv: int(kv[0])))
    return 'Reactions: ' + '; '.join(parts) + (f'. Slots: {left}.' if left else '.')


def gaps(sheet):
    """What the sheet does not say that the inventory needs (never filled in by the engine)."""
    out = []
    unknown = [s['name'] for k, s in spells(sheet).items()
               if k not in CATALOG and k not in NOT_REACTIONS and not s.get('casting_time')]
    if unknown:
        out.append('spells with no casting_time and not in the catalog (a reaction among them is missed): '
                   + ', '.join(unknown))
    if any(s['level'] is None for s in spells(sheet).values()):
        out.append('spells with no level')
    if not slots(sheet):
        out.append('no spell slot counts')
    named_only = [name for section in FEATURE_KEYS + FEAT_KEYS + ITEM_KEYS
                  for name, detail in _entries((sheet or {}).get(section)) if not detail]
    if named_only:
        out.append('features, feats and items are names only (no activation or text), so only catalog names are '
                   'recognised: ' + ', '.join(named_only))
    if not (sheet or {}).get('feats'):
        out.append('no feats section (feats listed among features are matched by name)')
    if not any((sheet or {}).get(k) for k in ('weapons', 'attacks')):
        out.append('no weapons or attacks: the opportunity attack weapon (and reach) is unknown')
    assumed = [r['name'] for r in build(sheet)['reactions'] if (r.get('cost') or {}).get('uses') and
               build(sheet)['uses'][r['cost']['uses']].get('assumed')]
    if assumed:
        out.append('uses taken from the catalog, not the sheet: ' + ', '.join(assumed))
    return out

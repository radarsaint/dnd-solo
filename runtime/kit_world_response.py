"""Opt-in host judgment over existing actors; native effects, no fabricated stats."""
import copy
from . import kit_combat
from .state_context import require, in_combat

SCHEMA = {'type': 'object', 'additionalProperties': False,
 'properties': {'act': {'type': 'string', 'enum': ['wait', 'reveal', 'start_combat']},
                'actors': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 16},
                'why': {'type': 'string'}}, 'required': ['act', 'actors', 'why']}
RULE = ('world_response is your DM judgment about what the existing people do in response to '
        'this player action. Use their goals and knowledge; waiting and talking remain valid. '
        'Choose wait with [] or reveal/start_combat with offered actor ids, and explain why. '
        'This is an emergent choice, not a claim that the source prescribed it. Do not invent '
        'stats, outcomes, surprise or a PC action. The engine reveals chosen actors and, for '
        'combat, asks initiative. Do not name still-hidden actors in performance: narrate '
        'the player attempt; the engine appends the resulting reveal/initiative request.')

def offer(source, state, body):
    if body.get('table_talk') or body.get('kind') in ('opening', 'exit', 'threshold_look'):
        return None
    if in_combat(state) or state.get('pending_check'):
        return None
    people = {}
    stats = kit_combat.config(source).get('actors', {})
    for key, actor in (state.get('actors') or {}).items():
        if actor.get('location') != state.get('area') or actor.get('status') not in ('alive', 'hidden'):
            continue
        original = (source.get('actors') or {}).get(key) or {}
        goal = original.get('immediate_goal') or original.get('motive')
        # The verified scene adapter supplies goal/motive only when grounded.
        if not goal:
            continue
        people[key] = {'name': original.get('name') or key, 'goal': goal,
                       'can_fight': key in stats, 'hidden': actor.get('status') == 'hidden',
                       'goal_authority': original.get('goal_authority', 'existing_room'),
                       'goal_evidence': original.get('goal_evidence', [])}
    return {'actors': people, 'rule': RULE} if people else None

def check(value, offered, plan):
    if value is None:
        return None
    require(offered, 'world_response was not offered on this turn')
    require(isinstance(value, dict) and set(value) == {'act', 'actors', 'why'},
            'world_response needs act, actors and why')
    act, actors, why = value['act'], value['actors'], value['why']
    require(act in ('wait', 'reveal', 'start_combat'), 'Unknown world_response.act')
    require(isinstance(actors, list) and all(isinstance(k, str) for k in actors),
            'world_response.actors lists offered actor ids')
    require(len(actors) <= 16 and len(set(actors)) == len(actors), 'Duplicate or excessive response actors')
    require(isinstance(why, str) and 4 <= len(why.split()) and len(why) <= 1000,
            'world_response.why explains this choice in 4+ words (at most 1000 characters)')
    require(not plan.get('ask_player') and not plan.get('roll_call') and not plan.get('risk_confirm'),
            'Answer a player/check/risk question before advancing world_response')
    require(not any(plan.get(k) for k in ('handles', 'combat_acts', 'downed')),
            'Resolve offered player acts before adding world_response')
    require((not actors) if act == 'wait' else bool(actors), 'wait uses []; other responses need actors')
    require(all(k in offered['actors'] for k in actors), 'world_response names an absent or unavailable actor')
    if act == 'start_combat':
        require(all(offered['actors'][k]['can_fight'] for k in actors), 'An actor has no executable combat stats')
    return value

def apply(runtime, adjudicator, body, plan):
    response = check(plan.get('world_response'), body.get('world_response'), plan)
    if not response or response['act'] == 'wait':
        return body
    require(not body.get('declared'), 'Resolve one consequence declaration at a time')
    revision, _ = runtime.load()
    state = runtime.preview_state(revision, body['events'])
    current = offer(runtime.source(), state, body)
    check(response, current, plan)  # validate against live preview, not stale packet ids
    actors = response['actors']
    events = [{'type': 'actor_status', 'actor': key, 'status': 'alive', 'reveal': True,
               'evidence': 'Kit world response: ' + response['why']} for key in actors]
    after = runtime.preview_state(revision, list(body['events']) + events)
    hidden_names = [current['actors'][k]['name'] for k in actors if current['actors'][k]['hidden']]
    public = (', '.join(hidden_names) + (' steps into view.' if len(hidden_names) == 1 else ' step into view.')) if hidden_names else ''
    if response['act'] == 'start_combat':
        require(all(p['actor'] in actors for p in runtime.source().get('_timed_procedures') or []),
                'Include source-prescribed procedure actors when starting this encounter')
        fight = kit_combat.Fight(runtime.source(), after, revision, body['action'], check=None, roll=adjudicator.roll)
        fight.ensure_fight('kit_world_response')
        fight.fight['participants'] = list(actors)
        fight.fight['hp'] = {k: v for k, v in fight.fight['hp'].items() if k in actors}
        fight.fight['max_hp'] = dict(fight.fight['hp'])
        fight.fight['surprised'] = []  # this choice never awards surprise
        fight.trace.append('Kit chooses opposition: ' + response['why'])
        events += fight.events()
        if fight.lines:
            public += (' ' if public else '') + ' '.join(fight.lines)
        remaining=[k for k in actors if fight.active(k)]
        attack=('They move' if len(remaining)>1 else 'The opponent moves')+' to attack. ' if remaining else ''
        public += (' ' if public else '') + attack + 'Roll initiative.'
    result = copy.copy(body)
    result['declared'] = {'acts': {'world_response': response}, 'events': events,
                          'public': public, 'kind': 'world_response'}
    return result

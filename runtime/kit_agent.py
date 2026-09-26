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
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

from .state_context import InvalidChange, PROJECT_ROOT, Runtime, require


ROOM_FIXTURE = PROJECT_ROOT / 'tests/fixtures/level_01_area_06c.json'


class PendingRuling(Exception):
    """The room slice cannot establish this outcome without more game machinery."""


@dataclass(frozen=True)
class Resolution:
    kind: str
    public_event: str
    events: list


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
            public = 'You address the figures at the card table.'
        event = {'type': 'beat', 'tags': [kind],
                 'evidence': f'Player declared: {action[:500]}. Resolution: {public}'}
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
        'move': {'type': 'string', 'enum': [
            'npc_reply', 'kit_comment_then_npc', 'world_description', 'ruling', 'ask_clarification']},
        'public_brief': {'type': 'string'},
        'focus_actor': {'type': 'string', 'enum': ['uktarl', 'other', 'none']},
        'table_presence': {'type': 'string', 'enum': ['quiet', 'brief', 'present']},
        'tone': {'type': 'string', 'enum': ['wry', 'warm', 'threatening', 'curious', 'plain', 'quiet']},
    },
    'required': ['observed_event', 'goal', 'appraisal', 'memory_refs', 'move', 'public_brief',
                 'focus_actor', 'table_presence', 'tone'],
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
        instructions = (
            'You are Kit’s private decision stage, using the supplied canonical personality. '
            'Read DM-only information to keep the scene grounded. The event has already been adjudicated; '
            'do not change its result or request world writes. Copy accepted_public_event exactly into '
            'observed_event. Appraise its relation to one of Kit’s actual '
            'goals, or choose none. Reference only supplied episode IDs. Choose a high-level move and '
            'regulate her table presence. Write a brief public-safe direction for the performer '
            'that conveys the specific chosen move and Kit’s attitude without any hidden identity, '
            'clue, or private motive. Keep the trace brief and specific. Do not write dialogue. '
            'An NPC’s motives are distinct from Kit’s reaction. The player may surprise you; do not force a route.'
        )
        return self._complete(instructions, payload, 'kit_private_decision', PLAN_SCHEMA)

    def perform(self, payload):
        instructions = (
            'Perform the chosen DM move as Kit. You have only player-visible room facts and a bounded '
            'public resolution; do not invent discoveries, geometry, rules outcomes, NPC commitments, '
            'combat results, or player thoughts/actions. Never assume a hidden fact from prior knowledge. '
            'The Dealer is a practiced, self-important performer who wants a bargain; the other card '
            'players have no established individual voice. Keep NPC speech separate from Kit’s direct '
            'table comments. Follow the selected public brief, tone, and table presence; quiet means '
            'no Kit segment. The brief conveys a choice, not authority to invent facts. '
            'The accepted event will be displayed before your segments on physical/check turns; '
            'do not repeat it verbatim. Leave a real decision for the player. '
            'A mechanically consequential unsupported action should invite clarification, not resolve itself.'
        )
        return self._complete(instructions, payload, 'kit_public_performance', SPEECH_SCHEMA)


def check_plan(plan, episodes, public_event):
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
    for field in ('move', 'focus_actor', 'table_presence', 'tone'):
        require(plan[field] in PLAN_SCHEMA['properties'][field]['enum'], f'Invalid {field}')
    require(plan['move'] != 'kit_comment_then_npc' or plan['table_presence'] != 'quiet',
            'Chosen move conflicts with quiet table presence')
    require(isinstance(plan['public_brief'], str) and
            0 < len(plan['public_brief'].strip()) <= 350, 'Invalid public performance brief')


def check_public_content(text, public_view, player_action):
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


def check_speech(speech, plan, public_view, player_action):
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
    spoken = '\n'.join(f"{segment['speaker']}: {segment['text'].strip()}" for segment in segments)
    check_public_content(spoken, public_view, player_action)
    return spoken


class KitAgent:
    def __init__(self, runtime, model, adjudicator=None):
        self.runtime = runtime
        self.model = model
        self.adjudicator = adjudicator or Room6CAdjudicator()

    def turn(self, action, turn_id=None, use_memory=True):
        require(isinstance(action, str) and 0 < len(action.strip()) <= 1000,
                'Player action must be 1–1000 characters')
        revision, state = self.runtime.load()
        turn_id = turn_id or str(uuid.uuid4())
        resolution = self.adjudicator.resolve(action, revision, state)
        public_view = self.runtime.preview(revision, resolution.events)
        context = self.runtime.context()
        episodes = state.get('kit', {}).get('episodes', [])[-8:] if use_memory else []
        plan = self.model.plan({
            'personality_core': context['personality_core'],
            'dm_context': context['dm_context'],
            'kit_state': {'episodes': episodes,
                          'current_appraisal': state.get('kit', {}).get('current_appraisal') if use_memory else None},
            'player_action': action, 'accepted_public_event': resolution.public_event,
            'action_kind': resolution.kind,
        })
        check_plan(plan, episodes, resolution.public_event)
        check_public_content(plan['public_brief'], public_view, action)
        public_history = [{'player_input': turn['player_input'], 'spoken': turn['spoken'][-2000:]}
                          for turn in self.runtime.recent_kit_turns(limit=6)]
        performance_payload = {
            'personality_core': context['personality_core'],
            'player_view_after_event': public_view,
            'player_action': action, 'accepted_public_event': resolution.public_event,
            'action_kind': resolution.kind, 'public_history': public_history,
            'selected_move': {
                'move': plan['move'],
                'focus_actor': {'uktarl': 'Dealer', 'other': 'Card player',
                                'none': 'none'}[plan['focus_actor']],
                'table_presence': plan['table_presence'], 'tone': plan['tone'],
                'brief': plan['public_brief'],
            },
        }
        for attempt in range(2):
            speech = self.model.perform(performance_payload)
            try:
                spoken = check_speech(speech, plan, public_view, action)
                break
            except InvalidChange:
                if attempt:
                    raise
                performance_payload['retry_instruction'] = (
                    'The previous output failed the public visibility or format check. '
                    'Use only supplied player-visible facts and accepted event.')
        if resolution.kind != 'social':
            spoken = f'Narrator: {resolution.public_event}\n{spoken}'
        record = {'player_input': action, 'public_event': resolution.public_event,
                  'trace': plan, 'spoken': spoken}
        next_revision = self.runtime.commit_kit_turn(turn_id, revision, resolution.events, record)
        return {'revision': next_revision, 'turn_id': turn_id,
                'public_event': resolution.public_event, 'spoken': spoken}


def describe_view(view):
    lines = [view['area'], '']
    lines.extend(view['known_facts_here'])
    lines.extend(edge['description'] for edge in view['exits'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'play', 'trace'])
    parser.add_argument('--db', default='kit-06c.sqlite')
    parser.add_argument('--model', help='OpenAI Responses API model for private decision and performance')
    parser.add_argument('--perception', type=int, help='Test character Wisdom (Perception) modifier')
    parser.add_argument('--insight', type=int, help='Test character Wisdom (Insight) modifier')
    parser.add_argument('--no-memory', action='store_true', help='Ablation: hide Kit’s prior episodes from her decision stage')
    args = parser.parse_args()
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = json.loads(ROOM_FIXTURE.read_text(encoding='utf-8'))
            runtime.initialize(source, source['starting_area'])
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'trace':
            print(json.dumps(runtime.recent_kit_turns(), indent=2, ensure_ascii=False))
        else:
            if not args.model:
                parser.error('play requires --model YOUR_MODEL_ID')
            if not os.environ.get('OPENAI_API_KEY'):
                parser.error('play requires OPENAI_API_KEY in the process environment')
            model = OpenAIResponsesModel(args.model)
            agent = KitAgent(runtime, model, Room6CAdjudicator(args.perception, args.insight))
            print('Kit’s area 6c test. Enter an action, or /quit. Private traces: separate trace command.')
            print(describe_view(runtime.player_view()))
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


if __name__ == '__main__':
    main()

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
from pathlib import Path

from .state_context import InvalidChange, PROJECT_ROOT, Runtime, StaleTurn, require


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
        'public_brief': {'type': 'object', 'additionalProperties': False,
                         'properties': {key: {'type': 'string'} for key in
                                        ('objective', 'tactic', 'visible_cue', 'player_opening')},
                         'required': ['objective', 'tactic', 'visible_cue', 'player_opening']},
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

ONE_PASS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'decision': PLAN_SCHEMA, 'performance': SPEECH_SCHEMA},
    'required': ['decision', 'performance'],
}

PRIVATE_INSTRUCTIONS = (
    'You are Kit’s private decision stage, using the supplied canonical personality. '
    'Read DM-only information to keep the scene grounded. The event has already been adjudicated; '
    'do not change its result or request world writes. Copy accepted_public_event exactly into '
    'observed_event. Appraise its relation to one of Kit’s actual '
    'goals, or choose none. Reference only supplied episode IDs. Choose a high-level move and '
    'regulate her table presence. In public_brief choose an immediate objective, a tactic '
    'that pursues it, one observable action grounded in the room, and a real opening for '
    'the player. Use the actor’s private motives to decide what they try, but phrase the '
    'brief as safe direction for a performer who sees only the public scene. If action_kind '
    'is opening, choose world_description and frame the people and pressure before the '
    'player acts; the performance also needs the dealer’s first utterance. Show Kit’s '
    'taste through the choice of beat. Do not include hidden identities, clues, or motives. '
    'Keep the trace brief and specific. Do not write dialogue. '
    'An NPC’s motives are distinct from Kit’s reaction. The player may surprise you; do not force a route.'
)

PUBLIC_INSTRUCTIONS = (
    'Perform the chosen DM move as Kit. You have only player-visible room facts and a bounded '
    'public resolution; do not invent discoveries, geometry, rules outcomes, NPC commitments, '
    'combat results, or player thoughts/actions. Never assume a hidden fact from prior knowledge. '
    'Use the supplied authored actor cards to give the Dealer a recognizable vocal signature '
    'and physical touchstone across turns. Text can describe a voice and enact its rhythm; '
    'it cannot supply an audible accent. Avoid phonetic stereotypes and repeated catchphrases. '
    'If action_kind is opening, frame a scene in motion rather than listing the room inventory; '
    'telegraph the public social and exploration invitations without announcing a hidden truth. '
    'On a social reply, react to the player’s actual words. A character may take a few sentences '
    'to test, tempt, threaten, or tell a short story when it earns the space, but stop at a real '
    'player decision. Let a second card player react only when that changes the scene. '
    'Keep NPC speech separate from Kit’s direct table comments. '
    'Follow the selected public brief, tone, and table presence; quiet means '
    'no Kit segment. The brief conveys a choice, not authority to invent facts. '
    'The accepted event will be displayed before your segments on physical/check turns; '
    'do not repeat it verbatim. In a social scene, let the NPC pursue a specific objective '
    'through a response, action, or question grounded in the room; a price or fact alone is '
    'rarely the whole exchange. Give the player something meaningful to answer or act on. '
    'Do not pad the turn with generic banter or extra speakers. Leave a real decision for the player. '
    'A mechanically consequential unsupported action should invite clarification, not resolve itself.'
)

ONE_PASS_INSTRUCTIONS = (
    'For live chat, produce one object with decision first and performance second. '
    'Apply the private decision instructions to the private input, then write the public '
    'performance using only the public input, accepted event, and the decision’s checked '
    'public_brief, move, tone, focus actor, and table presence. Keep the decision brief. '
    'The decision is an appraisal and concrete DM move, not a justification of dialogue. '
    'The performance must remain grounded and give the player a meaningful response. '
    'This faster path is an experiment; it does not establish the same causal separation '
    'as the staged path.\n\nPRIVATE DECISION: ' + PRIVATE_INSTRUCTIONS +
    '\n\nPUBLIC PERFORMANCE: ' + PUBLIC_INSTRUCTIONS
)


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
        return self._complete(PRIVATE_INSTRUCTIONS, payload, 'kit_private_decision', PLAN_SCHEMA)

    def perform(self, payload):
        return self._complete(PUBLIC_INSTRUCTIONS, payload, 'kit_public_performance', SPEECH_SCHEMA)


def check_plan(plan, episodes, public_event, action_kind=None):
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
    require(action_kind != 'opening' or plan['move'] == 'world_description',
            'Room entry needs a world description')
    brief = plan['public_brief']
    require(isinstance(brief, dict) and set(brief) ==
            {'objective', 'tactic', 'visible_cue', 'player_opening'} and
            all(isinstance(value, str) and 0 < len(value.strip()) <= 240
                for value in brief.values()), 'Invalid public performance brief')


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


def check_speech(speech, plan, public_view, player_action, action_kind=None):
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
    require(action_kind != 'opening' or
            all(any(segment['speaker'] == speaker for segment in segments)
                for speaker in ('Narrator', 'Dealer')),
            'Room entry needs narration and the dealer')
    spoken = '\n'.join(f"{segment['speaker']}: {segment['text'].strip()}" for segment in segments)
    check_public_content(spoken, public_view, player_action)
    return spoken


def prepare_inputs(runtime, revision, state, action, resolution, use_memory):
    public_view = runtime.preview(revision, resolution.events)
    context = runtime.context()
    if context['revision'] != revision:
        raise StaleTurn(f'Expected revision {revision}; current is {context["revision"]}')
    episodes = state.get('kit', {}).get('episodes', [])[-8:] if use_memory else []
    body = {'action': action, 'events': resolution.events, 'kind': resolution.kind,
            'public_event': resolution.public_event, 'public_view': public_view,
            'use_memory': use_memory}
    planning_input = {
        'personality_core': context['personality_core'],
        'dm_context': context['dm_context'],
        'kit_state': {'episodes': episodes,
                      'current_appraisal': state.get('kit', {}).get('current_appraisal')
                      if use_memory else None},
        'player_action': action, 'accepted_public_event': resolution.public_event,
        'action_kind': resolution.kind,
    }
    return revision, body, planning_input


def prepare_turn(runtime, adjudicator, action, use_memory=True):
    require(isinstance(action, str) and 0 < len(action.strip()) <= 1000,
            'Player action must be 1–1000 characters')
    revision, state = runtime.load()
    resolution = adjudicator.resolve(action, revision, state)
    return prepare_inputs(runtime, revision, state, action, resolution, use_memory)


def prepare_opening(runtime):
    revision, state = runtime.load()
    require(revision == 0 and state['area'] == 'area_06c',
            'The room entry is available only before the first turn')
    resolution = Resolution('opening', 'A newcomer has reached the card room.', [
        {'type': 'beat', 'tags': ['scene_entry'],
         'evidence': 'Initial framing of area 6c before the player acts.'}])
    return prepare_inputs(runtime, revision, state, '[scene entry]', resolution, use_memory=True)


def public_performance_base(runtime, body):
    public_history = [{'player_input': turn['player_input'], 'spoken': turn['spoken'][-2000:]}
                      for turn in runtime.recent_kit_turns(limit=6)]
    return {
        'personality_core': runtime.context()['personality_core'],
        'player_view_after_event': body['public_view'],
        'player_action': body['action'], 'accepted_public_event': body['public_event'],
        'action_kind': body['kind'], 'public_history': public_history,
        'performance_reference': runtime.source().get('public_performance', {}),
    }


def performance_input(runtime, body, plan):
    payload = public_performance_base(runtime, body)
    payload['selected_move'] = {
            'move': plan['move'],
            'focus_actor': {'uktarl': 'Dealer', 'other': 'Card player',
                            'none': 'none'}[plan['focus_actor']],
            'table_presence': plan['table_presence'], 'tone': plan['tone'],
            'brief': plan['public_brief'],
    }
    return payload


def checked_record(body, plan, speech):
    spoken = check_speech(speech, plan, body['public_view'], body['action'], body['kind'])
    if body['kind'] not in ('social', 'opening'):
        spoken = f"Narrator: {body['public_event']}\n{spoken}"
    return {'player_input': body['action'], 'public_event': body['public_event'],
            'trace': plan, 'spoken': spoken}


class KitAgent:
    def __init__(self, runtime, model, adjudicator=None):
        self.runtime = runtime
        self.model = model
        self.adjudicator = adjudicator or Room6CAdjudicator()

    def turn(self, action, turn_id=None, use_memory=True):
        revision, body, planning_input = prepare_turn(
            self.runtime, self.adjudicator, action, use_memory)
        return self._run(revision, body, planning_input, turn_id)

    def opening(self, turn_id=None):
        revision, body, planning_input = prepare_opening(self.runtime)
        return self._run(revision, body, planning_input, turn_id)

    def _run(self, revision, body, planning_input, turn_id):
        turn_id = turn_id or str(uuid.uuid4())
        plan = self.model.plan(planning_input)
        check_plan(plan, planning_input['kit_state']['episodes'], body['public_event'], body['kind'])
        check_public_content(json.dumps(plan['public_brief']), body['public_view'], body['action'])
        performance_payload = performance_input(self.runtime, body, plan)
        for attempt in range(2):
            speech = self.model.perform(performance_payload)
            try:
                record = checked_record(body, plan, speech)
                break
            except InvalidChange:
                if attempt:
                    raise
                performance_payload['retry_instruction'] = (
                    'The previous output failed the public visibility or format check. '
                    'Use only supplied player-visible facts and accepted event.')
        next_revision = self.runtime.commit_kit_turn(turn_id, revision, body['events'], record)
        return {'revision': next_revision, 'turn_id': turn_id,
                'public_event': body['public_event'], 'spoken': record['spoken']}


class KitChatBridge:
    """Host this model loop in an assistant chat, with no API credential in Python."""
    def __init__(self, runtime, adjudicator=None):
        self.runtime = runtime
        self.adjudicator = adjudicator or Room6CAdjudicator()

    def prepare(self, action=None, turn_id=None, use_memory=True, one_pass=False, opening=False):
        turn_id = turn_id or str(uuid.uuid4())
        if opening:
            require(action is None, 'Room opening does not take a player action')
            revision, body, planning_input = prepare_opening(self.runtime)
        else:
            revision, body, planning_input = prepare_turn(
                self.runtime, self.adjudicator, action, use_memory)
        body['host_mode'] = 'one_pass' if one_pass else 'staged'
        self.runtime.stage_kit_turn(turn_id, revision, body)
        if one_pass:
            return {'turn_id': turn_id, 'stage': 'one_pass',
                    'instructions': ONE_PASS_INSTRUCTIONS, 'schema': ONE_PASS_SCHEMA,
                    'input': {'private': planning_input,
                              'public': public_performance_base(self.runtime, body)}}
        return {'turn_id': turn_id, 'stage': 'private_decision',
                'instructions': PRIVATE_INSTRUCTIONS, 'schema': PLAN_SCHEMA,
                'input': planning_input}

    def decide(self, turn_id, plan):
        pending = self.runtime.pending_kit_turn(turn_id)
        revision, state = self.runtime.load()
        if revision != pending['revision']:
            raise StaleTurn(f"Expected revision {pending['revision']}; current is {revision}")
        body = pending['body']
        require(body['host_mode'] == 'staged', 'Use complete for a one-pass turn')
        episodes = state.get('kit', {}).get('episodes', [])[-8:] if body['use_memory'] else []
        check_plan(plan, episodes, body['public_event'], body['kind'])
        check_public_content(json.dumps(plan['public_brief']), body['public_view'], body['action'])
        payload = performance_input(self.runtime, body, plan)
        self.runtime.save_kit_plan(turn_id, revision, plan)
        return {'turn_id': turn_id, 'stage': 'public_performance',
                'instructions': PUBLIC_INSTRUCTIONS, 'schema': SPEECH_SCHEMA,
                'input': payload}

    def finish(self, turn_id, speech):
        pending = self.runtime.pending_kit_turn(turn_id)
        require(pending['body']['host_mode'] == 'staged', 'Use complete for a one-pass turn')
        require(pending['plan'] is not None, 'Complete private decision before performance')
        body = pending['body']
        record = checked_record(body, pending['plan'], speech)
        revision = self.runtime.commit_kit_turn(
            turn_id, pending['revision'], body['events'], record, consume_pending=True)
        return {'revision': revision, 'turn_id': turn_id,
                'public_event': body['public_event'], 'spoken': record['spoken']}

    def complete(self, turn_id, output):
        """Validate and commit one model output in one host round trip."""
        require(isinstance(output, dict) and set(output) == {'decision', 'performance'},
                'Expected a decision and performance')
        pending = self.runtime.pending_kit_turn(turn_id)
        body, plan = pending['body'], output['decision']
        require(body['host_mode'] == 'one_pass', 'Use decide and finish for a staged turn')
        revision, state = self.runtime.load()
        if revision != pending['revision']:
            raise StaleTurn(f"Expected revision {pending['revision']}; current is {revision}")
        episodes = state.get('kit', {}).get('episodes', [])[-8:] if body['use_memory'] else []
        check_plan(plan, episodes, body['public_event'], body['kind'])
        check_public_content(json.dumps(plan['public_brief']), body['public_view'], body['action'])
        self.runtime.save_kit_plan(turn_id, revision, plan)
        record = checked_record(body, plan, output['performance'])
        next_revision = self.runtime.commit_kit_turn(
            turn_id, revision, body['events'], record, consume_pending=True)
        return {'revision': next_revision, 'turn_id': turn_id,
                'public_event': body['public_event'], 'spoken': record['spoken']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'view', 'prepare', 'decide', 'finish', 'complete',
                                            'play', 'trace'])
    parser.add_argument('--db', default='kit-06c.sqlite')
    parser.add_argument('--model', help='Optional standalone Responses API model for play')
    parser.add_argument('--perception', type=int, help='Test character Wisdom (Perception) modifier')
    parser.add_argument('--insight', type=int, help='Test character Wisdom (Insight) modifier')
    parser.add_argument('--no-memory', action='store_true', help='Ablation: hide Kit’s prior episodes from her decision stage')
    parser.add_argument('--one-pass', action='store_true', help='One model output for live chat; use complete to commit')
    parser.add_argument('--opening', action='store_true', help='Prepare the initial scene entry instead of a player action')
    parser.add_argument('--action', help='Player action for prepare')
    parser.add_argument('--action-file', help='UTF-8 player action file for prepare')
    parser.add_argument('--turn-id', help='Turn ID returned by prepare')
    parser.add_argument('--input-file', help='JSON plan, speech, or combined output; - reads stdin')
    args = parser.parse_args()
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = json.loads(ROOM_FIXTURE.read_text(encoding='utf-8'))
            runtime.initialize(source, source['starting_area'])
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'view':
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'trace':
            print(json.dumps(runtime.recent_kit_turns(), indent=2, ensure_ascii=False))
        elif args.command in ('prepare', 'decide', 'finish', 'complete'):
            bridge = KitChatBridge(runtime, Room6CAdjudicator(args.perception, args.insight))
            try:
                if args.command == 'prepare':
                    if args.opening:
                        if args.action is not None or args.action_file is not None:
                            parser.error('--opening does not take an action')
                        action = None
                    else:
                        if (args.action is None) == (args.action_file is None):
                            parser.error('prepare requires exactly one of --action or --action-file')
                        action = (args.action if args.action_file is None else
                                  Path(args.action_file).read_text(encoding='utf-8').strip())
                    result = bridge.prepare(action, args.turn_id, use_memory=not args.no_memory,
                                            one_pass=args.one_pass, opening=args.opening)
                else:
                    if not args.turn_id or not args.input_file:
                        parser.error(f'{args.command} requires --turn-id and --input-file')
                    raw = sys.stdin.read() if args.input_file == '-' else Path(args.input_file).read_text(encoding='utf-8')
                    submitted = json.loads(raw)
                    result = (bridge.decide(args.turn_id, submitted) if args.command == 'decide' else
                              bridge.finish(args.turn_id, submitted) if args.command == 'finish' else
                              bridge.complete(args.turn_id, submitted))
            except PendingRuling as exc:
                result = {'stage': 'pending_ruling', 'message': str(exc), 'committed': False}
            except InvalidChange as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc), 'committed': False},
                                 ensure_ascii=False), file=sys.stderr)
                return 2
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if not args.model:
                parser.error('standalone play requires --model; for ChatGPT use prepare/decide/finish')
            if not os.environ.get('OPENAI_API_KEY'):
                parser.error('standalone play requires OPENAI_API_KEY; for ChatGPT use prepare/decide/finish')
            model = OpenAIResponsesModel(args.model)
            agent = KitAgent(runtime, model, Room6CAdjudicator(args.perception, args.insight))
            print('Kit’s area 6c test. Enter an action, or /quit. Private traces: separate trace command.')
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

"""The room's story brief (runtime/kit_brief.py): Kit knows what the scene is about.

In the live 6c run (2026-10-03) Kit read the room as a list of mechanics: the vampire act
never served its purpose (scaring newcomers into the toll) and the toll was never demanded.
These tests pin the general mechanism: the brief is in the private input on entry and every
turn after, an undelivered primary hook is raised by its NPC within its beats, and nothing in
the brief reaches the performer except a public-safe hook line when it is overdue."""
import copy
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from runtime import kit_agent, kit_brief, kit_guards
from runtime.kit_agent import KitAgent, Resolution, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, MIRROR, RecordingModel, exchange_speech, with_raised_hooks
from kit_policy import rejections_raise

SOURCE = json.loads(FIXTURE.read_text())
FEASIBILITY = json.loads((Path(__file__).parent / 'fixtures/feasibility_room.json').read_text())
# The live player turns before the toll should have come up (transcripts/session.md T1-T3).
# T1 drops its price question (a detail request this scripted double does not answer); T2 is
# the host's accepted rewording.
LIVE = (
    'Nik steps to the edge of the candlelight but stays a pace back from the empty chair, hand resting '
    'easy near his belt. "Not lost. Maybe looking." While he talks, he watches the fourth player, the '
    'one who never looked up, and glances at the coin towers.',
    'Nik sits down in the chair and sets a single copper on the table. "I count well enough. Twenty-one." '
    'He nods at the silver ring by the dealer\'s stack. "Someone lose that, or is it the pot?" While the '
    'dealer answers, Nik watches his face and the way he talks: does the accent hold up, and is he putting '
    'on a show? Insight check: 1d20 (17) + 4 = `21`',
    'Nik leans back like he\'s buying the act and keeps his eyes on the dealer\'s hands. "A dwarf, huh. '
    'He get to keep his blood, at least?" He smiles a little. "Deal." He\'s watching the shuffle and the '
    'deal for anything off, like a palmed card, a crimp, or a glance at the quiet one with their hand on '
    'their chest. Perception check: 2d20kh1 (11, 5) + 4 = `15`',
)
SECRETS = ('doppelganger', 'stone key', 'marked', 'harria', 'thugs', 'pose as vampires', 'not undead',
           'scares newcomers', 'pinprick', 'cheat')


ENTRY_SPEECH = {'segments': [
    {'speaker': 'Narrator', 'text': ('A card pauses between the dealer\u2019s fingers mid-deal. Four pale '
                                     'players sit among scattered coins and a silver ring, and one of '
                                     'them slowly turns to look at the doorway. North of the table, a '
                                     'carved mountain crowded with tiny dwarves hangs above a recessed '
                                     'stone tub.')},
    {'speaker': 'Dealer', 'text': ('Well now. A visitor, and on such a slow night. Come in, come in; '
                                   'the table is far friendlier than the corridor. Care to make an offer, '
                                   'or shall I name one?')}]}


class Entering(RecordingModel):
    """RecordingModel that can also frame the room entry."""

    def plan(self, payload):
        plan = super().plan(payload)
        action = payload['player_action']  # the live turns are long: keep each field in bounds
        plan['appraisal']['cause'] = action[:300]
        plan['improv_read']['player_bid'] = action[:300]
        if payload.get('action_kind') != 'opening':
            plan['public_brief']['reply_to'] = action[:200]
        if payload.get('action_kind') == 'opening':
            plan.update(move='world_description', table_presence='quiet', public_brief={
                'objective': 'Frame the interruption of the card game.',
                'tactic': 'Let the dealer weigh the visitor as a potential customer.',
                'visible_cue': 'The dealer suspends a card above the table.',
                'player_opening': 'The newcomer can speak, observe, or leave.',
                'reply_to': 'none', 'scope': 'feature',
                'kit_focus': 'Let the interrupted game, not the room inventory, greet the newcomer.',
                'callback': 'none', 'mirror': MIRROR, 'npc_notice': 'none'})
        return plan

    def perform(self, payload, performance_variant='current'):
        if payload.get('action_kind') == 'opening':
            self.performances.append(payload.copy())
            return copy.deepcopy(ENTRY_SPEECH)
        return super().perform(payload, performance_variant)


class IgnoresHooks(Entering):
    """A performer that plays the table but never raises the overdue hook (the live failure)."""

    def perform(self, payload, performance_variant='current'):
        return super().perform(dict(payload, raise_now=None), performance_variant)


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)

    def start(self, source=SOURCE, area='area_06c'):
        self.runtime.initialize(copy.deepcopy(source), area)
        return self.runtime

    def agent(self, model):
        return KitAgent(self.runtime, model, RoomAdjudicator(perception=0, insight=0, roll=lambda: 15))

    def beat(self, delivered=()):
        revision, state = self.runtime.load()
        self.runtime.commit(f'beat-{revision}', revision, [{
            'type': 'story_beat', 'area': state['area'], 'delivered': list(delivered), 'evidence': 'test beat'}])


class ReviewFixes(Base):
    """Nagatha's review of #55 at 96e279f: no stall, no stale hook, degraded mode clears it."""

    def test_a_primary_hook_speech_cannot_deliver_is_refused_at_load(self):
        source = copy.deepcopy(FEASIBILITY)
        hook = {'id': 'see_cache', 'primary': True, 'by': 'sentry', 'within_beats': 1,
                'text': 'The sentry points the stranger at the cache.', 'delivered_when': {'fact_known': 'cache_door'}}
        source['facts'].setdefault('cache_door', {'area': 'entry', 'text': 'A door.', 'visible': False})
        source['story'] = {'entry': {'hooks': [hook]}}
        # Before the fix this stalled every turn: no line could ever meet fact_known.
        with self.assertRaisesRegex(InvalidChange, 'delivered by what an NPC says'):
            kit_brief.compile_story(source)
        hook['delivered_when'] = {'any': [{'fact_known': 'cache_door'},
                                          {'said': {'by': ['sentry'], 'any': ['the cache']}}]}
        kit_brief.compile_story(source)  # speech can deliver it now
        hook.update(primary=False, delivered_when={'fact_known': 'cache_door'})
        kit_brief.compile_story(source)  # a secondary hook is only tracked, never forced

    def test_the_brief_is_capped_and_fight_rounds_are_not_beats(self):
        self.start()
        source = self.runtime.source()
        state = copy.deepcopy(self.runtime.load()[1])
        for actor in state['actors'].values():
            actor['traits'] = ['x' * 290] * 6
        made = kit_brief.brief(source, state)
        self.assertLessEqual(len(json.dumps(made, ensure_ascii=False).encode()), kit_brief.BRIEF_MAX_BYTES)
        self.assertTrue(made.get('trimmed'))
        self.assertEqual(len(made['hooks']), len(source['story']['area_06c']['hooks']))
        fighting = dict(state, combat={'status': 'running'})
        self.assertIsNone(kit_brief.beat_event(self.runtime.source(), fighting, '', 'round'))


class BriefNeverLeaks(Base):
    def test_the_brief_stays_private_and_overdue_lines_are_public_safe(self):
        self.start()
        model = Entering()
        agent = self.agent(model)
        agent.opening('entry')
        for index, action in enumerate(LIVE):
            agent.turn(action, f't{index + 1}')
        for index, payload in enumerate(model.performances):
            text = json.dumps(payload).casefold()
            self.assertNotIn('story_brief', text)
            self.assertNotIn('beats_in_scene', text)
            for secret in ('doppelganger', 'stone key', 'harria', 'marked game', 'pinprick'):
                self.assertNotIn(secret, text)
            for secret in SECRETS:
                self.assertNotIn(secret, json.dumps(payload.get('raise_now') or []).casefold())
            if index < 2:  # entry and T1: the motive stays behind the Insight roll T2 makes
                self.assertNotIn('scares newcomers', text)
                self.assertNotIn('thugs', text)
        self.assertIn('story_brief', model.plans[0])
        self.assertIn('scares newcomers', json.dumps(model.plans[0]['story_brief']))

    def test_a_hook_line_that_names_a_secret_is_refused_at_load(self):
        for text in ('The doppelganger slips out of its disguise.', 'The dealer admits the deck is marked.',
                     'Someone mentions the stone key behind the carving.'):
            with self.subTest(text=text):
                source = copy.deepcopy(SOURCE)
                source['story']['area_06c']['hooks'][0]['text'] = text
                with self.assertRaisesRegex(InvalidChange, 'said to the performer'):
                    kit_brief.compile_story(source)


class AnyRoom(Base):
    """Not 6c: the same mechanism on other room data."""

    class Talk:
        def resolve(self, action, revision, state):
            return Resolution('social', 'You speak.', [{'type': 'beat', 'tags': ['social'], 'evidence': action}])

    def test_a_minimal_room_still_yields_a_sane_brief(self):
        self.start(FEASIBILITY, 'entry')
        _, body, planning = kit_agent.prepare_turn(self.runtime, self.Talk(), 'Hello?')
        brief = planning['story_brief']
        self.assertEqual(brief['area'], 'entry')
        self.assertEqual({p['actor'] for p in brief['present']}, {'sentry', 'hidden_watcher'})
        sentry = next(p for p in brief['present'] if p['actor'] == 'sentry')
        self.assertEqual(sentry['wants'], ['Protect the companion recovering in the passage.'])
        self.assertEqual((brief['hooks'], brief['raise_now'], brief['purposes']), ([], [], []))
        self.assertTrue(brief['endings'] and brief['about'])
        self.assertNotIn('story_due', body)

    def test_a_synthetic_room_with_a_story_raises_its_hook_on_time(self):
        source = copy.deepcopy(FEASIBILITY)
        source['actors']['sentry']['traits'] = ['Short-tempered when tired.']
        source['story'] = {'entry': {
            'about': 'A tired sentry guards a wounded friend and wants the stranger gone.',
            'purposes': [{'what': 'The barricade', 'for': 'Keeps strangers out of the passage.', 'roots': ['sentry']}],
            'hooks': [{'id': 'turn_back', 'primary': True, 'by': 'sentry', 'within_beats': 2,
                       'text': 'The sentry tells the stranger to turn back, and says why.',
                       'delivered_when': {'said': {'by': ['sentry'], 'any': ['turn back', 'go back']}}}],
            'endings': ['The stranger turns back.', 'The stranger talks their way past.']}}
        self.start(source, 'entry')
        self.assertEqual(kit_brief.brief(self.runtime.source(), self.runtime.load()[1])['raise_now'], [])
        self.beat()
        self.beat()
        state = self.runtime.load()[1]
        due = kit_brief.due_hooks(self.runtime.source(), state)
        self.assertEqual([d['id'] for d in due], ['turn_back'])
        label = due[0]['by']
        with self.assertRaisesRegex(InvalidChange, 'Story hook overdue'):
            kit_brief.check_raised(due, self.runtime.source(), state, f'{label}: Nice weather.')
        kit_brief.check_raised(due, self.runtime.source(), state, f'{label}: Turn back. The passage is closed.')
        event = kit_brief.beat_event(self.runtime.source(), state, f'{label}: Turn back now.', 'x')
        self.assertEqual(event['delivered'], ['turn_back'])
        brief = kit_brief.brief(self.runtime.source(), state)
        self.assertEqual(brief['present'][-1]['traits'] if brief['present'][-1]['actor'] == 'sentry' else
                         next(p for p in brief['present'] if p['actor'] == 'sentry')['traits'],
                         ['Short-tempered when tired.'])


if __name__ == '__main__':
    unittest.main()

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
from pathlib import Path

from runtime import kit_agent, kit_brief, kit_guards, kit_toll
from runtime.kit_agent import KitAgent, Resolution, Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, MIRROR, RecordingModel, exchange_speech, with_raised_hooks

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
        return KitAgent(self.runtime, model, Room6CAdjudicator(perception=0, insight=0, roll=lambda: 15))

    def beat(self, delivered=()):
        revision, state = self.runtime.load()
        self.runtime.commit(f'beat-{revision}', revision, [{
            'type': 'story_beat', 'area': state['area'], 'delivered': list(delivered), 'evidence': 'test beat'}])


class EnteringTheRoom(Base):
    def test_entering_6c_puts_the_motive_the_toll_hook_and_uktarls_traits_in_the_prompt(self):
        self.start()
        model = Entering()
        self.agent(model).opening('entry')
        brief = model.plans[0]['story_brief']
        purposes = ' '.join(p['for'] for p in brief['purposes'])
        self.assertIn('paying the 10 gp toll for safe passage', purposes)
        self.assertIn('vampire act', ' '.join(p['what'] for p in brief['purposes']).casefold())
        hooks = {h['id']: h for h in brief['hooks']}
        self.assertTrue(hooks['toll_demand']['primary'])
        self.assertFalse(hooks['toll_demand']['delivered'])
        uktarl = next(p for p in brief['present'] if p['actor'] == 'uktarl')
        self.assertIn('Lies and cheats for the fun of it (source).', uktarl['traits'])
        self.assertIn('Blames others for his own failures (source).', uktarl['traits'])
        self.assertTrue(any('scares newcomers' in want for want in uktarl['wants']))
        self.assertTrue(any('30 gp' in t['when'] for t in brief['thresholds']))
        self.assertTrue(brief['endings'])
        # Every turn in the scene, not once.
        self.agent(model).turn('I nod to the dealer.', 'next')
        self.assertEqual(model.plans[-1]['story_brief']['beats_in_scene'], 1)
        self.assertIn('toll_demand', {h['id'] for h in model.plans[-1]['story_brief']['hooks']})

    def test_plan_beats_may_cite_a_hook(self):
        self.start()
        from runtime import kit_plan
        block = {'beats': [{'id': 'toll', 'who': 'uktarl', 'toward': 'name the toll', 'when': 'soon',
                            'why': 'the act exists to collect it', 'roots': ['hook:toll_demand'],
                            'change': 'new', 'reason': 'none'}], 'dropped': []}
        kit_plan.check_plan_block(block, self.runtime.source(), self.runtime.load()[1])
        block['beats'][0]['roots'] = ['hook:no_such_hook']
        with self.assertRaises(InvalidChange):
            kit_plan.check_plan_block(block, self.runtime.source(), self.runtime.load()[1])


class LiveFailuresSurface(Base):
    """Replay of the live run: the toll and the act's purpose surface within N beats."""

    def test_a_performer_that_lets_the_toll_slide_is_rejected_by_the_hooks_beat(self):
        self.start()
        model = IgnoresHooks()
        agent = self.agent(model)
        agent.opening('entry')
        agent.turn(LIVE[0], 't1')
        agent.turn(LIVE[1], 't2')
        within = next(h['within_beats'] for h in SOURCE['story']['area_06c']['hooks'] if h['id'] == 'toll_demand')
        self.assertEqual(self.runtime.load()[1]['story']['area_06c']['beats'], within)
        with self.assertRaisesRegex(InvalidChange, 'Story hook overdue: the Dealer'):
            agent.turn(LIVE[2], 't3')

    def test_the_toll_and_the_acts_purpose_are_raised_in_character_within_n_beats(self):
        self.start()
        model = Entering()  # follows raise_now, as the instructions say
        agent = self.agent(model)
        agent.opening('entry')
        for index, action in enumerate(LIVE):
            agent.turn(action, f't{index + 1}')
        state = self.runtime.load()[1]
        self.assertLessEqual(state['story']['area_06c']['beats'], 4)
        self.assertEqual(kit_toll.here(self.runtime.source(), state)['passage_toll'][1]['status'], 'demanded')
        self.assertTrue({'toll_demand', 'act_menace', 'rigged_game'} <= set(state['story']['area_06c']['delivered']))
        raised = [p for p in model.performances if p.get('raise_now')]
        self.assertTrue(raised)
        self.assertEqual(raised[0]['raise_now'][0]['speaker'], 'Dealer')
        self.assertEqual(kit_brief.brief(self.runtime.source(), state)['raise_now'], [])


class UndeliveredHookStaysFlagged(Base):
    def test_flagged_until_delivered(self):
        self.start()
        source = self.runtime.source()
        for beat in range(6):
            brief = kit_brief.brief(source, self.runtime.load()[1])
            toll = next(h for h in brief['hooks'] if h['id'] == 'toll_demand')
            self.assertFalse(toll['delivered'])
            self.assertEqual(toll['beats_waiting'], beat)
            self.assertEqual('toll_demand' in brief['raise_now'], beat >= 3)
            self.beat()
        # The NPC names it: the toll is demanded, and the hook latches delivered.
        revision, state = self.runtime.load()
        body = dict(kit_toll.here(source, state)['passage_toll'][1], status='demanded', demanded_by='uktarl')
        self.runtime.commit('raised', revision, [kit_toll.event('passage_toll', body, 'raised in test')])
        self.beat(['toll_demand'])
        brief = kit_brief.brief(source, self.runtime.load()[1])
        self.assertTrue(next(h for h in brief['hooks'] if h['id'] == 'toll_demand')['delivered'])
        self.assertNotIn('toll_demand', brief['raise_now'])
        self.assertEqual(self.runtime.load()[1]['story']['area_06c']['delivered'], ['toll_demand'])

    def test_nobody_raises_a_hook_when_its_npc_is_gone_or_a_fight_runs(self):
        self.start()
        for _ in range(3):
            self.beat()
        state = self.runtime.load()[1]
        self.assertIn('toll_demand', kit_brief.brief(self.runtime.source(), state)['raise_now'])
        gone = copy.deepcopy(state)
        gone['actors']['uktarl']['status'] = 'fled'
        self.assertNotIn('toll_demand', kit_brief.brief(self.runtime.source(), gone)['raise_now'])
        fighting = copy.deepcopy(state)
        fighting['combat'] = {'status': 'running'}
        self.assertEqual(kit_brief.brief(self.runtime.source(), fighting)['raise_now'], [])


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

    def test_a_waived_toll_retires_the_act_hook_too(self):
        """V1/V3-style: the toll is settled by social play before its NPC names it; nobody is
        then forced to sell the deadly dark."""
        self.start()
        model = IgnoresHooks()
        agent = self.agent(model)
        agent.opening('entry')
        revision, state = self.runtime.load()
        body = dict(kit_toll.here(self.runtime.source(), state)['passage_toll'][1], status='waived')
        self.runtime.commit('waived', revision, [kit_toll.event('passage_toll', body, 'Waived through Harria.')])
        for index, action in enumerate(LIVE):
            agent.turn(action, f't{index + 1}')  # never rejected for an overdue hook
        brief = kit_brief.brief(self.runtime.source(), self.runtime.load()[1])
        delivered = {h['id'] for h in brief['hooks'] if h['delivered']}
        self.assertTrue({'toll_demand', 'act_menace'} <= delivered)
        self.assertEqual(brief['raise_now'], [] if 'rigged_game' in delivered else ['rigged_game'])
        self.assertTrue(all('raise_now' not in p or not p['raise_now'] or
                            all('passage' not in r['raises'] and 'dangerous' not in r['raises'] for r in p['raise_now'])
                            for p in model.performances))

    def test_a_degraded_performance_carrying_the_hook_commits(self):
        self.start()
        for _ in range(3):
            self.beat()
        bridge = kit_agent.KitChatBridge(self.runtime, Room6CAdjudicator(perception=0, insight=0, roll=lambda: 15))
        prepared = bridge.prepare('I nod to the dealer.', 'stuck')
        self.assertTrue(prepared['input'].get('raise_now') or
                        self.runtime.pending_kit_turn('stuck')['body'].get('story_due'))
        payload = bridge.decide('stuck', RecordingModel().plan(prepared['input']))
        self.assertIn('raise_now', kit_agent.DEGRADED_INSTRUCTION)
        plain = exchange_speech(1)
        for _ in range(kit_agent.DEGRADED_AFTER_REJECTIONS):
            with self.assertRaisesRegex(InvalidChange, 'Story hook overdue') as caught:
                bridge.finish('stuck', plain)
        self.assertIn('names the amount (10 gp)', str(caught.exception))
        due = self.runtime.pending_kit_turn('stuck')['body']['story_due']
        speech = with_raised_hooks(plain, {'raise_now': kit_agent.raise_now_view(due)})
        result = bridge.finish('stuck', speech, degraded=True)
        self.assertEqual(result['revision'], self.runtime.load()[0])
        state = self.runtime.load()[1]
        self.assertIn('toll_demand', state['story']['area_06c']['delivered'])
        self.assertEqual(kit_toll.here(self.runtime.source(), state)['passage_toll'][1]['status'], 'demanded')

    def test_natural_toll_words_and_tight_phrases(self):
        self.start()
        source = self.runtime.source()
        self.assertTrue(kit_toll.names_toll(source, 'passage_toll', 'Dealer: Ten gold and you walk out safe.'))
        hooks = {h['id']: h for h in source['story']['area_06c']['hooks']}
        state = self.runtime.load()[1]
        for line in ('Dealer: The night is young; keep your hand still and deal with it.',
                     'Dealer: It is dangerous to bet against the house, safely or not.'):
            with self.subTest(line=line):
                self.assertFalse(kit_brief.holds(hooks['act_menace']['delivered_when'], source, state, line))
                self.assertFalse(kit_brief.holds(hooks['rigged_game']['delivered_when'], source, state, line))

    def test_the_guard_and_the_detector_share_one_toll_test(self):
        # #55 review: one test for "this NPC sentence names the toll", used by the detector
        # and the call-6 guard. The stake and the toll are both 10 gp here, so loose words
        # (walk out, go on, get through) count only in a sentence with no game words.
        self.start()
        source = self.runtime.source()

        def named(line):
            return kit_toll.names_toll(source, 'passage_toll', f'Dealer: {line}')

        demand = 'Ten gold and you walk out safe.'
        self.assertTrue(named(demand))
        with self.assertRaises(InvalidChange):  # named in passing, no opening for the player
            kit_guards.check_toll_exchange([{'speaker': 'Dealer', 'text': demand}], 10, False)
        kit_guards.check_toll_exchange([{'speaker': 'Dealer', 'text': 'Down here the dark is not kind. '
                                         'Ten gold and you walk out safe. Do we have an understanding?'}], 10, False)
        # Strong words count anywhere, game talk or not.
        self.assertTrue(named('Ten gold a head to pass, cards or no cards.'))
        for line in ("Ten gold says you won't get through three hands. Brave enough?",
                     'Bring ten gold and walk out richer, maybe. Interested?',
                     'Ten gold is safe with me, friend. Shall we?',
                     'Ten gold and you walk out safe, so ante up and play.'):
            with self.subTest(line=line):
                self.assertFalse(named(line))
                kit_guards.check_toll_exchange([{'speaker': 'Dealer', 'text': line}], 10, False)
        for line in ('Ten gold a round, go on and sit.', "The house plays ten gold, and you're safe at my table.",
                     "I'll put up ten gold if you get through this hand."):
            with self.subTest(line=line):  # stake talk before the toll is raised: not the guard's business
                self.assertFalse(named(line))
                kit_guards.check_toll_exchange([{'speaker': 'Dealer', 'text': line}], 10, False)
        self.assertIs(kit_guards.npc_names_toll_words, kit_toll.npc_names_toll_words)

    def test_natural_invitations_and_the_games_own_names_count(self):
        self.start()
        source = self.runtime.source()
        hooks = {h['id']: h for h in source['story']['area_06c']['hooks']}
        state = self.runtime.load()[1]
        for line in ('Care to play?', 'Join us for a hand?', 'Twenty-one, friend. Want in?',
                     'Cards are friendlier than the corridor. Sit.', 'Play a round, stranger.',
                     'Twenty-one is all we play here.'):
            with self.subTest(line=line):
                self.assertTrue(kit_brief.holds(hooks['rigged_game']['delivered_when'], source, state,
                                                f'Dealer: {line}'))
        for line in ('Cards are old down here.', 'Sit wherever you like; the corridor is cold.',
                     'Give me a hand with this lantern.', 'I want in on the gossip.',
                     'The others will join us later.'):
            with self.subTest(line=line):  # "cards + sit" needs both words in one line
                self.assertFalse(kit_brief.holds(hooks['rigged_game']['delivered_when'], source, state,
                                                 f'Dealer: {line}'))
        for line in ('We protect you from what walks the halls.', 'This is no place for the living.'):
            with self.subTest(line=line):
                self.assertTrue(kit_brief.holds(hooks['act_menace']['delivered_when'], source, state,
                                                f'Dealer: {line}'))

    def test_a_new_scene_in_the_same_area_re_arms_the_hooks(self):
        # Story memory belongs to the open scene (scene_id; scene-1 before scene ids exist).
        self.start()
        state = copy.deepcopy(self.runtime.load()[1])
        source = self.runtime.source()
        kit_brief.apply_event(state, source, {'type': 'story_beat', 'area': 'area_06c',
                                              'delivered': ['toll_demand'], 'evidence': 'x'})
        self.assertEqual(kit_brief.story_state(state, 'area_06c')['delivered'], ['toll_demand'])
        self.assertEqual(state['story']['area_06c']['scene'], kit_brief.FIRST_SCENE)
        state['scene_id'] = 'scene-2'
        self.assertEqual(kit_brief.story_state(state, 'area_06c'), {'beats': 0, 'delivered': []})
        made = kit_brief.brief(source, state)
        self.assertFalse(next(h for h in made['hooks'] if h['id'] == 'toll_demand')['delivered'])
        kit_brief.apply_event(state, source, {'type': 'story_beat', 'area': 'area_06c', 'delivered': [],
                                              'evidence': 'x'})
        self.assertEqual(state['story']['area_06c'], {'beats': 1, 'delivered': [], 'scene': 'scene-2'})

    def test_game_names_from_a_called_list_or_the_name(self):
        # Non-6c: any card procedure names itself; a said condition with game picks them up.
        self.assertEqual(kit_brief.game_names({'name': 'Three-Dragon Ante (house rules)'}), ['three-dragon ante'])
        self.assertEqual(kit_brief.game_names({'name': 'Dragonchess', 'called': ['Dragonchess', 'the board']}),
                         ['dragonchess', 'the board'])
        self.assertTrue(kit_brief._says('the board is set; sit', 'the board + sit'))
        self.assertFalse(kit_brief._says('the board is set', 'the board + sit'))

    def test_the_brief_is_capped_and_fight_rounds_are_not_beats(self):
        self.start()
        source = self.runtime.source()
        state = copy.deepcopy(self.runtime.load()[1])
        for actor in state['actors'].values():
            actor['traits'] = ['x' * 290] * 6
        made = kit_brief.brief(source, state)
        self.assertLessEqual(len(json.dumps(made, ensure_ascii=False).encode()), kit_brief.BRIEF_MAX_BYTES)
        self.assertTrue(made.get('trimmed'))
        self.assertEqual(len(made['hooks']), 3)
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

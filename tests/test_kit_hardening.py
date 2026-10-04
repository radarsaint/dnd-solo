"""Guards for failure modes a live ChatGPT host hits (branch kit-hardening).

Each test class maps to one entry in section (g) of
docs/architecture/kit-expression-gap.md. Sample lines here are test inputs that
exercise a construction; none of them is a line the runtime ever produces.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent, kit_guards
from runtime.kit_agent import (KitAgent, KitChatBridge, PendingRuling, RoomAdjudicator,
                               fit_to_budget)
from runtime.state_context import (CONTEXT_BUDGET_BYTES, HostSequenceError, InvalidChange,
                                   PERSONALITY_CORE, Runtime, StaleTurn, encode)
from test_kit_agent import FIXTURE, NIK_GREETING, NIK_FLAT_REPLY as NIK_REPLY, RecordingModel, exchange_speech

SOURCE = json.loads(FIXTURE.read_text())
CARDS = SOURCE['public_performance']['actor_cards']
CONTRACTS = {name: card['voice_contract'] for name, card in CARDS.items()}
LEAKS = kit_guards.leak_sets(SOURCE)
EMPTY_VIEW = {'known_facts_here': []}


def seg(speaker, text, reacts_to=None):
    return {'speaker': speaker, 'text': text, **({'reacts_to': reacts_to} if reacts_to else {})}


def history(*turns):
    return [{'player_input': 'x', 'spoken': '\n'.join(f'{s}: {t}' for s, t in lines)} for lines in turns]


class BridgeCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.adjudicator = RoomAdjudicator(perception=0, insight=0, roll=lambda: 20)
        self.bridge = KitChatBridge(self.runtime, self.adjudicator)

    def quiet_plan(self, private_input, **brief):
        plan = self.model.plan(private_input)
        plan.update(move='npc_reply', table_presence='quiet')
        plan['public_brief'].update(brief)
        return plan

    def one_pass(self, action, turn_id, **brief):
        prepared = self.bridge.prepare(action, turn_id, one_pass=True)
        return prepared, self.quiet_plan(prepared['input']['private'], **brief)

    def staged(self, action, turn_id, **brief):
        prepared = self.bridge.prepare(action, turn_id)
        plan = self.quiet_plan(prepared['input'], **brief)
        self.bridge.decide(turn_id, plan)
        return plan


class PaddingTests(unittest.TestCase):
    """(g1) Padding past the floors: repetition, restating the player, recycling, filler."""

    def check(self, segments, action='What is the game here?', kind='social', past=()):
        kit_guards.check_padding(segments, action, kind, past)

    def test_ordinary_exchange_passes(self):
        self.check(exchange_speech(2, kit=False)['segments'])

    def test_repeated_run_is_padding(self):
        with self.assertRaisesRegex(InvalidChange, 'Padding: the turn repeats'):
            self.check([seg('Narrator', 'The lamp gutters over the worn felt of the table.'),
                        seg('Dealer', 'Look closer and you will see the lamp gutters over the worn felt of the table.')])

    def test_echoing_the_player_is_padding(self):
        action = 'I tell him I came down here looking for my missing brother Tam.'
        with self.assertRaisesRegex(InvalidChange, 'echoes 7\\+ of the player'):
            self.check([seg('Dealer', 'You came down here looking for your missing brother Tam? '
                                      'I came down here looking for my missing brother Tam, you say.')], action)

    def test_narration_retelling_the_bid_is_padding(self):
        with self.assertRaisesRegex(InvalidChange, 'retells what the player said'):
            self.check([seg('Narrator', 'You ask the table what game they are playing.'),
                        seg('Dealer', 'Three-card draw, house rules.')])
        # A physical turn may narrate the player's visible act; only social retelling is padding.
        self.check([seg('Narrator', 'You ask nothing; the ring glints.')], kind='inspect_feature')

    def test_recycled_line_from_an_earlier_turn_is_padding(self):
        past = history([('Dealer', 'Every chair at this table costs something before the night is out.')])
        with self.assertRaisesRegex(InvalidChange, 'recycles an earlier line'):
            self.check([seg('Dealer', 'Sit, but every chair at this table costs something before the night is out.')],
                       past=past)

    def test_naming_the_current_public_card_state_is_not_padding(self):
        # The player's hand is on the table in the public view: reading it back is the state.
        hand = 'red 7, gold 9, blue 3, green 5, white 2, black 8'
        table = json.dumps({'three_dragon_ante': {'player': {'hand': hand.split(', ')}}})
        past = history([('Narrator', f'Your hand: {hand}.')])
        line = [seg('Narrator', f'Your hand still reads {hand}.')]
        with self.assertRaisesRegex(InvalidChange, 'recycles an earlier line'):
            self.check(line, past=past)
        kit_guards.check_padding(line, 'What do I hold?', 'social', past, table)
        # Anything beyond the state is still checked.
        with self.assertRaisesRegex(InvalidChange, 'recycles an earlier line'):
            kit_guards.check_padding([seg('Dealer', 'Every chair at this table costs something before the night is out.')],
                                     'Well?', 'social',
                                     history([('Dealer', 'Every chair at this table costs something before the night is out.')]),
                                     table)

    def test_literal_leak_phrases_are_room_data_not_code(self):
        import inspect
        code = inspect.getsource(kit_agent.check_public_content).lower()
        for phrase in kit_guards.leak_phrases(SOURCE)['phrases']:
            self.assertNotIn(phrase, code)
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            kit_agent.check_public_content('The stone key is warm.', {}, '', phrases=kit_guards.leak_phrases(SOURCE))
        kit_agent.check_public_content('Harria, you say?', {}, 'Who is Harria?', phrases=kit_guards.leak_phrases(SOURCE))

    def test_stock_filler_is_padding(self):
        with self.assertRaisesRegex(InvalidChange, 'stock filler'):
            self.check([seg('Narrator', 'The tension is palpable as the cards fall.')])

    def test_padding_messages_reach_the_host_limits(self):
        limits = kit_agent.performance_limits('exchange')
        self.assertIn(str(kit_guards.PADDING_REPEAT_RUN_WORDS), limits['padding'])
        self.assertIn('stock filler', limits['padding'])


class NpcVoiceTests(unittest.TestCase):
    """(g2) NPCs sound like their own card, never like Kit, never like each other."""

    def voices(self, segments, past=()):
        kit_guards.check_npc_voices(segments, CONTRACTS, past)

    def test_table_talk_in_an_npc_mouth_is_hard_rejected(self):
        for line in ('Make a Wisdom check if you doubt me.', 'Roll for initiative, then.',
                     'The DM would not like that.', 'DC 15 says you blink first.'):
            with self.subTest(line=line), self.assertRaisesRegex(InvalidChange, 'table talk'):
                kit_guards.check_npc_meta([seg('Dealer', line)])
        kit_guards.check_npc_meta([seg('Kit', 'Roll Insight.'), seg('Dealer', 'Sit, and cut the deck.')])

    def test_kit_phrasing_and_verdicts_are_not_npc_lines(self):
        with self.assertRaisesRegex(InvalidChange, 'table-side phrasing'):
            self.voices([seg('Dealer', "Well. That's a choice, walking in here with your purse showing.")])
        with self.assertRaisesRegex(InvalidChange, 'one-word verdict'):
            self.voices([seg('Dealer', 'Reckless. Sit anyway, and show me your coin.')])

    def test_kit_dry_register_is_not_npc_humor(self):
        for line in ('Nothing untoward at this table. Mostly.',
                     'Still, I respect the ambition of that entrance.',
                     'Two more coppers, for my pride, and we are square.',
                     'I have not been this amused since the roof fell in.'):
            with self.subTest(line=line), self.assertRaisesRegex(InvalidChange, 'dry register'):
                self.voices([seg('Dealer', line)])
        # Salesman's humor that pursues something passes.
        self.voices([seg('Dealer', 'A face like that deserves better luck than it brought. Sit, and I '
                                   'will deal you some of mine for a single silver.')])

    def test_npc_cannot_borrow_kits_words_this_turn_or_recently(self):
        with self.assertRaisesRegex(InvalidChange, "borrowed Kit's words"):
            self.voices([seg('Kit', 'Brave, walking into a room of fangs with empty hands.'),
                         seg('Dealer', 'Walking into a room of fangs with empty hands, and no coin to show.')])
        past = history([('Kit', 'Nobody tips a sunken stone tub over.')])
        with self.assertRaisesRegex(InvalidChange, "borrowed Kit's words"):
            self.voices([seg('Dealer', 'Nobody tips a sunken stone tub, visitor.')], past)

    def test_two_npcs_that_sound_alike_are_rejected(self):
        with self.assertRaisesRegex(InvalidChange, 'interchangeable|share the phrase'):
            self.voices([seg('Dealer', 'The house always collects what the house is owed tonight, stranger.'),
                         seg('Fourth player', 'House always collects what house is owed.')])

    def test_voice_contract_limits_are_checked(self):
        with self.assertRaisesRegex(InvalidChange, 'voice contract rules out'):
            self.voices([seg('Dealer', 'Okay, sit down and play.')])
        with self.assertRaisesRegex(InvalidChange, 'Fresco-side player ran'):
            self.voices([seg('Fresco-side player', 'You should really go and find a different table to '
                                                    'bother tonight because this one is mine.')])
        self.voices([seg('Fresco-side player', 'Back off. My stack.')])

    def test_every_card_has_a_complete_distinct_voice_contract(self):
        contracts = kit_guards.check_voice_contracts(CARDS)
        self.assertEqual(set(contracts), set(kit_agent.actor_speakers(SOURCE).values()))
        for field in ('rhythm', 'register', 'humor'):
            self.assertEqual(len({c[field] for c in contracts.values()}), len(contracts), field)
        broken = {**CARDS, 'Dealer': {**CARDS['Dealer'], 'voice_contract': {
            key: value for key, value in CONTRACTS['Dealer'].items() if key != 'humor'}}}
        with self.assertRaisesRegex(InvalidChange, 'needs a voice_contract'):
            kit_guards.check_voice_contracts(broken)
        twin = {**CARDS, 'Fourth player': {**CARDS['Fourth player'], 'voice_contract': {
            **CONTRACTS['Fourth player'], 'rhythm': CONTRACTS['Door-side player']['rhythm']}}}
        with self.assertRaisesRegex(InvalidChange, 'share the same rhythm'):
            kit_guards.check_voice_contracts(twin)

    def test_voice_cards_are_public_safe_and_script_no_lines(self):
        text = json.dumps(CARDS, ensure_ascii=False).lower()
        kit_agent.check_public_content(text, {}, '', phrases=kit_guards.leak_phrases(SOURCE))
        for word in ('doppel', 'mimic', 'shape', 'imitat', 'copy', 'vampire', 'disguise', 'cheat',
                     'marked', 'rival', 'bandit', 'harria', 'uktarl'):
            self.assertNotIn(word, text)
        for card in CARDS.values():
            for value in json.dumps(card['voice_contract'], ensure_ascii=False).split('", "'):
                self.assertNotRegex(value, r'\\"[^"]{12,}\\"', 'no quoted lines')

    def test_performer_is_told_to_speak_from_each_card(self):
        for variant in kit_agent.PERFORMANCE_VARIANTS.values():
            self.assertIn('voice_contract', variant)
            self.assertIn('never change an NPC’s diction', variant)
        self.assertIn('npc_voices', kit_agent.performance_limits())


class DirectionNotDictionTests(BridgeCase):
    """(g3) Kit's direction reaches NPCs through tactic, pacing, and framing only."""

    def test_focus_that_sets_npc_diction_is_rejected(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'diction')
        plan = self.model.plan(prepared['input'])
        for focus in ('Let the dealer crack wry jokes about the newcomer.',
                      'Give the dealer a witty drawl while he sizes up the visitor.',
                      'Have him speak like Kit would, amused at the audacity.'):
            bad = {**plan, 'public_brief': {**plan['public_brief'], 'kit_focus': focus}}
            with self.subTest(focus=focus), self.assertRaisesRegex(InvalidChange, 'sets how an NPC talks'):
                self.bridge.decide('diction', bad)
        ok = {**plan, 'public_brief': {**plan['public_brief'],
                                       'kit_focus': 'Linger on the dealer weighing the visitor’s purse; a brief dry Kit remark on the entrance.'}}
        self.bridge.decide('diction', ok)

    def test_brief_cannot_script_an_npc_line(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'script')
        plan = self.model.plan(prepared['input'])
        plan['public_brief']['tactic'] = 'The dealer says "you look like a winner to me" and deals.'
        with self.assertRaisesRegex(InvalidChange, 'scripts a line'):
            self.bridge.decide('script', plan)


class VagueFocusTests(BridgeCase):
    """(g4) Empty directives in kit_focus are rejected."""

    def test_generic_focus_is_rejected_and_concrete_focus_passes(self):
        for focus in ('Make it engaging.', 'Keep the scene interesting and fun.',
                      'Make the dealer really interesting.', 'Show Kit’s personality and add tension.'):
            with self.subTest(focus=focus), self.assertRaisesRegex(InvalidChange, 'too generic'):
                kit_guards.check_focus_specific(focus)
        for focus in ('Deliberate restraint.', 'Rule plainly and hand the moment back to the player.',
                      'Spotlight the empty chair and the nudged coppers.'):
            kit_guards.check_focus_specific(focus)

    def test_bridge_rejects_a_vague_focus_at_decide(self):
        prepared = self.bridge.prepare('Deal me in.', 'vague')
        plan = self.model.plan(prepared['input'])
        plan['public_brief']['kit_focus'] = 'Keep it interesting.'
        with self.assertRaisesRegex(InvalidChange, 'too generic'):
            self.bridge.decide('vague', plan)


class RulingDodgeTests(BridgeCase):
    """(g5) A social turn cannot escape the exchange floors by calling itself a ruling."""

    def dodge(self, prepared, **update):
        plan = self.model.plan(prepared['input'])
        plan.update(focus_actor='none', table_presence='brief', **update)
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(scope='call', kit_focus='Rule plainly and hand the scene back.')
        return plan

    def test_social_bid_labelled_ruling_or_call_is_rejected(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'dodge')
        with self.assertRaisesRegex(InvalidChange, 'not a ruling'):
            self.bridge.decide('dodge', self.dodge(prepared, move='ruling'))
        with self.assertRaisesRegex(InvalidChange, 'Call scope on a social turn'):
            self.bridge.decide('dodge', self.dodge(prepared, move='world_description'))

    def test_real_rules_question_may_be_a_call(self):
        prepared = self.bridge.prepare('Can I roll Insight on the dealer?', 'rules')
        self.bridge.decide('rules', self.dodge(prepared, move='ruling'))
        result = self.bridge.finish('rules', {'segments': [seg('Kit', 'Wisdom (Insight), yes. Go ahead.', 'roll Insight on the dealer')]})
        self.assertEqual(result['revision'], 1)

    def test_clarification_must_ask_and_cannot_hide_an_npc_reply(self):
        prepared = self.bridge.prepare('I say: do the thing with the cards.', 'clarify')
        self.bridge.decide('clarify', self.dodge(prepared, move='ask_clarification'))
        with self.assertRaisesRegex(InvalidChange, 'must actually ask'):
            self.bridge.finish('clarify', {'segments': [seg('Kit', 'Cards it is.', 'do the thing with the cards')]})
        with self.assertRaisesRegex(InvalidChange, 'cannot carry an NPC reply'):
            self.bridge.finish('clarify', {'segments': [seg('Kit', 'Which thing?', 'do the thing'),
                                                        seg('Dealer', 'Show me, then.')]})
        self.bridge.finish('clarify', {'segments': [seg('Kit', 'Which thing: shuffle, cut, or palm one?', 'the thing with the cards')]})


class ParaphraseLeakTests(BridgeCase):
    """(g6) Paraphrased secrets are caught by DM-only keyword sets, Kit lines included."""

    def leak(self, text, action='Hello.', view=EMPTY_VIEW):
        kit_guards.check_paraphrased_leaks(text, view, action, LEAKS)

    def test_paraphrases_of_hidden_facts_are_caught(self):
        for text in ('Those cards have a funny shine on the back.',
                     'Up close the fangs look like painted wax.',
                     'For a blink his face ripples like it is borrowed.',
                     'A tiny stone key hides among the carved dwarves.'):
            with self.subTest(text=text), self.assertRaisesRegex(InvalidChange, 'paraphrases a private fact'):
                self.leak(text)
        self.leak('The dealer fans the cards with a practiced flourish.')

    def test_kit_ruling_voice_is_checked_too(self):
        prepared, plan = self.one_pass('(OOC) Can I tell if the fangs are real just by asking?', 'kit-leak')
        plan.update(table_presence='brief', move='ruling', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(scope='call', kit_focus='Rule the question exactly and briefly.')
        with self.assertRaisesRegex(InvalidChange, 'paraphrases a private fact'):
            self.bridge.complete('kit-leak', {'decision': plan, 'performance': {'segments': [
                seg('Kit', 'Ask him and you get his answer, not the truth.')]}})

    def test_player_raising_a_secret_allows_questions_and_denials_only(self):
        action = 'Those fangs are fake, aren’t they?'
        self.leak('Fake? These fangs?', action)
        self.leak('These fangs are not fake, visitor.', action)
        with self.assertRaisesRegex(InvalidChange, 'paraphrases'):
            self.leak('Fine, the fangs are painted on.', action)

    def test_revealed_fact_is_no_longer_secret(self):
        revealed = {'known_facts_here': [SOURCE['facts']['false_vampires']['text']]}
        self.leak('Up close the fangs look like painted wax.', view=revealed)

    def test_brief_paraphrase_is_rejected_before_the_performer_sees_it(self):
        prepared = self.bridge.prepare('Deal me in.', 'brief-leak')
        plan = self.model.plan(prepared['input'])
        plan['public_brief']['visible_cue'] = 'The lamplight catches a shine on the back of his cards.'
        with self.assertRaisesRegex(InvalidChange, 'paraphrases a private fact'):
            self.bridge.decide('brief-leak', plan)

    def test_leak_keywords_never_reach_either_stage(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'lk', one_pass=True)
        packed = json.dumps(prepared, ensure_ascii=False)
        self.assertNotIn('leak_keywords', packed)
        self.assertNotIn('shine on the back', packed)
        self.assertNotIn('numeric_facts', packed)


class RetryCapTests(BridgeCase):
    """(g7) Retries are capped; the host gets a degraded-but-valid path, then abandon."""

    def test_degraded_path_unlocks_after_the_cap_and_records_warnings(self):
        self.staged(NIK_GREETING, 'stuck', reply_to='Whats going on here?')
        with self.assertRaises(HostSequenceError):
            self.bridge.finish('stuck', NIK_REPLY, degraded=True)  # not unlocked yet
        for attempt in range(kit_agent.DEGRADED_AFTER_REJECTIONS):
            with self.assertRaises(kit_agent.PerformanceRejected) as caught:
                self.bridge.finish('stuck', NIK_REPLY)
        self.assertTrue(caught.exception.guidance['degraded_available'])
        self.assertIn('Degraded mode is available', str(caught.exception))
        result = self.bridge.finish('stuck', NIK_REPLY, degraded=True)
        self.assertTrue(result['degraded'])
        self.assertIn('Exchange scope', result['soft_warnings'][0])
        record = self.runtime.recent_kit_turns()[-1]
        self.assertTrue(record['degraded'])
        self.assertTrue(self.runtime.kit_timing('stuck')['degraded'])

    def test_degraded_mode_never_relaxes_hard_checks(self):
        self.staged('I take a seat.', 'hard')
        leaky = {'segments': [seg('Narrator', 'The doppelganger smiles.'), seg('Dealer', 'Sit.')]}
        for _ in range(kit_agent.DEGRADED_AFTER_REJECTIONS):
            with self.assertRaises(InvalidChange):
                self.bridge.finish('hard', leaky)
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.bridge.finish('hard', leaky, degraded=True)
        agency = {'segments': [seg('Narrator', 'You nod and agree to his terms.'), seg('Dealer', 'Good.')]}
        with self.assertRaisesRegex(InvalidChange, 'Player agency'):
            self.bridge.finish('hard', agency, degraded=True)

    def test_abandon_is_offered_and_frees_the_action_for_a_fresh_decision(self):
        self.staged(NIK_GREETING, 'doomed', reply_to='Whats going on here?')
        for _ in range(kit_agent.ABANDON_SUGGEST_AFTER):
            with self.assertRaises(kit_agent.PerformanceRejected) as caught:
                self.bridge.finish('doomed', NIK_REPLY)
        self.assertEqual(caught.exception.guidance['next_step'], 'abandon_and_prepare_again')
        self.assertEqual(self.bridge.abandon('doomed')['stage'], 'abandoned')
        with self.assertRaisesRegex(HostSequenceError, 'never prepared, or was abandoned'):
            self.bridge.finish('doomed', NIK_REPLY)
        self.staged(NIK_GREETING, 'fresh')
        self.assertEqual(self.bridge.finish('fresh', exchange_speech(1, kit=False))['revision'], 1)

    def test_api_path_makes_its_last_attempt_degraded(self):
        class AlwaysFlat(RecordingModel):
            def plan(inner, payload):
                return {**super().plan(payload), 'move': 'npc_reply', 'table_presence': 'quiet'}

            def perform(inner, payload, performance_variant='current'):
                return json.loads(json.dumps(NIK_REPLY))

        result = KitAgent(self.runtime, AlwaysFlat(), self.adjudicator).turn(NIK_GREETING, 'api-flat')
        self.assertEqual(result['timing']['model_calls'], 1 + kit_agent.API_PERFORMANCE_ATTEMPTS)
        self.assertTrue(result['timing']['degraded'])
        self.assertTrue(self.runtime.recent_kit_turns()[-1]['degraded'])

    def test_cli_rejection_carries_the_options(self):
        self.staged(NIK_GREETING, 'cli', reply_to='Whats going on here?')
        temp = Path(tempfile.mkdtemp())
        (temp / 'flat.json').write_text(json.dumps(NIK_REPLY))
        self.runtime.close()
        outputs = []
        for _ in range(kit_agent.DEGRADED_AFTER_REJECTIONS):
            err = io.StringIO()
            with patch('sys.argv', ['kit_agent', 'finish', '--db', str(self.path), '--turn-id', 'cli',
                                    '--input-file', str(temp / 'flat.json')]), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(kit_agent.main(), 2)
            outputs.append(json.loads(err.getvalue()))
        self.assertFalse(outputs[0]['degraded_available'])
        self.assertEqual(outputs[-1]['next_step'], 'retry_degraded')
        out = io.StringIO()
        with patch('sys.argv', ['kit_agent', 'finish', '--db', str(self.path), '--turn-id', 'cli',
                                '--input-file', str(temp / 'flat.json'), '--degraded']), \
                contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        self.assertTrue(json.loads(out.getvalue())['degraded'])
        self.runtime = Runtime(self.path)


class ContextBudgetTests(BridgeCase):
    """(g8) Context bloat: the core is sent once, and memory is trimmed to the budget."""

    def test_one_pass_sends_the_personality_core_and_history_once(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'once', one_pass=True)
        packed = json.dumps(prepared['input'], ensure_ascii=False)
        core = PERSONALITY_CORE.read_text(encoding='utf-8')
        self.assertEqual(packed.count(json.dumps(core, ensure_ascii=False)[1:-1][:200]), 1)
        self.assertNotIn('personality_core', prepared['input']['public'])
        self.assertNotIn('public_history', prepared['input']['public'])
        self.assertIn('shared_with_private', prepared['input']['public'])
        self.assertIn('appear once', prepared['instructions'])
        # The staged performer still gets both: it is a separate call.
        staged = self.bridge.prepare(NIK_GREETING, 'staged-core')
        payload = self.bridge.decide('staged-core', self.model.plan(staged['input']))
        self.assertIn('personality_core', payload['input'])

    def test_fit_to_budget_drops_least_relevant_then_oldest_and_says_so(self):
        episodes = [{'turn_id': f't{i}', 'spoken': 'x' * 1000, 'note': 'y' * 1500} for i in range(6)]
        packet = {'kit_state': {'episodes': [dict(e) for e in episodes]},
                  'dialogue_history': [{'spoken': 'z' * 500} for _ in range(4)],
                  'dm_context': {'recent_rhythm': [{'evidence': 'r' * 300} for _ in range(8)]}}
        order = ['t2', 't0', 't1', 't3', 't4']  # least relevant first; t5 is the latest
        kept = fit_to_budget(packet, order, budget=9000, combined_budget=10 ** 6)
        self.assertEqual(kept[-1], 't5')
        self.assertNotIn('t2', kept)
        self.assertLessEqual(len(encode(packet).encode()), 9000)
        self.assertGreater(packet['kit_state']['memory_trimmed']['episodes_dropped'], 0)
        with self.assertRaisesRegex(InvalidChange, 'Context budget exceeded'):
            fit_to_budget({'kit_state': {'episodes': []}, 'dialogue_history': [],
                           'dm_context': {'recent_rhythm': [], 'big': 'q' * 5000}}, [], budget=1000)

    def test_a_detail_turn_after_a_long_game_fits_both_budgets(self):
        class LongTalk(RecordingModel):
            def plan(inner, payload):
                plan = super().plan(payload)
                action = payload['player_action']
                plan['appraisal']['cause'] = action[:300]
                plan['improv_read']['player_bid'] = action[:300]
                plan['public_brief']['reply_to'] = action[:200]
                return plan

        agent = KitAgent(self.runtime, LongTalk(), self.adjudicator)
        for turn in range(12):
            agent.turn(f'Question {turn}: ' + ' '.join(f'word{turn}x{i}' for i in range(90)) + '?',
                       f'long-{turn}')
        for ask in ('What game is it?', 'What is the dealer drinking?', 'How much for passage?'):
            prepared = self.bridge.prepare(ask, f'detail-{len(ask)}', one_pass=True)
            private = len(encode(prepared['input']['private']).encode())
            public = len(encode(prepared['input']['public']).encode())
            self.assertIn('detail_oracle', prepared['input']['private'])
            self.assertLessEqual(private, CONTEXT_BUDGET_BYTES)
            self.assertLessEqual(private + public, kit_agent.ONE_PASS_BUDGET_BYTES)
            self.runtime.discard_pending_kit_turn(f'detail-{len(ask)}')

    def test_a_long_card_game_with_a_full_detail_ledger_fits(self):
        """QA PR #15 item 9: the measured worst case. 12 long turns, a Three-Dragon Ante
        gambit mid-play (the largest procedure state over 30 seeds), and CANON_LIMIT canon
        entries at the maximum fact and basis lengths; both a detail turn and a card turn
        (whose public half carries the changed view) fit, with nothing trimmed but memory."""
        from runtime import kit_cards, state_context

        class LongTalk(RecordingModel):
            def plan(inner, payload):
                plan = super().plan(payload)
                action = payload['player_action']
                plan['appraisal']['cause'] = action[:300]
                plan['improv_read']['player_bid'] = action[:300]
                plan['public_brief']['reply_to'] = action[:200]
                return plan

        adjudicator = RoomAdjudicator(perception=0, insight=0, roll=lambda: 20, sleight_of_hand=0)
        agent = KitAgent(self.runtime, LongTalk(), adjudicator)
        self.runtime.set_player_character('Nik', 'Harengon', 'Rogue', 3)
        for turn in range(12):
            agent.turn(f'Question {turn}: ' + ' '.join(f'word{turn}x{i}' for i in range(90)) + '?',
                       f'long-{turn}')
        config = self.runtime.source()['procedures']['three_dragon_ante']
        biggest = None
        for seed in range(30):
            table = kit_cards.CardTable('three_dragon_ante', config, {'perception': 0}, f'm{seed}')
            game = table.resolve('card_join', 'I buy in with 40 gold and deal me in.', 1,
                                 kit_cards.initial_state(config))[1]
            revision = 2
            for _ in range(4):
                if game['public']['player']['gp'] < 1:
                    break
                if game['public']['gambit']['phase'] == 'done':
                    game = table.resolve('card_join', 'Deal again.', revision, game)[1]
                    revision += 1
                game = table.resolve('card_ante', 'I ante my weakest card.', revision, game)[1]
                revision += 1
                while game['public']['gambit']['phase'] == 'play':
                    if biggest is None or len(encode(game)) > len(encode(biggest)):
                        biggest = json.loads(json.dumps(game))
                    game = table.resolve('card_play', 'I play my strongest card.', revision, game)[1]
                    revision += 1
        basis = 'b' * state_context.CANON_BASIS_MAX_CHARS
        events = [{'type': 'canon_entry', 'slot': 'area_06c/card_table/game', 'kind': 'procedure',
                   'fact': ('Three-Dragon Ante: ' + 'x' * 240)[:240], 'basis': basis, 'public': True,
                   'scope': 'location', 'procedure': 'three_dragon_ante', 'roots': ['card_table'],
                   'choice': 'd0.three_dragon_ante', 'price': None, 'evidence': 'worst case'}]
        for index in range(state_context.CANON_LIMIT - 1):
            priced = index % 3 == 0
            events.append({
                'type': 'canon_entry', 'kind': 'price' if priced else 'object',
                'slot': f'area_06c/{"price" if priced else "detail"}/item_{index:02d}_' + 'q' * 20,
                'fact': ((f'{index} gp ' if priced else '') + 'f' * 240)[:240], 'basis': basis,
                'public': True, 'scope': 'location', 'procedure': None,
                'roots': ['card_table', 'treasure_on_table'], 'choice': 'priced' if priced else 'self',
                'price': {'amount': index, 'unit': 'gp', 'source': 'srd',
                          'basis': 'SRD 5.1 food_drink_lodging: Inn stay, aristocratic (per day)'}
                if priced else None, 'evidence': 'worst case'})
        events.append({'type': 'procedure_state', 'procedure': 'three_dragon_ante', 'state': biggest,
                       'evidence': 'worst case'})
        self.runtime.commit('worst-case', self.runtime.load()[0], events)
        bridge = KitChatBridge(self.runtime, adjudicator)
        for ask in ('How much for passage through the door?', 'I play my strongest card.'):
            turn_id = f'worst-{len(ask)}'
            prepared = bridge.prepare(ask, turn_id, one_pass=True)
            private = len(encode(prepared['input']['private']).encode())
            public = len(encode(prepared['input']['public']).encode())
            self.assertLessEqual(private, CONTEXT_BUDGET_BYTES)
            self.assertLessEqual(private + public, kit_agent.ONE_PASS_BUDGET_BYTES)
            self.assertEqual(len(prepared['input']['private']['dm_context']['dm_only']['canon_here']),
                             state_context.CANON_LIMIT, 'the whole ledger is sent, never trimmed')
            self.runtime.discard_pending_kit_turn(turn_id)

    def test_long_game_stays_inside_both_budgets(self):
        class LongTalk(RecordingModel):
            def plan(inner, payload):
                plan = super().plan(payload)
                action = payload['player_action']
                plan['appraisal']['cause'] = action[:300]
                plan['improv_read']['player_bid'] = action[:300]
                plan['public_brief']['reply_to'] = action[:200]
                return plan

        agent = KitAgent(self.runtime, LongTalk(), self.adjudicator)
        for turn in range(12):
            agent.turn(f'Question {turn}: ' + ' '.join(f'word{turn}x{i}' for i in range(90)) + '?',
                       f'long-{turn}')
        prepared = self.bridge.prepare('One more question about word3x5?', 'budget', one_pass=True)
        private = len(encode(prepared['input']['private']).encode())
        public = len(encode(prepared['input']['public']).encode())
        self.assertLessEqual(private, CONTEXT_BUDGET_BYTES)
        self.assertLessEqual(private + public, kit_agent.ONE_PASS_BUDGET_BYTES)
        kit_state = prepared['input']['private']['kit_state']
        # With the 94 KB budget, 12 long turns need no trim; fit_to_budget's trim order is
        # covered by test_fit_to_budget_drops_least_relevant_then_oldest_and_says_so.
        self.assertEqual(kit_state['episodes'][-1]['turn_id'], 'long-11')
        # The model may only cite episodes it was shown.
        dropped = {f'long-{i}' for i in range(12)} - {e['turn_id'] for e in kit_state['episodes']}
        plan = self.quiet_plan(prepared['input']['private'])
        plan['memory_refs'] = [sorted(dropped)[0]]
        with self.assertRaisesRegex(InvalidChange, 'Unknown or invalid memory reference'):
            self.bridge.complete('budget', {'decision': plan, 'performance': exchange_speech(3, kit=False)})


class HostSequenceTests(BridgeCase):
    """(g9) Out-of-order calls, unknown or finished turn IDs, and stale turns explain themselves."""

    def test_unknown_turn_and_skipped_decide(self):
        with self.assertRaises(HostSequenceError) as caught:
            self.bridge.finish('never', exchange_speech())
        self.assertEqual(caught.exception.next_step, 'prepare')
        self.bridge.prepare(NIK_GREETING, 'skip')
        with self.assertRaises(HostSequenceError) as caught:
            self.bridge.finish('skip', exchange_speech())
        self.assertEqual(caught.exception.next_step, 'decide')

    def test_resubmitting_a_committed_turn_returns_it_instead_of_failing(self):
        prepared, plan = self.one_pass(NIK_GREETING, 'lost')
        output = {'decision': plan, 'performance': exchange_speech(1, kit=False)}
        first = self.bridge.complete('lost', output)
        again = self.bridge.complete('lost', output)
        self.assertTrue(again['already_committed'])
        self.assertEqual((again['revision'], again['spoken']), (first['revision'], first['spoken']))
        with self.assertRaises(HostSequenceError) as caught:
            self.bridge.complete('lost', {'decision': plan, 'performance': exchange_speech(2, kit=False)})
        self.assertEqual(caught.exception.next_step, 'prepare_new_turn')
        with self.assertRaises(HostSequenceError) as caught:
            self.bridge.prepare('Another question?', 'lost')
        self.assertEqual(caught.exception.next_step, 'prepare_new_turn')

    def test_stale_turn_tells_the_host_to_prepare_again(self):
        self.staged(NIK_GREETING, 'first')
        self.bridge.finish('first', exchange_speech(1, kit=False))
        self.bridge.prepare('What are the stakes?', 'old')
        self.bridge.feedback('Fewer menus, please.')
        with self.assertRaisesRegex(StaleTurn, 'Prepare the same player action again'):
            self.bridge.decide('old', self.model.plan(self.bridge.prepare('Deal?', 'x')['input']))

    def test_cli_reports_next_step(self):
        self.runtime.close()
        temp = Path(tempfile.mkdtemp())
        (temp / 'speech.json').write_text(json.dumps(exchange_speech()))
        err = io.StringIO()
        with patch('sys.argv', ['kit_agent', 'finish', '--db', str(self.path), '--turn-id', 'ghost',
                                '--input-file', str(temp / 'speech.json')]), contextlib.redirect_stderr(err):
            self.assertEqual(kit_agent.main(), 2)
        self.assertEqual(json.loads(err.getvalue())['next_step'], 'prepare')
        self.runtime = Runtime(self.path)


class PlayerAgencyTests(unittest.TestCase):
    """(g10) Nobody decides what the player does, agrees to, or feels."""

    def test_declared_actions_and_feelings_are_rejected(self):
        for speaker, line in (('Narrator', 'You nod and take the offered seat.'),
                              ('Narrator', 'Your heart races as he turns the card.'),
                              ('Kit', 'You feel the weight of every stare.'),
                              ('Narrator', 'He watches you hesitate at the door.'),
                              ('Dealer', 'So you agree, then. Ten gold.'),
                              ('Door-side player', 'You feel it too.')):
            with self.subTest(line=line), self.assertRaisesRegex(InvalidChange, 'Player agency'):
                kit_guards.check_player_agency([seg(speaker, line)])

    def test_questions_conditions_and_perception_pass(self):
        kit_guards.check_player_agency([
            seg('Dealer', 'Do you feel lucky? If you agree to the stakes, sit.'),
            seg('Narrator', 'You see the dealer’s card pause; the others wait for whatever you want to do.'),
            seg('Kit', 'Your call.')])


class MergeReconciliationTests(unittest.TestCase):
    """(g11) The three merged PRs' carriers and instructions all survive together."""

    def test_brief_schema_and_instructions_carry_all_three_prs(self):
        brief = kit_agent.PLAN_SCHEMA['properties']['public_brief']
        # kit-voice-spec adds mirror and npc_notice (tests/test_kit_voice.py); the three PRs' fields stay.
        self.assertLessEqual({'tactic', 'reply_to', 'scope', 'kit_focus', 'callback'}, set(brief['required']))
        # Plan update #3, PR3 (b): objective, visible_cue and player_opening are no longer asked for.
        self.assertFalse({'objective', 'visible_cue', 'player_opening'} & set(brief['required']))
        self.assertIn('player_note', kit_agent.PLAN_SCHEMA['required'])
        for variant in kit_agent.PERFORMANCE_VARIANTS.values():
            self.assertIn('answer them, do not echo them back', variant)        # PR #8
            self.assertIn('never a default line or a required beat', variant)   # PR #8
            self.assertIn('callback is not none', variant)                      # PR #10
        self.assertIn('KIT’S TABLE VOICE', kit_agent.PERFORMANCE_VARIANTS['kit_expression_v1'])  # PR #9
        one_pass = kit_agent.one_pass_instructions()
        for phrase in ('callback', 'player_note', 'KIT’S TABLE VOICE', 'generic aim'):
            self.assertIn(phrase, one_pass)


class CardPlayerIdentityTests(BridgeCase):
    """(g12) Each card player is a separate speaker with their own card."""

    def test_three_card_player_labels_replace_the_shared_one(self):
        speakers = kit_agent.speech_speakers(SOURCE)
        self.assertNotIn('Card player', speakers)
        for label in ('Door-side player', 'Fresco-side player', 'Fourth player'):
            self.assertIn(label, speakers)
            self.assertIn(label, CARDS)

    def test_source_facts_and_actors_are_unchanged(self):
        self.assertEqual(set(SOURCE['actors']), {'uktarl', 'bandit_a', 'bandit_b', 'doppelganger'})
        self.assertEqual(SOURCE['actors']['doppelganger']['secrets'],
                         ['A doppelganger disguised as one of the apparent vampires.'])
        self.assertEqual(len(SOURCE['facts']), 15)  # + vampire_tells and four Perception details (table call 8)
        self.assertIn('The gang demands 10 gp per character for safe passage. If they cannot extort or '
                      'defeat adventurers, they try to turn them against the Xanathar goblinoids.',
                      SOURCE['room_rules'])

    def test_focus_card_player_reaches_performer_by_label_only(self):
        prepared = self.bridge.prepare('I ask the player by the door what they think.', 'door')
        plan = self.quiet_plan(prepared['input'])
        plan.update(focus_actor='doppelganger')
        plan['improv_read'].update(actor_ref='doppelganger', actor_basis='motive')
        payload = self.bridge.decide('door', plan)
        self.assertEqual(payload['input']['selected_move']['focus_actor'], 'Fourth player')
        packed = json.dumps(payload['input'], ensure_ascii=False).lower()
        for private in ('doppelganger', 'bandit_a', 'bandit_b'):
            self.assertNotIn(private, packed)
        with self.assertRaisesRegex(InvalidChange, r'Fourth player\)? (never spoke|did not speak)'):
            self.bridge.finish('door', {'segments': [
                seg('Narrator', 'The dealer and the player by the fresco both look up from the table at once.'),
                seg('Door-side player', 'I, uh. Just sit. Please.'),
                seg('Dealer', 'You heard him. Sit, and we will see whether your luck is as loud as your questions.')]})


class NpcRepetitionTests(unittest.TestCase):
    """(g13) NPCs do not run on catchphrases or pet names across turns."""

    def test_pet_name_repeated_from_a_recent_turn_is_rejected(self):
        past = history([('Dealer', 'Sit down, friend.')])
        with self.assertRaisesRegex(InvalidChange, 'reused the pet name "friend"'):
            kit_guards.check_npc_repetition([seg('Dealer', 'Your deal, my friend.')], past)
        kit_guards.check_npc_repetition([seg('Dealer', 'Your deal, pilgrim.')], past)
        # Outside the window it may come back.
        old = history([('Dealer', 'Sit down, friend.')], [('Dealer', 'Well?')], [('Dealer', 'Cards.')])
        kit_guards.check_npc_repetition([seg('Dealer', 'Your deal, friend.')], old)

    def test_npc_repeating_their_own_phrase_is_rejected(self):
        past = history([('Dealer', 'Look whenever your nerve is ready.')])
        with self.assertRaisesRegex(InvalidChange, 'repeated their own phrase'):
            kit_guards.check_npc_repetition([seg('Dealer', 'Cards are down. Look whenever your nerve allows.')], past)


class KitTicTests(unittest.TestCase):
    """(g14) Kit's rulings do not settle into one sentence template or a stock acknowledgement."""

    def test_contrast_template_and_noted_cannot_repeat(self):
        past = history([('Kit', 'An accusation, not a discovery.')])
        with self.assertRaisesRegex(InvalidChange, '"X, not Y" contrast'):
            kit_guards.check_kit_tics([seg('Kit', 'A threat, not an attack.')], past)
        with self.assertRaisesRegex(InvalidChange, '"X, not Y" contrast'):
            kit_guards.check_kit_tics([seg('Kit', 'Nerve, not skill. Talk, not steel.')])
        with self.assertRaisesRegex(InvalidChange, '"noted"'):
            kit_guards.check_kit_tics([seg('Kit', 'Noted.')], history([('Kit', 'Eighteen is noted.')]))
        kit_guards.check_kit_tics([seg('Kit', 'That counts as a threat; nobody rolls initiative yet.')], past)

    def test_voice_example_no_longer_seeds_the_template(self):
        voice = kit_agent.KIT_EXPRESSION_V1
        self.assertNotIn('Strength, not Dexterity', voice)
        self.assertIn('no sentence template or stock acknowledgement', voice)
        self.assertLessEqual(len(voice), 1800)


class NumericFactTests(unittest.TestCase):
    """(g15) Fixed source numbers such as the passage price cannot drift."""

    facts = kit_guards.numeric_facts(SOURCE)

    def check(self, line, action='How much to get through?', speaker='Dealer'):
        kit_guards.check_numeric_facts([seg(speaker, line)], self.facts, action)

    def test_wrong_price_is_rejected_for_any_speaker(self):
        for line, speaker in (('Twelve gold for passage, and cheap at that.', 'Dealer'),
                              ('The door costs 12 gp a head.', 'Dealer'),
                              ('Passage is fifteen gold here.', 'Kit')):
            with self.subTest(line=line), self.assertRaisesRegex(InvalidChange, 'source fixes 10'):
                self.check(line, speaker=speaker)

    def test_right_price_player_numbers_and_unrelated_amounts_pass(self):
        self.check('Ten gold a head buys the door.')
        self.check('Eight gold for passage? You insult the door.', action='I offer 8 gold for passage.')
        self.check('I won twenty gold tonight from the last fool.')


class RefusedAttemptTests(BridgeCase):
    """(g16) A refused attempt leaves a public trace the next turn can pick up."""

    def test_refused_spell_is_recorded_and_reaches_the_next_turn(self):
        with self.assertRaisesRegex(PendingRuling, 'noted in the public history'):
            self.bridge.prepare('I cast Detect Magic.', 'spell')
        self.assertEqual(self.runtime.load()[0], 1)
        attempts = self.runtime.load()[1]['refused_attempts']
        self.assertEqual(attempts[0]['action'], 'I cast Detect Magic.')
        self.assertIn('Spell effects outside combat', attempts[0]['ruling'])
        self.assertNotIn('Combat', attempts[0]['ruling'])
        prepared = self.bridge.prepare('Fine. What are you all playing?', 'after', one_pass=True)
        self.assertEqual(prepared['input']['private']['refused_attempts'], attempts)
        self.assertEqual(prepared['input']['public']['refused_attempts'], attempts)
        staged = self.bridge.prepare('And the stakes?', 'after-staged')
        self.assertEqual(staged['input']['refused_attempts'], attempts)

    def test_host_input_problems_are_not_recorded(self):
        bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        with self.assertRaisesRegex(PendingRuling, 'Load a character sheet or state the Perception roll'):
            bridge.prepare('I inspect the fresco.', 'nomod')
        self.assertEqual(self.runtime.load()[0], 0)

    def test_cli_marks_the_attempt_recorded(self):
        self.runtime.close()
        out = io.StringIO()
        with patch('sys.argv', ['kit_agent', 'prepare', '--db', str(self.path),
                                '--action', 'I cast Light.']), contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        result = json.loads(out.getvalue())
        self.assertEqual((result['stage'], result['attempt_recorded']), ('pending_ruling', True))
        self.runtime = Runtime(self.path)


class ExitOrderTests(BridgeCase):
    """(g17) On an exit the room reacts first; the departure line comes last."""

    def test_exit_event_prints_after_the_reaction(self):
        prepared, plan = self.one_pass('I walk out through the south door.', 'exit')
        result = self.bridge.complete('exit', {'decision': plan, 'performance': exchange_speech(4, kit=False)})
        lines = result['spoken'].splitlines()
        self.assertTrue(lines[-1].startswith('Narrator: You go through the south door'))
        self.assertTrue(lines[0].startswith('Narrator: The dealer flips'))
        self.assertIn('after them on an exit', kit_agent.PUBLIC_INSTRUCTIONS)


class PacketSlimTests(BridgeCase):
    """kit-slim: the one-pass packet sends a changed player view as a delta, and the
    CLI prints compact JSON. Checks still read the full view."""

    def test_view_changes_keeps_only_what_changed(self):
        before = {'area': 'Card room', 'facts': ['a'], 'table': {'game': {'rules': ['r'], 'hand': [1, 2],
                                                                          'last': 3}}, 'gone': 1}
        after = {'area': 'Card room', 'facts': ['a', 'b'], 'table': {'game': {'rules': ['r'], 'hand': [2],
                                                                          'last': None}}, 'new': {'x': 1}}
        self.assertEqual(kit_agent.view_changes(after, before),
                         {'set': {'table.game.hand': [2], 'table.game.last': None, 'new': {'x': 1}},
                          'appended': {'facts': ['b']}, 'removed': ['gone']})
        self.assertEqual(kit_agent.view_changes(before, before), {})

    def test_a_card_turn_sends_the_view_delta_without_the_static_rules(self):
        from test_kit_06c_play import GAME_ASK, GameModel
        model = GameModel()
        adjudicator = RoomAdjudicator(perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20)
        agent = KitAgent(self.runtime, model, adjudicator)
        agent.turn(GAME_ASK, 'game')
        agent.turn('Deal me in.', 'join')
        bridge = KitChatBridge(self.runtime, adjudicator)
        prepared = bridge.prepare('I play the hand out for 10 gold.', 'play', one_pass=True)
        delta = prepared['input']['public']['player_view_after_event']
        self.assertIn('as_changes_to_private_view', delta)
        self.assertTrue(any(key.startswith('table_procedures.twenty_one.') for key in delta['set']), delta['set'])
        self.assertNotIn('rules', json.dumps(list(delta['set'])))
        self.assertNotIn('Kit\'s table version', json.dumps(delta))
        # Applying the changes to the private view gives exactly the full post-event view.
        view = json.loads(json.dumps(prepared['input']['private']['dm_context']['player_perceivable']))

        def at(path):
            *parents, leaf = path.split('.')
            node = view
            for key in parents:
                node = node[key]
            return node, leaf
        for path, value in delta.get('set', {}).items():
            node, leaf = at(path)
            node[leaf] = value
        for path, items in delta.get('appended', {}).items():
            node, leaf = at(path)
            node[leaf] = node[leaf] + items
        for path in delta.get('removed', []):
            node, leaf = at(path)
            del node[leaf]
        self.assertEqual(view, self.runtime.pending_kit_turn('play')['body']['public_view'])

    def test_cli_prints_compact_json_unless_pretty(self):
        self.runtime.close()
        outputs = []
        for extra, turn in (([], 'compact'), (['--pretty'], 'pretty')):
            out = io.StringIO()
            with patch('sys.argv', ['kit_agent', 'prepare', '--one-pass', '--full', '--db', str(self.path),
                                    '--turn-id', turn, '--action', NIK_GREETING] + extra), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(kit_agent.main(), 0)
            outputs.append(out.getvalue())
        compact, pretty = outputs
        self.assertEqual(compact.count('\n'), 1)
        self.assertEqual(json.loads(compact)['stage'], 'one_pass')
        self.assertGreater(len(pretty), len(compact) * 1.15)
        self.runtime = Runtime(self.path)


if __name__ == '__main__':
    unittest.main()

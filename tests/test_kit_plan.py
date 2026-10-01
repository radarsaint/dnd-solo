"""Kit's private running plan (runtime/kit_plan.py) and the docs/voice slot."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent, kit_plan, state_context
from runtime.state_context import InvalidChange, Runtime, encode
from test_kit_agenda import SIXC, move, room, state
from test_kit_agent import RecordingModel


def beat(bid, who='thug', toward='a shakedown at the door', when='soon', roots=('thug',), change='new', reason=''):
    return {'id': bid, 'who': who, 'toward': toward, 'when': when, 'why': 'He wants the PC\'s coin.',
            'roots': list(roots), 'change': change, 'reason': reason}


def plan(*beats, dropped=()):
    return {'beats': list(beats), 'dropped': list(dropped)}


class PlanBlockTests(unittest.TestCase):
    def setUp(self):
        actors = {'thug': {'location': 'hall', 'status': 'alive', 'stats': {}}}
        claims = {'stone': {'about': 'object:hall/stone', 'truth': 'A key is behind the loose stone.',
                            'source': 'adventure', 'fact': 'loose_stone', 'roots': ['loose_stone'],
                            'exposure': 'hidden', 'dc': 15, 'pc_check': 'investigation', 'pc_access': 'roll',
                            'holders': {'thug': 'unaware'}}}
        agenda = {'agents': {'gang': {'kind': 'faction', 'areas': '*', 'wants': 'the hall', 'roots': ['dust'],
                                      'moves': {'muster': move('Boots overhead.', ['dust'])}}}}
        self.source = room(agenda, actors, claims=claims)
        self.state = state('hall', actors)

    def check(self, block, stored=None):
        here = dict(self.state, kit_plan={'beats': stored} if stored else None)
        kit_plan.check_plan_block(block, self.source, here)

    def test_beats_cite_actors_claims_or_agenda_and_respect_knowers(self):
        self.check(plan(beat('a'), beat('b', who='gang', roots=['gang:muster']), beat('c', who='kit', roots=['stone'])))
        with self.assertRaisesRegex(InvalidChange, '1-4 roots'):
            self.check(plan(beat('a', roots=['a_ghost'])))
        with self.assertRaisesRegex(InvalidChange, 'an actor id, an agenda agent id, or kit'):
            self.check(plan(beat('a', who='nobody')))
        with self.assertRaisesRegex(InvalidChange, 'thug is unaware of stone'):
            self.check(plan(beat('a', roots=['loose_stone'])))

    def test_size_is_capped(self):
        with self.assertRaisesRegex(InvalidChange, 'at most 5'):
            self.check(plan(*[beat(f'b{i}') for i in range(6)]))
        with self.assertRaisesRegex(InvalidChange, '1-160'):
            self.check(plan(beat('a', toward='x' * 161)))

    def test_carry_over_keep_advance_revise_drop(self):
        stored = [{k: v for k, v in beat(bid).items() if k not in ('change', 'reason')} for bid in ('a', 'b')]
        with self.assertRaisesRegex(InvalidChange, 'carry b'):
            self.check(plan(beat('a', change='keep')), stored)
        with self.assertRaisesRegex(InvalidChange, 'already exists'):
            self.check(plan(beat('a'), beat('b', change='keep')), stored)
        with self.assertRaisesRegex(InvalidChange, 'advance or revise'):
            self.check(plan(beat('a', change='keep', when='now'), beat('b', change='keep')), stored)
        with self.assertRaisesRegex(InvalidChange, 'reason'):
            self.check(plan(beat('a', change='revise', toward='he folds'), beat('b', change='keep')), stored)
        self.check(plan(beat('a', change='advance', when='now'), beat('c')),
                   stored[:1])
        self.check(plan(beat('a', change='revise', toward='he folds', reason='The PC paid him off.')),
                   stored[:1])
        self.check(plan(dropped=[{'id': 'a', 'reason': 'The thug left.'}, {'id': 'b', 'reason': 'Spent.'}]), stored)


SPEECH = {'segments': [
    {'speaker': 'Narrator', 'text': 'He turns a coin between finger and thumb, then sets it down beside the deck.'},
    {'speaker': 'Dealer', 'text': 'You listen well. Most who come down here talk first and pay later, so '
     'keep your hands above the table while I deal; my friends have curious habits, and I have a '
     'living to make before the next traveler wanders through.'},
    {'speaker': 'Kit', 'text': 'The jeweler has finished. The bouncer gets a turn.',
     'reacts_to': 'keep your hands above the table'}]}
SPEECH2 = {'segments': [
    {'speaker': 'Narrator', 'text': 'The lamp hisses; somebody at the bar laughs too loudly and stops.'},
    {'speaker': 'Dealer', 'text': 'Still listening? Good. The quiet ones are the ones I like best at my table, '
     'because they think before they lose, and thinking takes time, and time down here is money that '
     'somebody else is always counting for you.'},
    {'speaker': 'Kit', 'text': 'He likes you. That is not a compliment.', 'reacts_to': 'Still listening'}]}
SPEECH3 = {'segments': [
    {'speaker': 'Narrator', 'text': 'Cards whisper across the felt, one, two, three, and stop in front of you.'},
    {'speaker': 'Dealer', 'text': 'Enough listening, friend. Every chair at this table costs something, '
     'and yours has been free for far too long, so either your silver joins mine on the felt or your '
     'feet carry you back up those stairs tonight.'},
    {'speaker': 'Kit', 'text': 'Ah. There it is.', 'reacts_to': 'Enough listening'}]}
DEALER = {'id': 'fleece', 'who': 'uktarl', 'toward': 'a rigged hand once the newcomer bets big', 'when': 'soon',
          'why': 'He wants the newcomer\'s coin.', 'roots': ['uktarl'], 'change': 'new', 'reason': ''}


class BridgePlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(copy.deepcopy(SIXC), 'area_06c')
        self.bridge = kit_agent.KitChatBridge(self.runtime)

    def turn(self, extra, speech=SPEECH):
        packet = self.bridge.prepare('I listen to the dealer.', one_pass=True)
        decision = RecordingModel().plan(packet['input']['private'])
        decision.update(extra)
        self.bridge.complete(packet['turn_id'], {'decision': decision, 'performance': speech})
        return packet

    def test_plan_persists_privately_and_carries(self):
        first = self.turn({'plan': plan(DEALER)})
        self.assertNotIn('kit_plan', first['input']['private'])
        self.turn({}, SPEECH2)  # no plan block: the stored plan carries unchanged
        packet = self.bridge.prepare('I listen to the dealer.', one_pass=True)
        self.assertEqual(packet['input']['private']['kit_plan']['beats'][0]['toward'], DEALER['toward'])
        self.assertNotIn(DEALER['toward'], encode(packet['input']['public']))
        body = self.runtime.pending_kit_turn(packet['turn_id'])['body']
        decision = RecordingModel().plan(packet['input']['private'])
        decision['plan'] = plan(dict(DEALER, change='keep'))
        self.assertNotIn(DEALER['toward'], encode(kit_agent.performance_input(self.runtime, body, decision)))
        with self.assertRaisesRegex(InvalidChange, 'already exists'):
            self.bridge.complete(packet['turn_id'], {'decision': dict(decision, plan=plan(DEALER)),
                                                     'performance': SPEECH3})
        self.bridge.complete(packet['turn_id'], {'decision': dict(decision, plan=plan(
            dropped=[{'id': 'fleece', 'reason': 'The newcomer will not bet.'}])), 'performance': SPEECH3})
        self.assertEqual(self.runtime.load()[1]['kit_plan'], {'beats': []})

    def test_instructions_carry_a_short_plan_paragraph(self):
        self.assertIn('PLAN: think ahead', kit_agent.PRIVATE_INSTRUCTIONS)
        self.assertNotIn('plan', kit_agent.API_PLAN_SCHEMA['properties'])


class VoiceSlotTests(unittest.TestCase):
    def folder(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name, text in files.items():
            (Path(temp.name) / name).write_text(text, encoding='utf-8')
        patch = mock.patch.object(state_context, 'VOICE_DIR', Path(temp.name))
        patch.start()
        self.addCleanup(patch.stop)

    def test_files_load_in_name_order_without_the_readme(self):
        self.folder({'b.md': 'Second.', 'a.md': 'First.', 'README.md': 'Not voice.', 'x.txt': 'no'})
        core = state_context.personality_core_text()
        self.assertTrue(core.startswith(state_context.PERSONALITY_CORE.read_text(encoding='utf-8')))
        self.assertLess(core.index('First.'), core.index('Second.'))
        self.assertNotIn('Not voice.', core)
        self.assertNotIn('no', core[-20:])

    def test_empty_folder_changes_nothing(self):
        self.folder({'README.md': 'Only the readme.'})
        self.assertEqual(state_context.personality_core_text(),
                         state_context.PERSONALITY_CORE.read_text(encoding='utf-8'))

    def test_over_the_cap_warns_and_skips_whole_files(self):
        self.folder({'a.md': 'A' * 100, 'b.md': 'B' * state_context.VOICE_MAX_BYTES})
        text, warning = state_context.load_voice()
        self.assertIn('A' * 100, text)
        self.assertNotIn('B', text.replace('## b', ''))
        self.assertIn('b.md', warning)

    def test_both_stages_read_the_voice_and_prepare_warns(self):
        self.folder({'voice.md': 'VOICE-MARKER line.', 'zz.md': 'Z' * state_context.VOICE_MAX_BYTES})
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(copy.deepcopy(SIXC), 'area_06c')
        bridge = kit_agent.KitChatBridge(runtime)
        packet = bridge.prepare('I listen to the dealer.', one_pass=True)
        self.assertIn('VOICE-MARKER', packet['input']['private']['personality_core'])
        self.assertIn('zz.md', packet['voice_warning'])
        body = runtime.pending_kit_turn(packet['turn_id'])['body']
        self.assertIn('VOICE-MARKER', kit_agent.public_performance_base(runtime, body)['personality_core'])

    def test_a_full_voice_slot_fits_the_worst_case_budget(self):
        size = state_context.VOICE_MAX_BYTES - 40
        self.folder({'voice.md': 'word ' * (size // 5)})
        self.assertIsNone(state_context.load_voice()[1])
        worst = unittest.defaultTestLoader.loadTestsFromName(
            'test_kit_hardening.ContextBudgetTests.test_a_long_card_game_with_a_full_detail_ledger_fits')
        self.assertTrue(unittest.TextTestRunner(stream=open(os.devnull, 'w')).run(worst).wasSuccessful())


if __name__ == '__main__':
    unittest.main()

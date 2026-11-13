"""Prep-time if-rulings and cheap next-move prep. Synthetic fixtures only."""
import tempfile
import unittest
from pathlib import Path

import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NIK = ROOT / 'tests/fixtures/characters/nik.json'
from runtime import kit_adventure, kit_links, kit_prefetch, kit_rulings, kit_skim
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime
from test_kit_agent import RecordingModel
from test_kit_scene_contract_gpt import SHEET
from runtime import kit_perform, kit_opening, kit_scene_contract


def _book():
    """Varied layouts: an opening if-sentence, a party talk ruling, a likely
    'creatures that' line, a DC sentence that must not leak, and a later area."""
    opening = (
        "1. The Ford\n\n"
        "> You step into the ford and feel the silt. Two marsh hounds wait "
        "on the far bank. A stone heron stands in the silt.\n\n"
        "If a character searches the reeds, they find a wet satchel.\n"
        "If the party talks to the miller, he warns them about the latch.\n"
        "Creatures that drink the sluice water grow still.\n"
        "If a character forces the gate, they must succeed on a DC 15 Strength check.\n"
        "If a character pries the latch, a hidden catch clicks open.\n"
        "If the characters are near the woods, review the wolf stat block in the appendix.\n"
        "• If the party is ready, see page 14.\n"
        "If a character succeeds on a Strength check. All rights reserved.\n"
        "If a character opens the chest, refer to the appendix.\n"
        "The planks run on toward the far side.\n"
    )
    later = (
        "2. The Mill\n\n"
        "The mill is quiet. A rusty wheel turns in the dark sluice.\n"
        "If the characters climb the wheel, they reach the loft unnoticed.\n"
        "A later mention of a ridge wolf does not belong to the opening.\n"
    )
    return "Chapter 1: The Green Cut\n\n" + opening + "\n\\f\n" + later


class RulingGraph(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        # The fixture uses a literal form-feed escape in the file; normalize it.
        self.source = _book().replace('\\f', '\f')
        self.report = kit_adventure.import_adventure(self.db, text=self.source)
        self.index, self.text = kit_adventure._load(self.db)
        self.start = self.index['start']

    def test_import_reports_structural_ruling_counts(self):
        counts = self.report.get('ruling_counts') or kit_rulings.counts(self.index)
        self.assertEqual(counts, self.index.get('ruling_counts') or counts)
        self.assertGreaterEqual(counts['confirmed'], 2)
        self.assertGreaterEqual(counts['likely'], 1)
        self.assertTrue(self.report.get('opening_rulings'))

    def test_search_if_is_confirmed_and_surfaces_verbatim(self):
        hit = kit_rulings.for_action(
            self.db, 'I search the reeds for a satchel.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('source_verified'))
        self.assertEqual(hit.get('confidence'), kit_links.CONFIRMED)
        self.assertIn('wet satchel', hit.get('quote'))
        self.assertTrue(kit_links.valid_quote(
            self.text[self.index['locations'][self.start]['body'][0]:
                      self.index['locations'][self.start]['body'][1]],
            hit.get('quote')))
        self.assertFalse(hit.get('has_mechanics'))

    def test_talk_ruling_attaches_to_a_person_trigger(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'miller' in (item.get('quote') or '').casefold()]
        self.assertTrue(found, 'talk ruling missing')
        self.assertEqual(found[0].get('trigger_kind'), 'npc')
        hit = kit_rulings.for_action(self.db, 'I talk to the miller about the latch.', self.start)
        self.assertIsNotNone(hit)
        self.assertIn('warns them about the latch', hit.get('quote'))

    def test_creatures_that_is_likely(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'sluice' in (item.get('quote') or '').casefold()]
        self.assertTrue(found)
        self.assertEqual(found[0].get('confidence'), kit_links.LIKELY)
        hit = kit_rulings.for_action(self.db, 'We drink the sluice water.', self.start)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get('confidence'), kit_links.LIKELY)

    def test_mechanics_ruling_is_recorded_but_flagged(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if item.get('has_mechanics')]
        self.assertTrue(found)
        hit = kit_rulings.for_action(self.db, 'I force the gate.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('has_mechanics'))
        self.assertIn('DC', hit.get('quote') or '')

    def test_a_later_section_ruling_is_not_used_at_the_opening(self):
        hit = kit_rulings.for_action(self.db, 'I climb the wheel to the loft.', self.start)
        self.assertIsNone(hit)
        mill = [key for key, loc in (self.index.get('locations') or {}).items()
                if 'mill' in str(loc.get('name') or '').casefold()]
        self.assertTrue(mill)
        later = kit_rulings.for_action(self.db, 'I climb the wheel to the loft.', mill[0])
        self.assertIsNotNone(later)
        self.assertIn('loft', later.get('quote'))

    def test_unrelated_action_does_not_invent_a_ruling(self):
        self.assertIsNone(kit_rulings.for_action(self.db, 'I wave from the bank.', self.start))


class NextMovePrep(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book().replace('\\f', '\f')
        kit_adventure.import_adventure(self.db, text=self.source)

    def test_prepare_next_is_cheap_and_covers_obvious_moves(self):
        found = kit_prefetch.prepare_next(self.db)
        self.assertTrue(found and found.get('ready'))
        self.assertGreater(found.get('area_chars') or 0, 0)
        self.assertGreaterEqual(found.get('ruling_n') or 0, 1)
        obvious = found.get('obvious') or {}
        self.assertGreaterEqual(obvious.get('look') or 0, 1)
        self.assertGreaterEqual(obvious.get('talk') or 0, 1)

    def test_landing_and_pick_do_not_stash_next_move_prep(self):
        burst = (
            'You step into the ford and feel the silt. Two marsh hounds wait '
            'on the far bank. A stone heron stands in the silt.'
        )
        first = kit_skim.accept(self.db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Ford',
        })
        # Accept / pick writes the opening; next-move prep waits until the
        # opening is already up (opening_line / Yes).
        self.assertNotIn(first.get('stage'), ('error',), first)
        data = kit_skim._read(self.db)
        self.assertFalse(data.get('next_move_prep'), data.get('next_move_prep'))
        # Direct stash also refuses until the opening has been accepted or spoken.
        kit_skim._write(self.db, {'status': 'skimmed'})
        self.assertIsNone(kit_prefetch.stash(self.db))

    def test_stash_runs_after_the_opening_is_up(self):
        kit_skim._write(self.db, {'status': 'accepted', 'burst_spoken': True,
                                  'scene_key': kit_adventure._load(self.db)[0].get('start')})
        found = kit_prefetch.stash(self.db)
        self.assertTrue(found and found.get('ready'))
        data = kit_skim._read(self.db)
        self.assertTrue((data.get('next_move_prep') or {}).get('ready'))
        # Second call does not rebuild.
        again = kit_prefetch.stash(self.db)
        self.assertEqual(again.get('area_key'), found.get('area_key'))




class PreparePacketCarriesBookRuling(unittest.TestCase):
    """When a matching book ruling exists, it is on the prepare packet.

    Reproduces the host CLI path: prepare --one-pass, including when the
    engine holds the turn as pending_ruling because the room has no procedure.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book().replace('\\f', '\f')
        kit_adventure.import_adventure(self.db, text=self.source)
        burst = (
            'You step into the ford and feel the silt. Two marsh hounds wait '
            'on the far bank. A stone heron stands in the silt.'
        )
        done = kit_skim.accept(self.db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Ford',
        })
        self.assertEqual(done.get('stage'), 'skim_accepted', done)
        start_session(str(self.db), str(NIK), room=done.get('room'))
        runtime = Runtime(str(self.db))
        self.bridge = KitChatBridge(runtime, RoomAdjudicator())
        opened = self.bridge.try_prepare('Yes.', one_pass=True)
        self.assertTrue(opened.get('committed') or opened.get('stage') == 'opening_committed', opened)

    def test_cli_prepare_puts_the_book_ruling_on_a_pending_packet(self):
        """A matching physical act that the engine cannot play still carries book_ruling."""
        action = Path(self.db).parent / 'action.txt'
        action.write_text('I pry the latch on the sluice.')
        completed = subprocess.run(
            [sys.executable, '-m', 'runtime.kit_agent', 'prepare', '--one-pass',
             '--db', str(self.db), '--action-file', str(action)],
            cwd=str(ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        packet = json.loads(completed.stdout)
        hit = packet.get('book_ruling')
        self.assertTrue(hit, {k: packet.get(k) for k in list(packet)[:20]})
        self.assertTrue(hit.get('source_verified'))
        self.assertIn('hidden catch', hit.get('quote') or '')
        self.assertFalse(hit.get('has_mechanics'))
        spoken = ' '.join(str(packet.get(k) or '') for k in ('spoken', 'player_message', 'message'))
        self.assertNotRegex(spoken, r'\bDC\s*\d+\b')

    def test_try_prepare_attaches_the_ruling_when_the_engine_holds(self):
        packet = self.bridge.try_prepare('I pry the latch on the sluice.', one_pass=True)
        hit = packet.get('book_ruling')
        self.assertTrue(hit, {k: packet.get(k) for k in list(packet)[:20]})
        self.assertTrue(hit.get('source_verified'))
        self.assertIn('hidden catch', hit.get('quote') or '')




class JunkRulingsAreDropped(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book().replace('\\f', '\f')
        kit_adventure.import_adventure(self.db, text=self.source)
        self.index, self.text = kit_adventure._load(self.db)
        self.start = self.index['start']

    def test_dm_instructions_footers_and_page_pointers_are_dropped(self):
        quotes = ' '.join(item.get('quote') or '' for item in kit_rulings.rulings_from(self.index, self.start)).casefold()
        for banned in ('review the wolf', 'see page 14', 'all rights reserved', 'refer to the appendix'):
            self.assertNotIn(banned, quotes)
        counts = kit_rulings.counts(self.index)
        self.assertGreaterEqual(counts['dropped'], 4, counts)
        self.assertEqual(counts['candidates'], counts['confirmed'] + counts['likely'] + counts['dropped'])
        # The real if-sentences are still there.
        self.assertIsNotNone(kit_rulings.for_action(self.db, 'I search the reeds for a satchel.', self.start))
        self.assertIsNotNone(kit_rulings.for_action(self.db, 'I pry the latch on the sluice.', self.start))

    def test_every_kept_ruling_has_a_trigger_kind(self):
        for item in self.index.get('rulings') or []:
            self.assertTrue(item.get('trigger_kind'), item)
            self.assertTrue((item.get('condition') or '').strip(), item)
            self.assertTrue((item.get('outcome') or '').strip(), item)

    def test_a_matching_prefetched_ruling_is_marked_served(self):
        kit_skim._write(self.db, {
            'status': 'accepted', 'burst_spoken': True,
            'scene_key': self.start,
        })
        found = kit_prefetch.stash(self.db)
        self.assertTrue(found and found.get('ready'))
        self.assertTrue(found.get('ruling_records'))
        hit = kit_rulings.for_action(self.db, 'I search the reeds for a satchel.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('prefetched'), hit)
        self.assertTrue(hit.get('trigger_kind'), hit)
        self.assertIn('wet satchel', hit.get('quote') or '')


class SourceVerifiedLookAndVoice(unittest.TestCase):
    """A visible officer, no ambush: Look describes the scene; Talk is in character."""

    intro = 'Captain Mara stands in the road and hails the caravan.'
    orders = 'Captain Mara has orders to hold the road until the wagons pass.'

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'play.sqlite'
        source = (
            '1. The North Road\n> ' + self.intro + '\n' + self.orders + '\n'
            'If a character searches the ditch, they find a bent horseshoe.\n'
            '2. The Tower\n> A bell rings on a high tower.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=source)
        scene = {
            'place': {'name': 'road', 'quote': self.intro},
            'people': [{
                'id': 'captain_mara', 'name': 'Captain Mara',
                'quote': self.intro, 'visibility': 'visible', 'kind': 'person',
                'goal': {'quote': self.orders, 'status': 'established'},
                'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        accepted = kit_skim.accept(self.db, {
            'burst': self.intro, 'source_quote': self.intro,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The North Road', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(self.db), str(SHEET))
        self.runtime = Runtime(str(self.db))
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        opening = self.bridge.prepare('Yes.')
        self.assertIn(self.intro, opening.get('spoken') or '')

    def test_look_with_nothing_to_roll_describes_what_is_visible(self):
        looked = self.bridge.prepare('I look around carefully.', one_pass=True)
        spoken = looked.get('spoken') or ''
        self.assertTrue(looked.get('committed'), looked)
        self.assertNotEqual(looked.get('stage'), 'called_roll', looked)
        self.assertIn('Captain Mara stands in the road', spoken)
        self.assertNotIn('Roll Perception', spoken)
        self.assertNotRegex(spoken, r'\bDC\s*\d+\b')
        low = spoken.casefold()
        for banned in ('this beat', 'the beat stays', 'off-stage', 'invent', 'off the page'):
            self.assertNotIn(banned, low)
        # After the opening, this look is the prepared next move.
        self.assertTrue(looked.get('served_from_prefetch'), looked)

    def test_instruction_flavored_npc_line_is_replaced_with_a_sourced_reply(self):
        line = 'I ask Captain Mara what we should do next.'
        prepared = self.bridge.prepare(line, one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara', table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara', actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to=line, scope='exchange')
        answered = self.bridge.complete(prepared['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator',
                 'text': 'Captain Mara keeps her post in the road and answers you.',
                 'reacts_to': 'none'},
                {'speaker': 'Captain Mara',
                 'text': 'I am not leaving this beat, and I am not bringing anyone else into it.',
                 'reacts_to': 'none'},
                {'speaker': 'Kit',
                 'text': 'What do you say back?',
                 'reacts_to': 'ask Captain Mara what'},
            ]},
        })
        spoken = answered.get('spoken') or ''
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        self.assertIn('Captain Mara:', spoken)
        officer = [part.split(':', 1)[1].strip()
                   for part in spoken.splitlines() if part.startswith('Captain Mara:')]
        self.assertTrue(officer, spoken)
        body = officer[0].casefold()
        self.assertNotIn('this beat', body)
        self.assertNotIn('invent', body)
        self.assertNotIn('off-stage', body)
        self.assertIn('hold the road', body)
        self.assertNotRegex(spoken, r'\bDC\s*\d+\b')

    def test_two_different_questions_get_different_replies(self):
        first = self._talk('I ask Captain Mara what we should do next.',
                           'I am not leaving this beat, and I am not bringing anyone else into it.')
        second_prep = self.bridge.prepare('I ask Captain Mara who she is waiting for.', one_pass=True)
        self.assertEqual(second_prep.get('stage'), 'one_pass', second_prep)
        plan = RecordingModel().plan(second_prep['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara', table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara', actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to='I ask Captain Mara who she is waiting for.',
                                    scope='exchange')
        # Same canned officer line the host might reuse. Narration around it is new.
        answered = self.bridge.complete(second_prep['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator',
                 'text': 'She considers the question and answers from her post.',
                 'reacts_to': 'none'},
                {'speaker': 'Captain Mara',
                 'text': 'I am not leaving this beat, and I am not bringing anyone else into it.',
                 'reacts_to': 'none'},
                {'speaker': 'Kit',
                 'text': 'What do you say back?',
                 'reacts_to': 'ask Captain Mara who'},
            ]},
        })
        spoken = answered.get('spoken') or ''
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        second = [part.split(':', 1)[1].strip()
                  for part in spoken.splitlines() if part.startswith('Captain Mara:')]
        self.assertTrue(second, spoken)
        self.assertNotEqual(kit_perform._norm(first), kit_perform._norm(second[0]), (first, second[0]))
        self.assertNotIn('this beat', second[0].casefold())

    def _talk(self, action, canned):
        prepared = self.bridge.prepare(action, one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara', table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara', actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to=action, scope='exchange')
        answered = self.bridge.complete(prepared['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator',
                 'text': 'Captain Mara keeps her post in the road and answers you.',
                 'reacts_to': 'none'},
                {'speaker': 'Captain Mara', 'text': canned, 'reacts_to': 'none'},
                {'speaker': 'Kit', 'text': 'What do you say back?',
                 'reacts_to': ' '.join(action.split()[:5])},
            ]},
        })
        spoken = answered.get('spoken') or ''
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        officer = [part.split(':', 1)[1].strip()
                   for part in spoken.splitlines() if part.startswith('Captain Mara:')]
        self.assertTrue(officer, spoken)
        return officer[0]


class PerformHelpers(unittest.TestCase):
    def test_instruction_vocab_is_detected_and_not_spoken(self):
        self.assertTrue(kit_perform.instruction_vocab(
            'I am not leaving this beat, and I am not bringing anyone else into it.'))
        self.assertFalse(kit_perform.instruction_vocab(
            'I have orders to hold the road until the wagons pass.'))

    def test_a_goal_quote_becomes_a_first_person_line(self):
        person = {
            'id': 'captain_mara', 'name': 'Captain Mara',
            'goal': 'Captain Mara has orders to hold the road until the wagons pass.',
            'knowledge_evidence': [],
        }
        line = kit_perform.npc_answer(person, 'I ask what we should do next.')
        self.assertIn('hold the road', line.casefold())
        self.assertFalse(kit_perform.instruction_vocab(line))
        self.assertTrue(line.startswith('I '))

    def test_empty_book_facts_still_hand_the_turn_back_with_a_varied_line(self):
        person = {'id': 'guard', 'name': 'Guard', 'goal': '', 'knowledge_evidence': []}
        first = kit_perform.npc_answer(person, 'I ask what is going on.')
        second = kit_perform.npc_answer(person, 'Who are you waiting for?', prior=[first])
        self.assertTrue(first and second)
        self.assertNotEqual(kit_perform._norm(first), kit_perform._norm(second))
        self.assertFalse(kit_perform.instruction_vocab(first))
        self.assertFalse(kit_perform.instruction_vocab(second))


if __name__ == '__main__':
    unittest.main()

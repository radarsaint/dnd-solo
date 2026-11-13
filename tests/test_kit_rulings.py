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
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import RecordingModel
from test_kit_scene_contract_gpt import SHEET
from runtime import kit_perform, kit_opening, kit_scene_contract


def _book():
    """Varied layouts: an opening if-sentence, a party talk ruling, a likely
    'creatures that' line, a DC sentence that must not leak, and a later area."""
    opening = (
        "1. The Clock Loft\n\n"
        "> You step into the loft and feel the draft. Two marsh lamps wait "
        "on the far rail. A brass telescope stands in the draft.\n\n"
        "If a character searches the cases, they find a dry satchel.\n"
        "If the party talks to the glazier, he warns them about the latch.\n"
        "Creatures that drink the cistern water grow still.\n"
        "If a character forces the gate, they must succeed on a DC 15 Strength check.\n"
        "If a character pries the latch, a hidden catch clicks open.\n"
        "If they need help, suggest that they search the area.\n"
        "If a character's hit points reach 0, they are unconscious.\n"
        "If a character wants to try something unexpected, try to say through the action.\n"
        "If they are ready, proceed to Chapter 3: A Quiet Loft.\nIf they start to argue over who gets what, use the lantern to calm everyone down.\n"
        "If a character reduces the telescope to 0 hit points, the cistern gate slams shut.\n"
        "If the characters are near the woods, review the wolf stat block in the appendix.\n"
        "• If the party is ready, see page 14.\n"
        "If a character succeeds on a Strength check. All rights reserved.\n"
        "If a character opens the chest, refer to the appendix.\n"
        "The planks run on toward the far side.\n"
    )
    later = (
        "2. The Workshop\n\n"
        "The workshop is quiet. A rusty wheel turns in the dark cistern.\n"
        "If the characters climb the wheel, they reach the loft unnoticed.\n"
        "A later mention of a ridge wolf does not belong to the opening.\n"
    )
    return "Chapter 1: The Copper Span\n\n" + opening + "\n\\f\n" + later


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
            self.db, 'I search the cases for a satchel.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('source_verified'))
        self.assertEqual(hit.get('confidence'), kit_links.CONFIRMED)
        self.assertIn('dry satchel', hit.get('quote'))
        self.assertTrue(kit_links.valid_quote(
            self.text[self.index['locations'][self.start]['body'][0]:
                      self.index['locations'][self.start]['body'][1]],
            hit.get('quote')))
        self.assertFalse(hit.get('has_mechanics'))

    def test_talk_ruling_attaches_to_a_person_trigger(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'glazier' in (item.get('quote') or '').casefold()]
        self.assertTrue(found, 'talk ruling missing')
        self.assertEqual(found[0].get('trigger_kind'), 'npc')
        hit = kit_rulings.for_action(self.db, 'I talk to the glazier about the latch.', self.start)
        self.assertIsNotNone(hit)
        self.assertIn('warns them about the latch', hit.get('quote'))

    def test_creatures_that_is_likely(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'cistern' in (item.get('quote') or '').casefold()]
        self.assertTrue(found)
        self.assertEqual(found[0].get('confidence'), kit_links.LIKELY)
        hit = kit_rulings.for_action(self.db, 'We drink the cistern water.', self.start)
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
                if 'workshop' in str(loc.get('name') or '').casefold()]
        self.assertTrue(mill)
        later = kit_rulings.for_action(self.db, 'I climb the wheel to the loft.', mill[0])
        self.assertIsNotNone(later)
        self.assertIn('loft', later.get('quote'))

    def test_unrelated_action_does_not_invent_a_ruling(self):
        self.assertIsNone(kit_rulings.for_action(self.db, 'I wave from the rail.', self.start))


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
            'You step into the loft and feel the draft. Two marsh lamps wait '
            'on the far rail. A brass telescope stands in the draft.'
        )
        first = kit_skim.accept(self.db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Clock Loft',
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
            'You step into the loft and feel the draft. Two marsh lamps wait '
            'on the far rail. A brass telescope stands in the draft.'
        )
        done = kit_skim.accept(self.db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Clock Loft',
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
        action.write_text('I pry the latch on the cistern.')
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
        packet = self.bridge.try_prepare('I pry the latch on the cistern.', one_pass=True)
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
        for banned in (
                'review the wolf', 'see page 14', 'all rights reserved',
                'refer to the appendix', 'suggest that they search',
                'they are unconscious', 'try something unexpected',
                'proceed to chapter', 'use the lantern to calm'):
            self.assertNotIn(banned, quotes)
        counts = kit_rulings.counts(self.index)
        self.assertGreaterEqual(counts['dropped'], 9, counts)
        # A local 0-HP world outcome is kept.
        hit = kit_rulings.for_action(self.db, 'I reduce the telescope to 0 hit points.', self.start)
        self.assertIsNotNone(hit)
        self.assertIn('cistern gate slams shut', hit.get('quote') or '')
        self.assertEqual(counts['candidates'], counts['confirmed'] + counts['likely'] + counts['dropped'])
        # The real if-sentences are still there.
        self.assertIsNotNone(kit_rulings.for_action(self.db, 'I search the cases for a satchel.', self.start))
        self.assertIsNotNone(kit_rulings.for_action(self.db, 'I pry the latch on the cistern.', self.start))

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
        hit = kit_rulings.for_action(self.db, 'I search the cases for a satchel.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('prefetched'), hit)
        self.assertTrue(hit.get('trigger_kind'), hit)
        self.assertIn('dry satchel', hit.get('quote') or '')



class SourceVerifiedLookAndVoice(unittest.TestCase):
    """Look and Talk hand the host facts; the host writes the line."""

    intro = 'Warden Quill stands in the loft by the brass rail and taps the case.'
    orders = 'Warden Quill has orders to keep the loft shut until the storm passes.'

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'play.sqlite'
        source = (
            '1. The Clock Loft\n> ' + self.intro + '\n' + self.orders + '\n'
            'If a character searches the cabinet, they find a bent eyepiece.\n'
            '2. The Annex\n> A chime rings in a side annex.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=source)
        scene = {
            'place': {'name': 'loft', 'quote': self.intro},
            'people': [{
                'id': 'warden_quill', 'name': 'Warden Quill',
                'quote': self.intro, 'visibility': 'visible', 'kind': 'person',
                'goal': {'quote': self.orders, 'status': 'established'},
                'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        accepted = kit_skim.accept(self.db, {
            'burst': self.intro, 'source_quote': self.intro,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Clock Loft', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(self.db), str(SHEET))
        self.runtime = Runtime(str(self.db))
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        opening = self.bridge.prepare('Yes.')
        self.assertIn(self.intro, opening.get('spoken') or '')

    def test_look_with_nothing_to_roll_hands_facts_and_the_host_describes(self):
        prepared = self.bridge.prepare('I look around carefully.', one_pass=True)
        self.assertNotEqual(prepared.get('stage'), 'called_roll', prepared)
        self.assertFalse(prepared.get('committed'), prepared)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        facts = prepared.get('host_facts') or {}
        self.assertEqual(facts.get('kind'), 'look', facts)
        visible = ' '.join(facts.get('visible') or [])
        self.assertIn('stands in the loft', visible)
        self.assertTrue(any(person.get('name') == 'Warden Quill' for person in facts.get('people') or []), facts)
        quill = [person for person in facts['people'] if person.get('name') == 'Warden Quill'][0]
        self.assertIn('keep the loft shut', (quill.get('goal') or '').casefold())
        self.assertIn('stands in the loft', (quill.get('visible_state') or '').casefold())
        self.assertNotIn('stands in the loft', (quill.get('goal') or '').casefold())
        self.assertNotIn('taps the case', (quill.get('goal') or '').casefold())
        # Python must not have spoken a chopped description already.
        self.assertFalse((prepared.get('spoken') or '').strip())
        looked = self._complete_look(
            prepared,
            'Warden Quill is in the loft, tapping the case as you take in the stretch ahead.',
        )
        spoken = looked.get('spoken') or ''
        self.assertNotEqual(looked.get('stage'), 'rejected', looked)
        self.assertNotIn(looked.get('stage'), ('rejected', 'one_pass'), looked)
        self.assertIn('tapping the case', (looked.get('spoken') or '').casefold())
        self.assertIn('tapping the case', spoken.casefold())
        self.assertNotIn('Roll Perception', spoken)
        self.assertNotRegex(spoken, r'\bDC\s*\d+\b')
        low = spoken.casefold()
        for banned in ('this beat', 'the beat stays', 'off-stage', 'invent', 'off the page'):
            self.assertNotIn(banned, low)

    def test_a_look_that_invents_an_unattested_name_is_rejected(self):
        prepared = self.bridge.prepare('I look around carefully.', one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        with self.assertRaises(InvalidChange) as raised:
            self._complete_look(
                prepared,
                'The wizard Thalric stands over a gilded basilisk in the ditch.',
            )
        self.assertIn('unattested', str(raised.exception).casefold())

    def test_instruction_flavored_npc_line_is_rejected_not_rewritten(self):
        prepared = self.bridge.prepare('I ask Warden Quill what we should do next.', one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        facts = prepared.get('host_facts') or {}
        self.assertEqual(facts.get('kind'), 'npc_reply', facts)
        people = facts.get('people') or []
        self.assertTrue(any('keep the loft shut' in (person.get('goal') or '').casefold() for person in people), facts)
        with self.assertRaises(InvalidChange) as raised:
            self._talk_complete(
                prepared,
                'I am not leaving this beat, and I am not bringing anyone else into it.',
            )
        message = str(raised.exception).casefold()
        self.assertTrue('instruction' in message or 'beat' in message, raised.exception)

    def test_the_host_writes_an_in_character_reply_from_the_facts(self):
        line = self._talk(
            'I ask Warden Quill what we should do next.',
            'Keep the loft shut with me until the storm has passed. That is my charge.',
        )
        self.assertIn('keep the loft shut', line.casefold())
        self.assertIn('storm', line.casefold())
        self.assertFalse(kit_perform.instruction_vocab(line))
        self.assertNotRegex(line, r'\bDC\s*\d+\b')

    def test_two_different_questions_keep_the_hosts_different_replies(self):
        first = self._talk(
            'I ask Warden Quill what we should do next.',
            'Keep the loft shut with me until the storm has passed. That is my charge.',
        )
        second = self._talk(
            'I ask Warden Quill who she is waiting for.',
            'I am waiting on the storm. It has not broken yet.',
        )
        self.assertNotEqual(kit_perform._norm(first), kit_perform._norm(second), (first, second))
        self.assertIn('storm', second.casefold())

    def test_a_section_backed_lookup_does_not_stall(self):
        prepared = self.bridge.prepare('Kit, what can you tell me about this loft?', one_pass=True)
        spoken = (prepared.get('spoken') or '').casefold()
        self.assertNotIn('checking the page', spoken)
        self.assertNotIn('give me a second', spoken)
        facts = prepared.get('host_facts') or {}
        # Either the host will complete from facts, or a hop already answered.
        if prepared.get('committed') and prepared.get('stage') == 'lookup':
            self.assertNotIn('checking the page', spoken)
            return
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        self.assertEqual(facts.get('kind'), 'lookup', facts)
        corpus = ' '.join((facts.get('section') or []) + (facts.get('visible') or [])).casefold()
        self.assertTrue('loft' in corpus or 'quill' in corpus or 'rail' in corpus, facts)
        answered = self._complete_kit(
            prepared,
            'This is the clock loft, where Warden Quill stands to tap the case.',
        )
        out = (answered.get('spoken') or '').casefold()
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        self.assertNotIn(answered.get('stage'), ('rejected', 'one_pass'), answered)
        self.assertIn('warden quill', out)
        self.assertNotIn('checking the page', out)

    def _complete_look(self, prepared, description):
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='world_description', focus_actor='none', table_presence='brief')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='I look around carefully.', scope='feature')
        return self.bridge.complete(prepared['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator', 'text': description, 'reacts_to': 'none'},
                {'speaker': 'Kit', 'text': 'What do you do?', 'reacts_to': 'look around carefully'},
            ]},
        })

    def _complete_kit(self, prepared, line):
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='ruling', focus_actor='none', table_presence='present', turn_mode='meta')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='what can you tell me about this loft', scope='call')
        return self.bridge.complete(prepared['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Kit',
                 'text': line,
                 'reacts_to': 'what can you tell me'},
            ]},
        })

    def _talk_complete(self, prepared, canned, action=None):
        action = action or 'I ask Warden Quill what we should do next.'
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='npc_reply', focus_actor='warden_quill', table_presence='brief')
        plan['improv_read'].update(actor_ref='warden_quill', actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to=action, scope='exchange')
        return self.bridge.complete(prepared['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator',
                 'text': (
                     'She stays in the loft and gives you a straight answer.'
                     if 'should do next' in action
                     else 'She glances down the expected line of clouds, then speaks.'
                 ),
                 'reacts_to': 'none'},
                {'speaker': 'Warden Quill', 'text': canned, 'reacts_to': 'none'},
                {'speaker': 'Kit', 'text': 'What do you say back?',
                 'reacts_to': ' '.join(action.split()[:5])},
            ]},
        })

    def _talk(self, action, line):
        prepared = self.bridge.prepare(action, one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        answered = self._talk_complete(prepared, line, action=action)
        spoken = answered.get('spoken') or ''
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        officer = [part.split(':', 1)[1].strip()
                   for part in spoken.splitlines() if part.startswith('Warden Quill:')]
        self.assertTrue(officer, spoken)
        self.assertEqual(kit_perform._norm(officer[0]), kit_perform._norm(line))
        return officer[0]


class PerformHelpers(unittest.TestCase):
    def test_instruction_vocab_is_detected(self):
        self.assertTrue(kit_perform.instruction_vocab(
            'I am not leaving this beat, and I am not bringing anyone else into it.'))
        self.assertFalse(kit_perform.instruction_vocab(
            'I have orders to keep the loft shut until the storm passes.'))

    def test_host_facts_list_the_goal_and_visible_state(self):
        person = {
            'id': 'warden_quill', 'name': 'Warden Quill',
            'quote': 'Warden Quill stands in the loft by the brass rail and taps the case.',
            'goal': {'quote': 'Warden Quill has orders to keep the loft shut until the storm passes.',
                     'status': 'established'},
            'knowledge': [],
            'addressable': True,
        }
        facts = kit_perform._person_facts(person, index=None)
        self.assertIn('keep the loft shut', facts['goal'].casefold())
        self.assertIn('stands in the loft', facts['visible_state'].casefold())
        self.assertIn('stands in the loft', facts['action'].casefold())
        self.assertNotIn('stands in the loft', facts['goal'].casefold())
        self.assertEqual(facts['name'], 'Warden Quill')

    def test_an_unattested_name_is_a_problem_and_a_paraphrase_is_not(self):
        facts = {
            'kind': 'npc_reply',
            'visible': ['Warden Quill stands in the loft by the brass rail and taps the case.'],
            'people': [{
                'id': 'warden_quill', 'name': 'Warden Quill',
                'goal': 'Warden Quill has orders to keep the loft shut until the storm passes.',
                'knowledge': [], 'visible_state': 'Warden Quill stands in the loft by the brass rail and taps the case.',
                'addressable': True, 'link_notes': [],
            }],
            'link_notes': [],
        }
        beat = {'source_verified': True, 'people': [{'id': 'warden_quill', 'name': 'Warden Quill',
                                                     'addressable': True}]}
        good = {'segments': [
            {'speaker': 'Warden Quill',
             'text': 'Keep the loft shut with me until the storm has passed.',
             'reacts_to': 'none'},
        ]}
        self.assertEqual(kit_perform.performance_problems(good, facts, beat=beat, action='I ask.'), [])
        bad = {'segments': [
            {'speaker': 'Warden Quill',
             'text': 'The wizard Thalric told me fifty wolves wait in the hills.',
             'reacts_to': 'none'},
        ]}
        problems = kit_perform.performance_problems(bad, facts, beat=beat, action='I ask.')
        self.assertTrue(any('unattested' in item for item in problems), problems)


    def test_a_stage_direction_is_not_filed_as_a_goal(self):
        person = {
            'id': 'warden_quill', 'name': 'Warden Quill',
            'quote': 'Warden Quill glances at the brass rail and nods.',
            'goal': {'quote': 'Warden Quill glances at the brass rail and nods.',
                     'status': 'established'},
            'knowledge': [],
            'addressable': True,
        }
        facts = kit_perform._person_facts(person, index=None)
        self.assertEqual(facts['goal'], '')
        self.assertIn('glances', facts['visible_state'].casefold())
        self.assertIn('glances', facts['action'].casefold())
        self.assertFalse(kit_perform.is_attested_goal('Warden Quill glances at the brass rail and nods.'))
        self.assertTrue(kit_perform.is_visible_action('Warden Quill glances at the brass rail and nods.'))

    def test_section_facts_drop_howto_and_keep_background(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'loft.sqlite'
        source = (
            "Chapter 1: The Copper Span\n\n"
            "1. The Clock Loft\n\n"
            "> You step into the loft and feel the draft. Warden Quill stands "
            "in the loft by the brass rail and taps the case.\n\n"
            "You are from the town of Lampwick, a small harbor below the glassworks.\n"
            "Today, it's your turn to check the loft.\n"
            "DM Tip: For instance, can you hit a monster if you roll well?\n"
            "If you do, some of the fun of playing is spoiled for you.\n"
            "This reflects the character's ability scores.\n"
            "Your character can use skills by rolling.\n"
        )
        kit_adventure.ingest_adventure(db, text=source)
        quotes = kit_perform._section_player_quotes(db)
        joined = ' '.join(quotes).casefold()
        self.assertTrue(quotes, quotes)
        self.assertIn('lampwick', joined)
        self.assertIn('from the town', joined)
        self.assertIn('step into the loft', joined)
        for banned in (
                'dm tip', 'for instance', 'fun of playing', 'can you hit',
                'ability scores', 'your character can'):
            self.assertNotIn(banned, joined)
        self.assertTrue(kit_perform.is_character_background(
            'You are from the town of Lampwick, a small harbor below the glassworks.'))
        self.assertTrue(kit_perform.is_howto_or_tip(
            'DM Tip: For instance, can you hit a monster if you roll well?'))




if __name__ == '__main__':
    unittest.main()

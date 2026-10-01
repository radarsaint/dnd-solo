"""Claims and knowers (runtime/kit_claims.py, runtime/pc_sheet.py) in area 6c.

Nik's sheet is one example; a second, low-Wisdom sheet built inline shows the bands
come from whatever sheet is loaded, not from any one character."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_claims, kit_guards, pc_sheet
from runtime.kit_agent import PendingRuling, Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel

NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())
SOURCE = json.loads(FIXTURE.read_text())


def dull_fighter():
    """Not a fixture: a Wis 8, Int 8 fighter, to show nothing is keyed to Nik."""
    return {'schema': 'character_sheet_v1', 'name': 'Brakka', 'ancestry': 'Half-Orc',
            'class': 'Fighter', 'level': 3, 'proficiency_bonus': 2,
            'abilities': {'str': 17, 'dex': 12, 'con': 16, 'int': 8, 'wis': 8, 'cha': 10},
            'skills': {'athletics': 5, 'intimidation': 2}}


def state_for(sheet, known=()):
    state = {'area': 'area_06c', 'actors': copy.deepcopy(SOURCE['actors']), 'known_facts': list(known),
             'player_sheet': sheet}
    return state


def claim(claim_id, speaker, stance, version, why='none given here', about='x/y', truth='t', roots=(),
          holder='none'):
    return {'claim': claim_id, 'about': about, 'truth': truth, 'roots': list(roots), 'holder': holder,
            'speaker': speaker, 'stance': stance, 'version': version, 'why': why}


class SheetTests(unittest.TestCase):
    def test_nik_sheet_loads_and_passives_derive_from_it(self):
        pc_sheet.check_sheet(NIK)
        # The Sentinel Shield gives advantage only while held; owning it is not holding it.
        self.assertEqual([pc_sheet.passive(NIK, s) for s in ('perception', 'insight', 'investigation')],
                         [14, 14, 17])
        self.assertEqual(pc_sheet.passive({**NIK, 'held': ['Sentinel Shield']}, 'perception'), 19)
        self.assertEqual(pc_sheet.skill_bonus(NIK, 'history'), 7)

    def test_any_sheet_works_and_missing_skills_fall_back_to_the_ability(self):
        sheet = pc_sheet.check_sheet(dull_fighter())
        self.assertEqual(pc_sheet.passive(sheet, 'insight'), 9)
        self.assertEqual(pc_sheet.skill_bonus(sheet, 'history'), -1)

    def test_a_printed_passive_that_does_not_add_up_is_rejected(self):
        with self.assertRaisesRegex(InvalidChange, 'does not match'):
            pc_sheet.check_sheet({**NIK, 'passives': {'insight': 16}})


class BandTests(unittest.TestCase):
    def packet(self, sheet, known=()):
        return kit_claims.claims_here(SOURCE, state_for(sheet, known), sheet)['claims']

    def test_nik_earns_the_fingerprints_his_passives_reach(self):
        claims = self.packet(NIK)
        vamp, deck, ring = claims['false_vampires'], claims['marked_deck'], claims['ring_value']
        # Passive Insight 14 meets the adventure's DC 14: fingerprint, and Kit may point.
        self.assertEqual((vamp['dc'], vamp['pc_band'], vamp['wink']), (14, 'fingerprint', 'point'))
        self.assertIn('fingerprint', vamp)
        # No adventure DC, but the dealer hides it with Sleight of Hand +3: flat 10 + 3 = 13.
        # Shield not held: passive Perception 14 meets it, so the fingerprint. The wink is keyed
        # to passive Insight (14, one over 13): Kit may point.
        self.assertEqual((deck['dc'], deck['pc_band'], deck['wink']), (13, 'fingerprint', 'point'))
        # Knowledge is never passive: the ring waits for a player's History roll.
        self.assertEqual((ring['pc_band'], ring['wink']), ('blind', 'none'))
        self.assertIn('only when the player asks', ring['player_roll'])

    def test_a_low_wisdom_character_gets_no_fingerprint_and_no_wink(self):
        claims = self.packet(dull_fighter())
        self.assertEqual((claims['false_vampires']['pc_band'], claims['false_vampires']['wink']), ('blind', 'none'))
        self.assertEqual(claims['marked_deck']['pc_band'], 'blind')

    def test_missing_dc_uses_dungeon_floor_level(self):
        # Any check the source gives no DC, concealment or not (here the ring's appraisal).
        ring = SOURCE['claims']['ring_value']
        self.assertNotIn('dc', ring)
        self.assertEqual(kit_claims.claim_dc(ring, SOURCE['actors'], floor_level=1), 10)
        self.assertEqual(kit_claims.claim_dc(ring, SOURCE['actors'], floor_level=4), 11)
        # An NPC actively hiding it brings a flat 10 + skill instead, whatever the floor.
        deck = SOURCE['claims']['marked_deck']
        self.assertEqual(kit_claims.claim_dc(deck, SOURCE['actors'], floor_level=4), 13)

    def test_npc_bands_come_from_stats_role_and_special_senses(self):
        ring = self.packet(NIK)['ring_value']['npc_bands']
        self.assertEqual(ring['uktarl'], 'knows')          # he counted the take
        self.assertEqual(ring['doppelganger'], 'knows')    # Read Thoughts
        self.assertEqual(ring['bandit_b'], 'knows')        # Int 10 meets the default DC 10 on floor 1
        deck = self.packet(NIK)['marked_deck']['npc_bands']
        self.assertEqual(deck['bandit_a'], 'close')        # passive Insight 10, three short of 13

    def test_a_revealed_fact_is_learned(self):
        self.assertEqual(self.packet(NIK, known=['false_vampires'])['false_vampires']['pc_band'], 'learned')

    def test_an_npc_lie_is_flat_deception_against_passive_insight(self):
        uktarl = kit_claims.npc_profile(SOURCE['actors']['uktarl'])
        self.assertEqual(kit_claims.lie_lands(uktarl, NIK), {'deception': 14, 'passive_insight': 14, 'lands': True})
        self.assertTrue(kit_claims.lie_lands(uktarl, dull_fighter())['lands'])


class DecisionTests(unittest.TestCase):
    def check(self, items, sheet=NIK):
        state = state_for(sheet)
        kit_claims.check_claims(items, kit_claims.claims_here(SOURCE, state, sheet), SOURCE, state)

    def test_uktarls_lie_needs_a_why_from_his_wants(self):
        self.check([claim('ring_value', 'uktarl', 'lie', 'Forty. Dwarf-blessed.',
                          why='bait to profit from newcomers: the ring rides the first gambit')])
        with self.assertRaisesRegex(InvalidChange, 'want'):
            self.check([claim('ring_value', 'uktarl', 'lie', 'Forty.', why='because it is funny')])

    def test_the_narrator_is_held_to_the_pc_band(self):
        with self.assertRaisesRegex(InvalidChange, 'narrator knows only'):
            self.check([claim('ring_value', 'narrator', 'truth', 'Twenty-five gold.')])
        self.check([claim('false_vampires', 'narrator', 'fingerprint', 'He wipes his chin a beat too fast.')])
        with self.assertRaisesRegex(InvalidChange, 'narrator knows only'):
            self.check([claim('false_vampires', 'narrator', 'fingerprint', 'He wipes his chin.')],
                       sheet=dull_fighter())

    def test_kit_winks_only_as_far_as_the_tier(self):
        self.check([claim('false_vampires', 'kit', 'wink', 'Watch his chin when he drinks.')])
        with self.assertRaisesRegex(InvalidChange, 'wink tier'):
            self.check([claim('false_vampires', 'kit', 'wink', 'Watch his chin when he drinks.')], sheet=dull_fighter())

    def test_bands_limit_what_a_speaker_can_do(self):
        # A source that did give a hard appraisal DC (15): an Int 10 bandit is anchored.
        source = copy.deepcopy(SOURCE)
        source['claims']['ring_value']['dc'] = 15
        state = state_for(NIK)
        packet = kit_claims.claims_here(source, state, NIK)
        kit_claims.check_claims([claim('ring_value', 'bandit_b', 'truth', 'Silver. Melt it, five gold.')],
                                packet, source, state)
        with self.assertRaisesRegex(InvalidChange, 'anchored'):
            kit_claims.check_claims([claim('ring_value', 'bandit_b', 'lie', 'Twenty-five.', why='share in the take')],
                                    packet, source, state)

    def test_a_new_kit_claim_needs_roots_and_a_holder(self):
        self.check([claim('new', 'uktarl', 'boast', 'The house red. A very good year for somebody.',
                          why='control the encounter: the drink sells the act to newcomers',
                          about='actor:uktarl/drink', truth='cherry cordial', roots=['card_table'],
                          holder='uktarl')])
        with self.assertRaisesRegex(InvalidChange, 'no source is nonsense'):
            self.check([claim('new', 'uktarl', 'truth', 'Ale.', about='actor:uktarl/drink', truth='ale',
                              holder='uktarl')])


class PlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')

    def test_the_sheet_loads_and_a_history_roll_learns_the_ring(self):
        self.runtime.set_player_sheet(NIK)
        revision, state = self.runtime.load()
        self.assertEqual(self.runtime.player_view()['your_character']['ancestry'], 'Harengon')
        adjudicator = Room6CAdjudicator(source=SOURCE)
        result = adjudicator.resolve('I want to appraise the silver ring. I rolled 11 + 7 = 18',
                                     revision, state)
        self.assertEqual(result.kind, 'knowledge')
        self.assertIn('Twenty-five gold', result.public_event)
        self.runtime.commit('t1', revision, result.events)
        state = self.runtime.load()[1]
        self.assertEqual(kit_claims.claims_here(SOURCE, state, NIK)['claims']['ring_value']['pc_band'], 'learned')

    def test_a_missed_history_roll_learns_nothing(self):
        self.runtime.set_player_sheet(NIK)
        revision, state = self.runtime.load()
        result = Room6CAdjudicator(source=SOURCE).resolve('What do I know about the ring? I rolled 2 + 7 = 9',
                                                          revision, state)
        self.assertNotIn('claim_learned', [event['type'] for event in result.events])

    def test_a_planned_lie_may_name_its_number_and_an_unplanned_one_may_not(self):
        guards = {'numeric_facts': kit_guards.numeric_facts(SOURCE), 'speakers': kit_agent.actor_speakers(SOURCE)}
        line = [{'speaker': 'Dealer', 'text': 'That ring? Forty gold. The priests in the Ward pay double.'}]
        with self.assertRaisesRegex(InvalidChange, 'ring value'):
            kit_agent.check_claimed_numbers(line, {}, guards, 'What is the ring worth?')
        plan = {'claims': [claim('ring_value', 'uktarl', 'lie', 'Forty gold. Dwarf-blessed.',
                                 why='bait to profit from newcomers')]}
        kit_agent.check_claimed_numbers(line, plan, guards, 'What is the ring worth?')
        other = [{'speaker': 'Fresco-side player', 'text': 'The ring? Forty gold.'}]
        with self.assertRaisesRegex(InvalidChange, 'ring value'):
            kit_agent.check_claimed_numbers(other, plan, guards, 'What is the ring worth?')

    def test_said_records_commit_with_the_lie_contest(self):
        self.runtime.set_player_sheet(NIK)
        revision, state = self.runtime.load()
        items = [claim('ring_value', 'uktarl', 'lie', 'Forty gold.', why='bait to profit from newcomers')]
        events = kit_claims.said_events(items, 't2', None, state)
        self.runtime.commit('t2', revision, events)
        said = self.runtime.load()[1]['claims']['said'][0]
        self.assertEqual((said['by'], said['stance'], said['contest']['lands']), ('uktarl', 'lie', True))

    def test_ring_lie_does_not_authorize_a_different_toll(self):
        plan = {'claims': [claim('ring_value', 'uktarl', 'lie', 'Forty gold.',
                                 why='bait to profit from newcomers')]}
        guards = {'numeric_facts': kit_guards.numeric_facts(SOURCE), 'speakers': kit_agent.actor_speakers(SOURCE)}
        for text in ('Passage costs forty gold.',
                     'The ring is forty gold. Passage costs forty gold.',
                     'The ring and passage both cost forty gold.'):
            with self.subTest(text=text), self.assertRaisesRegex(InvalidChange, 'passage toll'):
                kit_agent.check_claimed_numbers([{'speaker': 'Dealer', 'text': text}], plan,
                                               guards, 'What are your prices?')
        kit_agent.check_claimed_numbers(
            [{'speaker': 'Dealer', 'text': 'The ring costs forty gold. Passage costs ten gold.'}],
            plan, guards, 'What are your prices?')

    def test_planned_amount_keeps_its_currency_and_silent_claims_allow_nothing(self):
        guards = {'numeric_facts': kit_guards.numeric_facts(SOURCE)}
        text = [{'speaker': 'Dealer', 'text': 'The ring is forty gold.'}]
        for stance, version in (('lie', 'Forty silver.'), ('silence', 'Forty gold.')):
            plan = {'claims': [claim('ring_value', 'uktarl', stance, version)]}
            with self.subTest(stance=stance), self.assertRaisesRegex(InvalidChange, 'ring value'):
                kit_agent.check_claimed_numbers(text, plan, guards, 'What is the ring worth?')

    def commit_drink(self, turn_id, truth='cherry cordial', speaker='uktarl', holder='uktarl'):
        revision, state = self.runtime.load()
        item = claim('new', speaker, 'truth', truth, about='actor:uktarl/drink',
                     truth=truth, roots=['card_table'], holder=holder)
        packet = kit_claims.claims_here(SOURCE, state, state.get('player_sheet'))
        kit_claims.check_claims([item], packet, SOURCE, state)
        events = kit_claims.said_events([item], turn_id, packet, state)
        self.runtime.commit(turn_id, revision, events)
        return item

    def test_new_claim_redefinition_is_rejected_in_plan_and_atomic_commit(self):
        original = self.commit_drink('cordial')
        revision, state = self.runtime.load()
        changed = {**original, 'truth': 'ale', 'version': 'Ale.'}
        packet = kit_claims.claims_here(SOURCE, state, None)
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            kit_claims.check_claims([changed], packet, SOURCE, state)
        events = [{'type': 'advance_time', 'seconds': 60, 'evidence': 'QA rollback check.'}]
        events += kit_claims.said_events([changed], 'ale', packet, state)
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            self.runtime.commit('ale', revision, events)
        self.assertEqual(self.runtime.load(), (revision, state))
        self.commit_drink('restatement', 'Cherry cordial.')

    def test_new_claim_survives_history_eviction_and_restart(self):
        original = self.commit_drink('cordial')
        for index in range(kit_claims.SAID_LIMIT + 1):
            revision, state = self.runtime.load()
            item = claim('ring_value', 'uktarl', 'lie', 'Forty gold.',
                         why='bait to profit from newcomers')
            self.runtime.commit(f'lie-{index}', revision,
                                kit_claims.said_events([item], f'lie-{index}', None, state))
        path = self.runtime.db.execute('PRAGMA database_list').fetchone()[2]
        self.runtime.close()
        self.runtime = Runtime(path)
        _, state = self.runtime.load()
        self.assertFalse(any(record['claim'] == 'new' for record in state['claims']['said']))
        # Simulate a pre-fix snapshot after its said window evicted the original.
        legacy = copy.deepcopy(state)
        legacy['claims'].pop('established')
        revision = self.runtime.load()[0]
        with self.runtime.db:
            self.runtime.db.execute('UPDATE snapshots SET body=? WHERE revision=?',
                                    (json.dumps(legacy), revision))
        state = self.runtime.load()[1]
        packet = kit_claims.claims_here(SOURCE, state, None)
        self.assertEqual(packet['established']['actor:uktarl/drink']['truth'], 'cherry cordial')
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            kit_claims.check_claims([{**original, 'truth': 'ale'}], packet, SOURCE, state)

    def test_named_numeric_fact_mapping_handles_a_different_claim_id(self):
        source = copy.deepcopy(SOURCE)
        source['claims']['ring_lore'] = source['claims'].pop('ring_value')
        source['claims']['ring_lore']['numeric_fact'] = 'ring_value'
        guards = kit_agent.guard_context(source, {})
        plan = {'claims': [claim('ring_lore', 'uktarl', 'lie', 'Forty gold.')]}
        kit_agent.check_claimed_numbers([{'speaker': 'Dealer', 'text': 'The ring? Forty gold.'}],
                                       plan, guards, 'What is the ring worth?')
        with self.assertRaisesRegex(InvalidChange, 'passage toll'):
            kit_agent.check_claimed_numbers([{'speaker': 'Dealer', 'text': 'Passage costs forty gold.'}],
                                           plan, guards, 'What is the toll?')

    def test_conflicting_new_claims_in_one_plan_are_rejected(self):
        _, state = self.runtime.load()
        first = claim('new', 'uktarl', 'truth', 'Cordial.', about='actor:uktarl/drink',
                      truth='cherry cordial', roots=['card_table'], holder='uktarl')
        second = {**first, 'truth': 'ale', 'version': 'Ale.'}
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            kit_claims.check_claims([first, second], kit_claims.claims_here(SOURCE, state, None),
                                  SOURCE, state)

    def test_narrated_new_claim_is_durable_and_older_said_records_are_honored(self):
        original = self.commit_drink('visible-drink', speaker='narrator', holder='room')
        _, state = self.runtime.load()
        self.assertEqual(state['claims']['established']['actor:uktarl/drink']['truth'], 'cherry cordial')
        legacy = copy.deepcopy(state)
        legacy['claims'].pop('established')
        changed = {**original, 'truth': 'ale'}
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            kit_claims.check_claims([changed], kit_claims.claims_here(SOURCE, legacy, None),
                                  SOURCE, legacy)

    def test_identity_only_character_change_clears_old_stats(self):
        self.runtime.set_player_sheet(NIK)
        self.runtime.set_player_character('Brakka', 'Half-Orc', 'Fighter', 3)
        _, state = self.runtime.load()
        self.assertEqual(self.runtime.player_view()['your_character']['name'], 'Brakka')
        self.assertIsNone(state.get('player_sheet'))
        packet = kit_claims.claims_here(SOURCE, state, state.get('player_sheet'))
        self.assertIsNone(packet['pc'])
        self.assertEqual(packet['claims']['false_vampires']['pc_band'], 'blind')

    def test_reused_adjudicator_uses_current_sheet_without_caching_bonuses(self):
        adjudicator = Room6CAdjudicator(source=SOURCE, roll=lambda: 10)
        self.runtime.set_player_sheet(NIK)
        revision, state = self.runtime.load()
        first = adjudicator.resolve('I study their faces for a disguise.', revision, state)
        # Passive Insight 14 meets DC 14: automatic, nothing rolled (the roll lambda is unused).
        self.assertIn('passive Insight 14 meets DC 14', first.public_event)
        self.runtime.set_player_sheet(dull_fighter())
        revision, state = self.runtime.load()
        second = adjudicator.resolve('I study their faces for a disguise.', revision, state)
        self.assertIn('(Insight 9)', second.public_event)
        self.assertNotIn('vampire', second.public_event)
        self.runtime.set_player_character('Another', 'Human')
        revision, state = self.runtime.load()
        with self.assertRaisesRegex(PendingRuling, 'Load a character sheet or state the Insight roll'):
            adjudicator.resolve('I study their faces for a disguise.', revision, state)
        explicit = Room6CAdjudicator(source=SOURCE, insight=2, roll=lambda: 10)
        self.assertIn('(Insight 12)', explicit.resolve('I study their faces for a disguise.',
                                                     revision, state).public_event)

    def test_one_pass_knowledge_uses_the_roll_result_before_commit_and_retries_safely(self):
        self.runtime.set_player_sheet(NIK)
        bridge = kit_agent.KitChatBridge(self.runtime)
        before = self.runtime.load()
        packet = bridge.prepare('I appraise the silver ring. I rolled 11 + 7 = 18', one_pass=True)
        private = packet['input']['private']
        self.assertEqual(private['claims_here']['claims']['ring_value']['pc_band'], 'learned')
        self.assertEqual(self.runtime.load(), before)
        plan = RecordingModel().plan(private)
        plan['claims'] = [claim('ring_value', 'narrator', 'truth', 'The ring is worth twenty-five gold.')]
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'The stamped dwarven figures identify a fertility charm. '
             'The ring is worth twenty-five gold to a buyer who recognizes the work.'},
            {'speaker': 'Dealer', 'text': 'You have an eye for silver. I had hoped the ears would '
             'distract you, but the ring has stolen the evening. Take your time with it; the other '
             'three are waiting for me to finish dealing.'},
            {'speaker': 'Kit', 'text': 'An appraisal before a wager. You came prepared.',
             'reacts_to': 'appraise the silver ring'},
        ]}
        output = {'decision': plan, 'performance': speech}
        result = bridge.complete(packet['turn_id'], output)
        self.assertIn('twenty-five gold', result['spoken'])
        replay = bridge.complete(packet['turn_id'], output)
        self.assertEqual(replay['revision'], result['revision'])
        self.assertIn('ring_value', self.runtime.load()[1]['claims']['learned'])

    def test_one_pass_wrong_toll_is_rejected_before_a_corrected_ring_lie_commits(self):
        self.runtime.set_player_sheet(NIK)
        bridge = kit_agent.KitChatBridge(self.runtime)
        packet = bridge.prepare('I listen to the dealer.', one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        plan['claims'] = [claim('ring_value', 'uktarl', 'lie', 'Forty gold.',
                                why='bait to profit from newcomers')]
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'He turns the ring between finger and thumb, then '
             'sets it down beside his coins.'},
            {'speaker': 'Dealer', 'text': 'The ring? Forty gold. It was blessed by a dwarf with '
             'excellent taste and very poor luck. You may look while I deal, but keep your hands '
             'above the table; my friends have curious habits.'},
            {'speaker': 'Kit', 'text': 'The jeweler has finished. The bouncer gets a turn.',
             'reacts_to': 'keep your hands above the table'},
        ]}
        bad = copy.deepcopy(speech)
        bad['segments'][1]['text'] += ' Passage costs forty gold.'
        before = self.runtime.load()
        with self.assertRaisesRegex(kit_agent.PerformanceRejected, 'passage toll'):
            bridge.complete(packet['turn_id'], {'decision': plan, 'performance': bad})
        self.assertEqual(self.runtime.load(), before)
        result = bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})
        self.assertIn('Forty gold', result['spoken'])
        self.assertEqual(self.runtime.load()[1]['claims']['said'][-1]['contest']['lands'], True)

    def test_one_pass_new_claim_persists_and_a_later_redefinition_is_rejected(self):
        bridge = kit_agent.KitChatBridge(self.runtime)
        packet = bridge.prepare('I listen to the dealer.', one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        item = claim('new', 'uktarl', 'truth', 'Cherry cordial.', about='actor:uktarl/drink',
                     truth='cherry cordial', roots=['card_table'], holder='uktarl')
        plan['claims'] = [item]
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'He leaves his cup beside the coins and squares the '
             'deck with one slow tap.'},
            {'speaker': 'Dealer', 'text': 'Cherry cordial. I save the strong drink for the walk '
             'home, when nobody can reach my purse. You look like someone who asks questions '
             'before sitting down. Do you want a chair, or an answer first?'},
            {'speaker': 'Kit', 'text': 'At last, a drinking policy I can follow.',
             'reacts_to': 'save the strong drink'},
        ]}
        bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})
        packet = bridge.prepare('I nod to the dealer.', one_pass=True)
        self.assertEqual(packet['input']['private']['claims_here']['established']
                         ['actor:uktarl/drink']['truth'], 'cherry cordial')
        changed_plan = RecordingModel().plan(packet['input']['private'])
        changed_plan['claims'] = [{**item, 'truth': 'ale', 'version': 'Ale.'}]
        before = self.runtime.load()
        with self.assertRaisesRegex(InvalidChange, 'already established'):
            bridge.complete(packet['turn_id'], {'decision': changed_plan, 'performance': speech})
        self.assertEqual(self.runtime.load(), before)


if __name__ == '__main__':
    unittest.main()

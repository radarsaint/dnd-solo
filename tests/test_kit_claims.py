"""Claims and knowers (runtime/kit_claims.py, runtime/pc_sheet.py) in area 6c.

Nik's sheet is one example; a second, low-Wisdom sheet built inline shows the bands
come from whatever sheet is loaded, not from any one character."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_claims, kit_guards, pc_sheet
from runtime.kit_agent import Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE

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
        self.assertEqual([pc_sheet.passive(NIK, s) for s in ('perception', 'insight', 'investigation')],
                         [19, 14, 17])
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
        # Passive Perception 19 vs the dealer's slip, 10 + sleight 3 = 13: six over.
        self.assertEqual((deck['dc'], deck['pc_band'], deck['wink']), (13, 'fingerprint', 'name_kind'))
        # Knowledge is never passive: the ring waits for a player's History roll.
        self.assertEqual((ring['pc_band'], ring['wink']), ('blind', 'none'))
        self.assertIn('only when the player asks', ring['player_roll'])

    def test_a_low_wisdom_character_gets_no_fingerprint_and_no_wink(self):
        claims = self.packet(dull_fighter())
        self.assertEqual((claims['false_vampires']['pc_band'], claims['false_vampires']['wink']), ('blind', 'none'))
        self.assertEqual(claims['marked_deck']['pc_band'], 'blind')

    def test_npc_bands_come_from_stats_role_and_special_senses(self):
        ring = self.packet(NIK)['ring_value']['npc_bands']
        self.assertEqual(ring['uktarl'], 'knows')          # he counted the take
        self.assertEqual(ring['doppelganger'], 'knows')    # Read Thoughts
        self.assertEqual(ring['bandit_b'], 'anchored')     # 10 vs 15, jewelry not his domain
        deck = self.packet(NIK)['marked_deck']['npc_bands']
        self.assertEqual(deck['bandit_a'], 'close')        # passive Insight 10 vs 13

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
        self.check([claim('false_vampires', 'kit', 'wink', 'Watch the napkin.')])
        with self.assertRaisesRegex(InvalidChange, 'wink tier'):
            self.check([claim('false_vampires', 'kit', 'wink', 'Watch the napkin.')], sheet=dull_fighter())

    def test_bands_limit_what_a_speaker_can_do(self):
        self.check([claim('ring_value', 'bandit_b', 'truth', 'Silver. Melt it, five gold.')])
        with self.assertRaisesRegex(InvalidChange, 'anchored'):
            self.check([claim('ring_value', 'bandit_b', 'lie', 'Twenty-five.', why='share in the take')])

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
        self.addCleanup(self.runtime.close)
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
        result = Room6CAdjudicator(source=SOURCE).resolve('What do I know about the ring? I rolled 3 + 7 = 10',
                                                          revision, state)
        self.assertNotIn('claim_learned', [event['type'] for event in result.events])

    def test_a_planned_lie_may_name_its_number_and_an_unplanned_one_may_not(self):
        guards = {'numeric_facts': kit_guards.numeric_facts(SOURCE)}
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


if __name__ == '__main__':
    unittest.main()

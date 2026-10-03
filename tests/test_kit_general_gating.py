"""PR A, general half: skill gating, linked-claim leak sets, and the table-narration check
work on any room's data, not only area 6c. A synthetic counting-house scene: a clerk
forging a ledger (the why is Insight's; the ink tells are Perception's and Investigation's),
and a synthetic twenty-one table that marks its cards with nicks."""
import unittest

from runtime import kit_claims, kit_guards, kit_twenty_one
from runtime.state_context import InvalidChange

SCENE = {
    'facts': {
        'ledger': {'area': 'counting_house', 'visible': True, 'text': 'A fat ledger lies open on the desk.'},
        'forgery_motive': {'area': 'counting_house', 'visible': False,
                           'text': 'The clerk forges the ledger to hide what he skims for his gambling debts.'},
        'forgery_tells': {'area': 'counting_house', 'visible': False,
                          'text': 'Two inks: the newer entries are blacker and scraped over older figures.'},
        'well_note': {'area': 'well_room', 'visible': False, 'text': 'A note is tucked under the well stone.'},
    },
    'actors': {'clerk': {'location': 'counting_house'}},
    'claims': {
        'forgery_motive': {'about': 'actor:clerk/why', 'truth': 'He forges it to hide his skimming.',
                           'source': 'adventure', 'fact': 'forgery_motive', 'roots': ['forgery_motive', 'ledger'],
                           'exposure': 'hidden', 'dc': 13, 'pc_check': 'insight', 'pc_access': 'roll',
                           'subject_words': ['ledger', 'clerk', 'entries']},
        'forgery_tells': {'about': 'item:ledger/tells', 'truth': 'Two inks; scraped figures.',
                          'source': 'adventure', 'fact': 'forgery_tells',
                          'roots': ['forgery_tells', 'forgery_motive'], 'exposure': 'hidden', 'dc': 13,
                          'pc_check': 'investigation', 'pc_checks': ['investigation', 'perception'],
                          'pc_access': 'roll', 'subject_words': ['ledger', 'ink', 'entries']},
        'well_note': {'about': 'item:well/note', 'truth': 'A note under the stone.', 'source': 'adventure',
                      'fact': 'well_note', 'roots': ['well_note'], 'exposure': 'hidden', 'dc': 12,
                      'pc_check': 'investigation', 'pc_access': 'roll', 'subject_words': ['well', 'stone']},
    },
    'leak_keywords': {
        'forgery': {'revealed_by': ['forgery_motive', 'forgery_tells'],
                    'groups': [['ledger', 'entries'], ['forged', 'forgery', 'doctored']]},
    },
}
STATE = {'area': 'counting_house', 'known_facts': ['ledger'], 'claims': {'learned': []}}


def roll(skill):
    name = skill.title()
    return f'\nAsh makes {"an" if name[0] in "AEIOU" else "a"} {name} check! 1d20 (15) + 2 = `17`'


class GeneralSkillGatingTests(unittest.TestCase):
    def target(self, action):
        found = kit_claims.check_target(action, SCENE, STATE)
        return found[0] if found else None

    def test_each_skill_finds_its_own_claim_on_the_same_subject(self):
        self.assertEqual(self.target('I study the ledger entries.' + roll('insight')), 'forgery_motive')
        self.assertEqual(self.target('I study the ledger entries.' + roll('investigation')), 'forgery_tells')
        self.assertEqual(self.target('I study the ledger entries.' + roll('perception')), 'forgery_tells')

    def test_named_and_implied_skills(self):
        self.assertEqual(kit_claims.chosen_skill('I use Insight on the clerk.'), 'insight')
        self.assertEqual(kit_claims.chosen_skill('I examine the ink.'), 'investigation')
        self.assertIsNone(kit_claims.chosen_skill('I examine the ink.', implied=False))
        self.assertEqual(kit_claims.chosen_skill("I read the clerk's motive."), 'insight')

    def test_a_skill_routes_to_the_linked_claim_or_to_nothing(self):
        motive = SCENE['claims']['forgery_motive']
        self.assertEqual(kit_claims.gated_claim(SCENE, STATE, 'forgery_motive', motive, 'perception')[0],
                         'forgery_tells')
        tells = SCENE['claims']['forgery_tells']
        self.assertEqual(kit_claims.gated_claim(SCENE, STATE, 'forgery_tells', tells, 'insight')[0],
                         'forgery_motive')
        note = SCENE['claims']['well_note']
        self.assertIsNone(kit_claims.gated_claim(SCENE, {'area': 'well_room'}, 'well_note', note, 'insight'),
                          'no linked claim takes Insight: it reveals nothing')
        learned = {**STATE, 'known_facts': ['ledger', 'forgery_tells']}
        self.assertIsNone(kit_claims.gated_claim(SCENE, learned, 'forgery_motive', motive, 'perception'))

    def test_other_rooms_claims_are_never_targets(self):
        self.assertIsNone(self.target('I search the well stone.' + roll('investigation')))

    def test_pc_checks_are_validated(self):
        bad = {**SCENE, 'claims': {**SCENE['claims'],
                                   'forgery_tells': {**SCENE['claims']['forgery_tells'], 'pc_checks': ['perception']}}}
        with self.assertRaises(InvalidChange):
            kit_claims.compile_claims(bad)

    def test_a_leak_set_opens_on_any_of_its_facts(self):
        sets = kit_guards.leak_sets(SCENE)
        line = 'The ledger entries are forged.'
        with self.assertRaises(InvalidChange):
            kit_guards.check_paraphrased_leaks(line, {}, '', sets)
        for fact in ('forgery_motive', 'forgery_tells'):
            kit_guards.check_paraphrased_leaks(line, {'known_facts_here': [SCENE['facts'][fact]['text']]}, '', sets)


class GeneralTableNarrationTests(unittest.TestCase):
    CONFIG = {'cheat': {'marks': {'units': ['nick', 'nicks'], 'count': 'value_minus_one'}}}
    PUBLIC = {'round': {'cards': ['king of hearts', '7 of clubs'], 'dealer_shows': '2 of spades'}}

    def test_another_tables_marks_and_cards(self):
        check = kit_twenty_one.check_narration
        self.assertEqual(check('Six nicks on your seven, nine on your king.', self.PUBLIC, self.CONFIG), [])
        self.assertTrue(check('Two nicks on your seven.', self.PUBLIC, self.CONFIG))
        self.assertTrue(check('He turns the queen of hearts.', self.PUBLIC, self.CONFIG))
        self.assertTrue(check('Your ace gleams.', self.PUBLIC, self.CONFIG))

    def test_no_scheme_no_count_check(self):
        self.assertEqual(kit_twenty_one.check_narration('Two pricks on your seven.', self.PUBLIC, {}), [])


if __name__ == '__main__':
    unittest.main()

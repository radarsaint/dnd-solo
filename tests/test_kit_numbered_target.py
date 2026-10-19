"""Nagatha's re-probe (High, on main de442cf): attack targeting ignored the number. "I stab giant
rat 1" and "I stab giant rat 5" both hit Giant rat 6, the first actor whose name matched (every
rat's first word, "giant", named all of them). An exact numbered name wins; a bare number never
names a foe; an unnumbered name several foes share asks which one rather than guess.

Synthetic roadcamp (tests/fixtures/rooms) relabelled Giant rat 6, 1 and 5 (in that actor order, so
the first-match bug shows); every die pinned. No book text."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_kit_combat_checkpoints as checkpoints
from test_kit_combat_checkpoints import NIK, Camp, without_shield

RATS = {'harl': 'Giant rat 6', 'cutthroat_a': 'Giant rat 1', 'cutthroat_b': 'Giant rat 5'}


def rat_camp(test, names=RATS, marks=None):
    source = json.loads(checkpoints.CAMP.read_text())
    for key, name in names.items():
        source['actors'][key]['name'] = name
    for key, mark in (marks or {}).items():
        source['actors'][key].update(mark)
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    path = Path(temp.name) / 'rats.json'
    path.write_text(json.dumps(source))
    with mock.patch.object(checkpoints, 'CAMP', path):
        return Camp(test, roll=lambda: 2, sheet=without_shield(NIK))


def hit_on(test, words):
    """The held hit's target: a hit with no damage waits on its roll, so the target is plain."""
    table = rat_camp(test)
    table.act('Initiative 25. ' + words)
    return (table.fight.get('pending') or {}).get('target')


class NumberedTargets(unittest.TestCase):
    def test_an_exact_numbered_name_wins(self):
        for words, key in (('I stab giant rat 1 with my dagger, 18 to hit.', 'cutthroat_a'),
                           ('I stab giant rat 5 with my dagger, 18 to hit.', 'cutthroat_b'),
                           ('I stab Giant Rat 6 with my dagger, 18 to hit.', 'harl'),
                           ('I stab rat 5 with my dagger, 18 to hit.', 'cutthroat_b')):
            with self.subTest(words=words):
                self.assertEqual(hit_on(self, words), key, words)

    def test_a_bare_number_in_the_roll_names_no_rat(self):
        table = rat_camp(self)
        table.act('Initiative 6. I stab giant rat 1 with my dagger, 18 to hit.')
        self.assertEqual(table.fight['pending']['target'], 'cutthroat_a', "'6' in the initiative is no rat")

    def test_an_unnumbered_shared_name_asks_which_one(self):
        table = rat_camp(self)
        exc = table.held('Initiative 25. I stab the giant rat with my dagger, 18 to hit.')
        self.assertIn('Which', str(exc))
        for name in ('Giant rat 1', 'Giant rat 5', 'Giant rat 6'):
            self.assertIn(name, str(exc))
        self.assertFalse(table.state.get('combat'), 'nothing committed on a guess')

    def test_a_unique_unnumbered_name_still_targets(self):
        table = rat_camp(self, {**RATS, 'cutthroat_b': 'Fire-side cutthroat'})
        table.act('Initiative 25. I stab the cutthroat with my dagger, 18 to hit.')
        self.assertEqual(table.fight['pending']['target'], 'cutthroat_b')



ONE_TO_THREE = {'harl': 'Giant rat 1', 'cutthroat_a': 'Giant rat 2', 'cutthroat_b': 'Giant rat 3'}
ONE_RAT = {'harl': 'Bandit captain', 'cutthroat_a': 'Giant rat 3', 'cutthroat_b': 'Fire-side cutthroat'}
I = 'Initiative 25. '


class SharedNamesAndPerception(unittest.TestCase):
    """Nagatha's re-probe at ef92808. High: 'the rat' never asked and hit the first actor (with one
    rat beside a captain, the captain); a missing number ('rat 3', 'Rat 2') picked someone. High (trial
    merge with #131): an unperceived rat could be targeted, then its damage raised KeyError. Medium:
    the 'Which one' list named unperceived rats. Low: a dead numbered foe and a missing number."""

    def target(self, words, names=RATS, marks=None):
        table = rat_camp(self, names, marks)
        table.act(I + words)
        return table.fight['pending']['target']

    def asks(self, words, names=RATS, marks=None):
        table = rat_camp(self, names, marks)
        exc = table.held(I + words)
        self.assertFalse(table.state.get('combat'), 'nothing committed')
        return str(exc)

    def test_one_name_set(self):
        from runtime import kit_names
        table = rat_camp(self, ONE_TO_THREE)
        found = kit_names.names(table.runtime.source(), 'cutthroat_b')
        self.assertTrue({'giant rat 3', 'rat 3', 'rat'} <= found, found)
        self.assertNotIn('3', found, 'a bare number is never a name')
        source = table.runtime.source()
        self.assertEqual(kit_names.resolve('rat 3', source, list(ONE_TO_THREE)), ('cutthroat_b', []))
        captain = rat_camp(self, ONE_RAT).runtime.source()
        self.assertEqual(kit_names.resolve('captain 3', captain, ['harl', 'cutthroat_a']), ('harl', []),
                         "an unnumbered foe's name still names it before a number")

    def test_the_shared_head_noun_asks_which_one(self):
        for words in ('I stab the rat with my dagger, 18 to hit.', 'I fire bolt the rat, 18 to hit.'):
            with self.subTest(words=words):
                self.assertIn('Which one: Giant rat 1, Giant rat 5 or Giant rat 6?', self.asks(words))

    def test_a_lone_rat_is_the_rat(self):
        self.assertEqual(self.target('I stab the rat with my dagger, 18 to hit.', ONE_RAT), 'cutthroat_a')

    def test_an_ordinal_names_the_numbered_foe(self):
        self.assertEqual(self.target('I stab the third rat with my dagger, 18 to hit.', ONE_TO_THREE), 'cutthroat_b')
        self.assertIn('Which one', self.asks('I stab the third rat with my dagger, 18 to hit.'))

    def test_a_numbered_foe_not_here_says_so(self):
        for words, names, shown in (('I stab rat 3 with my dagger, 18 to hit.', RATS, 'Giant rat 3'),
                                    ('I stab Rat 2 with my dagger, 18 to hit.', RATS, 'Giant rat 2'),
                                    ('I stab giant rat 1 with my dagger, 18 to hit.', ONE_RAT, 'Giant rat 1')):
            with self.subTest(words=words):
                self.assertIn(f"There's no {shown} here", self.asks(words, names))

    def test_an_unperceived_foe_is_no_target_and_not_offered(self):
        for mark in ({'visible': False}, {'conditions': ['invisible']}):
            with self.subTest(mark=mark):
                marks = {'cutthroat_b': mark}
                self.assertIn("There's no Giant rat 3 here that you can see",
                              self.asks('I stab giant rat 3 with my dagger, 18 to hit.', ONE_TO_THREE, marks))
                said = self.asks('I stab the giant rat with my dagger, 18 to hit.', ONE_TO_THREE, marks)
                self.assertIn('Which one: Giant rat 1 or Giant rat 2?', said)
                self.assertNotIn('Giant rat 3', said)

    def test_a_dead_numbered_foe_is_down(self):
        table = rat_camp(self, ONE_TO_THREE)
        table.act(I + 'I stab giant rat 2 with my dagger, 18 to hit, 20 damage.')
        self.assertIn('Giant rat 2 is already down', str(table.held('I stab giant rat 2 with my dagger, 18 to hit.')))


if __name__ == '__main__':
    unittest.main()

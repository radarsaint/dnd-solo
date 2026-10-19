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


def rat_camp(test, names=RATS):
    source = json.loads(checkpoints.CAMP.read_text())
    for key, name in names.items():
        source['actors'][key]['name'] = name
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


if __name__ == '__main__':
    unittest.main()

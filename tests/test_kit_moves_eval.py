"""v0.16.0: the labelled player-move set (tests/fixtures/moves/labelled_moves.tsv, synthetic) and the
typo repair in front of the move and skill readers (runtime/kit_lexicon.py)."""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_lexicon, kit_moves

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('eval_moves', ROOT / 'tools' / 'eval_moves.py')
evaluate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate)

HAS_LIBS = kit_lexicon._rf_process is not None and kit_lexicon._SpellChecker is not None
SCRIPTED = ("Let's play. Here's my character.", '"That\'s the Sentinel Shield, advantage on Perception." Yes, '
            "let's start.", 'I scan the thickets for anyone watching.', '15', 'I toss a stone into the left thicket.',
            'What do I know about goblins raiding this road?', '12', 'Initiative 14')


def fallback():
    """kit_lexicon as it runs on a host without the optional libraries."""
    kit_lexicon._english.cache_clear()
    return mock.patch.multiple(kit_lexicon, _rf_process=None, _rf_osa=None, _SpellChecker=None)


class LabelledSetTest(unittest.TestCase):
    def test_the_set_is_big_and_covers_every_move(self):
        rows = list(evaluate.rows())
        self.assertGreaterEqual(len(rows), 150)
        self.assertEqual({m for m, _s, _t in rows} - {'*'}, set(kit_moves.MOVES))

    def test_accuracy_floor(self):
        """Measured at v0.16.0: move 145/160, skill 80/92 with the libraries; 144/160, 79/92 without.
        Was 121/160 and 79/92 at v0.15.0. A change that drops below the floor is a regression."""
        per_move, per_skill, _ = evaluate.score()
        hit, n = evaluate.total(per_move)
        self.assertGreaterEqual(hit / n, 0.88)
        hit, n = evaluate.total(per_skill)
        self.assertGreaterEqual(hit / n, 0.85)
        self.assertGreaterEqual(per_move['talk'][0] / per_move['talk'][1], 0.8)

    def test_accuracy_floor_without_the_libraries(self):
        with fallback():
            per_move, per_skill, _ = evaluate.score()
        kit_lexicon._english.cache_clear()
        self.assertGreaterEqual(evaluate.total(per_move)[0] / evaluate.total(per_move)[1], 0.88)


class RepairTest(unittest.TestCase):
    def test_clean_lines_never_change(self):
        for line in SCRIPTED:
            self.assertEqual(kit_lexicon.normalize(line), line)
        for line in ('I charge the orc and slash at it', 'I ask the kid where his parents are',
                     'I tell Brindlewick the closest road is closed', 'I case the joint'):
            self.assertEqual(kit_lexicon.normalize(line), line)

    @unittest.skipUnless(HAS_LIBS, 'rapidfuzz + pyspellchecker not installed')
    def test_typos_are_repaired_toward_what_kit_reads(self):
        self.assertEqual(kit_lexicon.normalize('i atack the guy'), 'i attack the guy')
        self.assertEqual(kit_lexicon.normalize('i aks the kid'), 'i ask the kid')
        self.assertEqual(kit_lexicon.normalize('sneakin up on the camp'), 'sneaking up on the camp')
        self.assertEqual(kit_moves.classify('i atack the guy closest to me'), 'fight')
        self.assertEqual(kit_moves.classify('i aks the kid where his parents are'), 'talk')

    def test_without_the_libraries_only_long_one_letter_typos_are_repaired(self):
        with fallback():
            self.assertEqual(kit_lexicon.normalize('i look arround'), 'i look around')
            self.assertEqual(kit_lexicon.normalize('i aks the kid'), 'i aks the kid')
            self.assertEqual(kit_lexicon.normalize('I charge the orc'), 'I charge the orc')
        kit_lexicon._english.cache_clear()


class RoutingTest(unittest.TestCase):
    def test_social_skill_lines_are_talk(self):
        for line in ('I try to convince the guard to let us in', 'I threaten the thug until he talks',
                     'I bluff that the captain sent us', 'Is he lying?'):
            self.assertEqual(kit_moves.classify(line), 'talk', line)

    def test_climbing_and_sneaking_are_moves(self):
        for line in ('I climb the cliff', 'I jump across the gap', 'I sneak past the guards'):
            self.assertEqual(kit_moves.classify(line), 'move', line)

    def test_hitting_someone_is_a_fight_and_a_thrown_stone_is_not(self):
        self.assertEqual(kit_moves.classify('I hit him with my mace'), 'fight')
        self.assertEqual(kit_moves.classify('I toss a stone into the left thicket.'), 'use')

    def test_rules_and_check_questions_ask_the_dm(self):
        for line in ('Wait, am I still hidden?', "Shouldn't that be an Insight check?"):
            self.assertEqual(kit_moves.classify(line), 'ask_dm', line)


if __name__ == '__main__':
    unittest.main()

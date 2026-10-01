import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from scripts.blind_performance_review import load_experiment, main, render_review


def experiment():
    return {'experiment': 'area-06c-pilot', 'pairs': [{
        'case_id': 'P1 greeting',
        'public_context': 'Four pale people play cards near the door.',
        'player_input': 'Hi. What is going on?',
        'candidates': [
            {'variant_id': 'current-internal', 'spoken': 'Dealer: Care for a game?'},
            {'variant_id': 'actor-internal', 'spoken': 'Dealer: What did you expect to find?'},
        ],
    }]}


class BlindReviewTests(unittest.TestCase):
    def test_blind_packet_keeps_variant_mapping_separate_and_reproducible(self):
        data = experiment()
        packet, key = render_review(data, 'example-hash', 19)
        self.assertNotIn('current-internal', packet)
        self.assertNotIn('actor-internal', packet)
        self.assertNotIn('example-hash', packet)
        self.assertIn('Care for a game?', packet)
        self.assertIn('What did you expect', packet)
        self.assertEqual({key['mapping'][0]['A'], key['mapping'][0]['B']},
                         {'current-internal', 'actor-internal'})
        self.assertEqual((packet, key), render_review(data, 'example-hash', 19))

    def test_private_trace_field_is_rejected_before_packet_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.json'
            data = experiment()
            data['pairs'][0]['candidates'][0]['trace'] = 'secret motive'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'only variant_id and spoken'):
                load_experiment(path)

    def test_cli_refuses_to_overwrite_answer_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, review, key = (folder / name for name in ('source.json', 'review.md', 'key.json'))
            source.write_text(json.dumps(experiment()), encoding='utf-8')
            main(['--input', str(source), '--review', str(review), '--key', str(key), '--seed', '19'])
            self.assertIn('Continuation A', review.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(key.read_text(encoding='utf-8'))['seed'], 19)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--input', str(source), '--review', str(review), '--key', str(key), '--seed', '20'])
            self.assertEqual(json.loads(key.read_text(encoding='utf-8'))['seed'], 19)


if __name__ == '__main__':
    unittest.main()

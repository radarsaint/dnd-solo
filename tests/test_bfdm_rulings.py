"""Schema check for the source-checked BFDM ruling fixture.

This does not load Kit and does not treat the fixture as doctrine.
"""
import json
import re
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rulings" / "bfdm_rulings.jsonl"
KEYS = {"player_line", "intent", "my_ruling", "hidden_info_risk", "note"}
NOTE = re.compile(r"Paired by (word|name|mention|reply)\. (S3|EC) messages-\d{4}, \d{17,20}\.$")


class TestBfdmRulings(unittest.TestCase):
    def test_schema_and_every_note_cites_a_shard_and_message(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 300)
        seen = set()
        for n, line in enumerate(lines, 1):
            row = json.loads(line)
            self.assertEqual(set(row), KEYS, n)
            self.assertTrue(row["player_line"].strip(), n)
            self.assertTrue(row["intent"].strip(), n)
            self.assertIn(";", row["my_ruling"], n)
            self.assertIn(row["hidden_info_risk"], ("yes", "no"), n)
            self.assertRegex(row["note"], NOTE, n)
            message_id = row["note"].rsplit(" ", 1)[-1].rstrip(".")
            self.assertNotIn(message_id, seen, n)
            seen.add(message_id)


if __name__ == "__main__":
    unittest.main()

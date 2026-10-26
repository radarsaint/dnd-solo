"""Schema check for the source-checked BFDM ruling fixture.

This does not load Kit and does not treat the fixture as doctrine.
The follow-up file is not a verified set.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rulings"
FIXTURE = ROOT / "bfdm_rulings.jsonl"
FOLLOW = ROOT / "bfdm_rulings_followup.jsonl"
NOTES = ROOT / "PROVISIONAL_NOTES.md"
KEYS = {"player_line", "intent", "my_ruling", "hidden_info_risk", "note"}
INTENTS = {
    "social/speech",
    "other",
    "move",
    "interjection",
    "mixed",
    "spell",
    "ritual",
    "consent",
    "attack",
    "look",
    "negation",
    "roll report",
    "stunt",
    "search/examine",
    "ooc/meta",
    "emote",
}
NOTE = re.compile(
    r"Paired by (word|name|mention|reply)\. "
    r"server \d{17,20} channel \d{17,20} message \d{17,20} reply \d{17,20}\.$"
)
SERVERS = {"636012145204527125", "850779382791536640"}
DROPPED = "864445238209675284"
MIXED_ID = "863508929778941972"
FULL_TEXT_ID = "864393053490249778"


class TestBfdmRulings(unittest.TestCase):
    def test_schema_and_every_note_cites_server_channel_and_message(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 300)
        seen = set()
        blob = "\n".join(lines)
        self.assertNotIn(DROPPED, blob)
        self.assertNotIn("messages-", blob)
        self.assertNotIn("Everyone is PC", blob)
        found_mixed = False
        found_full = False
        for n, line in enumerate(lines, 1):
            row = json.loads(line)
            self.assertEqual(set(row), KEYS, n)
            self.assertTrue(row["player_line"].strip(), n)
            self.assertIn(row["intent"], INTENTS, n)
            self.assertIn(";", row["my_ruling"], n)
            self.assertIn(row["hidden_info_risk"], ("yes", "no"), n)
            self.assertRegex(row["note"], NOTE, n)
            self.assertNotIn("orpheus", row["player_line"].lower(), n)
            self.assertNotIn("<@", row["player_line"], n)
            self.assertNotIn("<@", row["my_ruling"], n)
            message_id = re.search(r"message (\d+)", row["note"]).group(1)
            server_id = re.search(r"server (\d+)", row["note"]).group(1)
            self.assertIn(server_id, SERVERS, n)
            self.assertNotIn(message_id, seen, n)
            seen.add(message_id)
            if message_id == MIXED_ID:
                found_mixed = True
                self.assertEqual(row["intent"], "mixed", n)
            if message_id == FULL_TEXT_ID:
                found_full = True
                self.assertIn("painting tonight", row["my_ruling"])
        self.assertTrue(found_mixed)
        self.assertTrue(found_full)

    def test_notes_state_the_gaps(self):
        text = NOTES.read_text(encoding="utf-8")
        self.assertIn("26 rows have Avrae messages in between", text)
        self.assertIn("3 skip an image-only reply", text)
        self.assertIn("@mentions are stripped", text)
        self.assertIn("messages-NNNN", text)
        self.assertIn("never a verified pair", text)

    def test_followup_is_not_verified(self):
        lines = FOLLOW.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 1000)
        kinds = set()
        for n, line in enumerate(lines, 1):
            row = json.loads(line)
            self.assertIs(row["verified"], False, n)
            self.assertIn(row["link"], ("avrae", "adjacency"), n)
            self.assertIn("Not verified", row["note"], n)
            self.assertNotIn("messages-", row["note"], n)
            if row["link"] == "adjacency":
                self.assertEqual(row["link_reason"], "adjacent", n)
            else:
                self.assertIn(row["link_reason"], ("actor", "reply"), n)
            kinds.add(row["link"])
            self.assertTrue(row["source_line"].strip(), n)
            self.assertTrue(row["my_ruling"].strip(), n)
        self.assertEqual(kinds, {"avrae", "adjacency"})


if __name__ == "__main__":
    unittest.main()

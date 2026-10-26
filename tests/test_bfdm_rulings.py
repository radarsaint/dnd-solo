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
NARRATION_ID = "738203001797345330"
NUMBERED_ID = "745509802968350730"
JOKE_ID = "868718296411820062"
TABLE_ID = "864001933106479126"
GONE = (
    "739267454592188487",
    "739722291581845505",
    "736749924745379841",
    "736750260051673098",
)


class TestBfdmRulings(unittest.TestCase):
    def test_schema_and_every_note_cites_server_channel_and_message(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 300)
        self.assertEqual(len(lines), 665)
        seen = set()
        blob = "\n".join(lines)
        self.assertNotIn(DROPPED, blob)
        self.assertNotIn("messages-", blob)
        self.assertNotIn("Everyone is PC", blob)
        for bad in GONE:
            self.assertNotIn(bad, blob)
        found_mixed = False
        found_full = False
        found_narr = False
        found_names = False
        found_joke = False
        found_table = False
        reply_ids = []
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
            reply_id = re.search(r"reply (\d+)", row["note"]).group(1)
            server_id = re.search(r"server (\d+)", row["note"]).group(1)
            self.assertIn(server_id, SERVERS, n)
            self.assertNotIn(message_id, seen, n)
            self.assertNotIn(reply_id, reply_ids, n)
            seen.add(message_id)
            reply_ids.append(reply_id)
            if message_id == MIXED_ID:
                found_mixed = True
                self.assertEqual(row["intent"], "mixed", n)
            if message_id == FULL_TEXT_ID:
                found_full = True
                self.assertIn("painting tonight", row["my_ruling"])
            if message_id == NARRATION_ID:
                found_narr = True
                self.assertTrue(row["my_ruling"].startswith("just let it happen;"), n)
            if message_id == NUMBERED_ID:
                found_names = True
                self.assertEqual(row["player_line"], "Sylric PC1 PC2 PC3 PC4 PC5 PC6")
                self.assertNotIn("PC3 PC3", row["player_line"])
            if message_id == JOKE_ID:
                found_joke = True
                self.assertIn("BEAR CASTOR", row["player_line"])
                self.assertNotIn("BEAR PC", row["player_line"])
            if message_id == TABLE_ID:
                found_table = True
                self.assertEqual(row["intent"], "ooc/meta")
        self.assertTrue(found_mixed)
        self.assertTrue(found_full)
        self.assertTrue(found_narr)
        self.assertTrue(found_names)
        self.assertTrue(found_joke)
        self.assertTrue(found_table)

    def test_notes_state_the_gaps(self):
        text = NOTES.read_text(encoding="utf-8")
        self.assertIn("26 rows have Avrae messages in between", text)
        self.assertIn("3 skip an image-only reply", text)
        self.assertIn("@mentions are stripped", text)
        self.assertIn("messages-NNNN", text)
        self.assertIn("never a verified pair", text)
        self.assertIn("Chadmart", text)

    def test_followup_is_not_verified(self):
        lines = FOLLOW.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 1000)
        kinds = set()
        tags = set()
        reply_ids = []
        blob = "\n".join(lines)
        for bad in GONE:
            self.assertNotIn(bad, blob)
        self.assertNotRegex(blob, r"(?i)fabertell|fabertel|fabertale")
        self.assertIn("Chadmarts", blob)
        self.assertEqual(blob.count("736749783506485340"), 1)
        for n, line in enumerate(lines, 1):
            row = json.loads(line)
            self.assertIs(row["verified"], False, n)
            self.assertIn(row["link"], ("avrae", "adjacency"), n)
            self.assertIn("Not verified", row["note"], n)
            self.assertNotIn("messages-", row["note"], n)
            reply_id = re.search(r"reply (\d+)", row["note"]).group(1)
            self.assertNotIn(reply_id, reply_ids, n)
            reply_ids.append(reply_id)
            if row["link"] == "adjacency":
                self.assertEqual(row["link_reason"], "adjacent", n)
                self.assertIn(row["tag"], ("chatter", "likely_play", "unsorted"), n)
                tags.add(row["tag"])
            else:
                self.assertIn(row["link_reason"], ("actor", "reply"), n)
                self.assertNotIn("tag", row)
            kinds.add(row["link"])
            self.assertTrue(row["source_line"].strip(), n)
            self.assertTrue(row["my_ruling"].strip(), n)
        self.assertEqual(kinds, {"avrae", "adjacency"})
        self.assertEqual(tags, {"chatter", "likely_play", "unsorted"})


if __name__ == "__main__":
    unittest.main()

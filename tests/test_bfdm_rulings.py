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
OOC = ROOT / "bfdm_rulings_ooc.jsonl"
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
ROW226_ID = "735955305799614595"
ROW351_ID = "742113158923157514"
ROW361_ID = "743278855988576366"
ROW426_ID = "734625715487506533"
ROW476_ID = "736859400173781013"
ROW553_ID = "741749695201935502"
GONE = (
    "739267454592188487",
    "739722291581845505",
    "736749924745379841",
    "736750260051673098",
)

# Character names on the scrub list. Whole-word, case-insensitive.
NAMES = frozenset(
    {
        "adrian",
        "amara",
        "apgan",
        "arc",
        "baeshra",
        "bo",
        "cairn",
        "castor",
        "cato",
        "chad",
        "chadowski",
        "copper",
        "demetrius",
        "dwendal",
        "ebuc",
        "eldon",
        "eliza",
        "evelyn",
        "faber",
        "fabertale",
        "fabertel",
        "fabertell",
        "finn",
        "florian",
        "fuddles",
        "gil",
        "gneiss",
        "goan",
        "goanhawe",
        "goose",
        "grimlock",
        "heki",
        "irynx",
        "jigsaw",
        "johann",
        "johnathan",
        "kiln",
        "kukudh",
        "kyrre",
        "leaf",
        "lilia",
        "llewelyn",
        "luard",
        "lucy",
        "lucky",
        "malathor",
        "meorys",
        "mictlan",
        "navar",
        "nolan",
        "ophelia",
        "orpheus",
        "ozgur",
        "paeton",
        "pearl",
        "percival",
        "rah",
        "riga",
        "rigatony",
        "rockman",
        "roy",
        "rush",
        "sabrine",
        "selene",
        "seraxa",
        "skitter",
        "sonny",
        "storm",
        "thomas",
        "tortillini",
        "traxim",
        "vee",
        "vivica",
        "web",
        "willow",
        "wren",
        "wynne",
    }
)
NAME_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])("
    + "|".join(sorted((re.escape(n) for n in NAMES), key=len, reverse=True))
    + r")(?![A-Za-z0-9_])"
)
PHRASE_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])("
    r"chad chadowski|chad mcfilligan|chad chadington|father chad"
    r")(?![A-Za-z0-9_])"
)
PROTECTED = [
    r"(?i)chad-?marts?",
    r"(?i)how lucky!",
    r"(?i)coils arc",
    r"(?i)lucky charms?",
    r"(?i)lucky point",
    r"(?i)pink pearl",
    r"(?i)pearl of power",
    r"(?i)willow wand",
    r"(?i)willow trees?",
    r"(?i)lunch rush",
    r"(?i)\bno rush\b",
    r"(?i)the rush\b",
    r"(?i)a rush of",
    r"(?i)in a rush of",
    r"(?i)mechanical rush",
    r"(?i)\band rush to\b",
    r"(?i)(?:story|reconciliation|major|character|good) arc\b",
    r"(?i)for arc reasons",
    r"(?i)tesla coils arc",
    r"(?i)bo-nus",
    r"(?i)everyone is \w+",
]


def is_castor_pun(text):
    if re.search(r"(?i)bear\s+castor", text):
        return True
    if re.search(r"(?i)everyone is castor", text):
        return True
    if re.search(
        r"(?i)(hail castor|rogue castor|prudish castor|castor on|"
        r"detective business castor|nice castor|castor it up|"
        r"castor in your room|only one castor|shame among all castor|"
        r"castors? as if to castor|castoring)",
        text,
    ):
        return True
    # Canonical spelling of this name, any case. A line that only had the
    # plural now has one castor token. That token is still the name.
    return re.search(r"(?i)\bcastors?\b", text) is not None


def protected_spans(text):
    spans = []
    for pat in PROTECTED:
        for m in re.finditer(pat, text):
            spans.append((m.start(), m.end()))
    if is_castor_pun(text):
        for m in re.finditer(r"(?i)\bcastors?\b", text):
            spans.append((m.start(), m.end()))
    return spans


def in_spans(pos, end, spans):
    return any(not (end <= a or pos >= b) for a, b in spans)


def name_leftovers(path, fields):
    """Whole-word list names that are not documented exceptions."""
    hits = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        pair = " ".join(row.get(f) or "" for f in fields)
        pair_pun = is_castor_pun(pair)
        for field in fields:
            text = row.get(field) or ""
            spans = protected_spans(text)
            if pair_pun:
                for m in re.finditer(r"(?i)\bcastors?\b", text):
                    spans.append((m.start(), m.end()))
            for m in NAME_RE.finditer(text):
                if in_spans(m.start(), m.end(), spans):
                    continue
                hits.append((n, field, m.group(1), text[max(0, m.start() - 32) : m.end() + 32]))
            found = PHRASE_RE.search(text)
            if found:
                hits.append((n, field, found.group(0), text[:80]))
    return hits


def load_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def by_message(rows):
    out = {}
    for row in rows:
        mid = re.search(r"message (\d+)", row["note"]).group(1)
        out[mid] = row
    return out


class TestBfdmRulings(unittest.TestCase):
    def test_schema_and_every_note_cites_server_channel_and_message(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 300)
        self.assertEqual(len(lines), 620)
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
        found_226 = False
        found_351 = False
        found_361 = False
        found_426 = False
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
            if row["intent"] == "ooc/meta":
                self.assertFalse(
                    row["my_ruling"].startswith("just let it happen;"),
                    n,
                )
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
            if message_id == ROW226_ID:
                found_226 = True
                self.assertEqual(row["intent"], "ooc/meta", n)
            if message_id == ROW351_ID:
                found_351 = True
                self.assertEqual(row["intent"], "ooc/meta", n)
            if message_id == ROW361_ID:
                found_361 = True
                self.assertEqual(row["intent"], "ooc/meta", n)
            if message_id == ROW426_ID:
                found_426 = True
                self.assertEqual(row["intent"], "social/speech", n)
        self.assertTrue(found_mixed)
        self.assertTrue(found_full)
        self.assertTrue(found_narr)
        self.assertTrue(found_names)
        self.assertTrue(found_joke)
        self.assertTrue(found_table)
        self.assertTrue(found_226)
        self.assertTrue(found_351)
        self.assertTrue(found_361)
        self.assertTrue(found_426)
        ooc_rows = load_rows(OOC)
        ooc_index = by_message(ooc_rows)
        self.assertEqual(len(ooc_rows), 45)
        self.assertEqual(ooc_index[ROW476_ID]["intent"], "ooc/meta")
        self.assertEqual(ooc_index[ROW553_ID]["intent"], "ooc/meta")
        self.assertTrue(ooc_index[ROW476_ID]["player_line"].startswith("(does that last forever?)"))
        self.assertTrue(ooc_index[ROW553_ID]["player_line"].startswith("(Can I hold an action?)"))

    def test_notes_state_the_gaps(self):
        text = NOTES.read_text(encoding="utf-8")
        self.assertIn("26 rows have Avrae messages in between", text)
        self.assertIn("3 skip an image-only reply", text)
        self.assertIn("@mentions are stripped", text)
        self.assertIn("messages-NNNN", text)
        self.assertIn("never a verified pair", text)
        self.assertIn("Chadmart", text)
        self.assertIn("55%", text)
        self.assertIn("How lucky!", text)
        self.assertIn("coils arc", text)
        self.assertIn("not a claim that only the castor jokes remain", text)
        self.assertIn("embed title", text)
        self.assertNotIn("Two cases are left on purpose", text)

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
        self.assertNotIn('"link": "avrae"', blob)
        self.assertNotRegex(blob, r"(?i)@kiln|@gneiss|@dwendal")
        for n, line in enumerate(lines, 1):
            row = json.loads(line)
            self.assertIs(row["verified"], False, n)
            self.assertEqual(row["link"], "adjacency", n)
            self.assertIn("Not verified", row["note"], n)
            self.assertNotIn("messages-", row["note"], n)
            reply_id = re.search(r"reply (\d+)", row["note"]).group(1)
            self.assertNotIn(reply_id, reply_ids, n)
            reply_ids.append(reply_id)
            self.assertEqual(row["link_reason"], "adjacent", n)
            self.assertIn(row["tag"], ("chatter", "likely_play", "unsorted"), n)
            tags.add(row["tag"])
            kinds.add(row["link"])
            self.assertTrue(row["source_line"].strip(), n)
            self.assertTrue(row["my_ruling"].strip(), n)
        self.assertEqual(kinds, {"adjacency"})
        self.assertEqual(tags, {"chatter", "likely_play", "unsorted"})

    def test_no_whole_word_names_outside_exceptions(self):
        """Acceptance bar: list names may remain only as documented exceptions."""
        verified = name_leftovers(FIXTURE, ("player_line", "my_ruling"))
        follow = name_leftovers(FOLLOW, ("source_line", "my_ruling"))
        self.assertEqual(verified, [], verified[:8])
        self.assertEqual(follow, [], follow[:8])
        blob_v = FIXTURE.read_text(encoding="utf-8")
        blob_f = FOLLOW.read_text(encoding="utf-8")
        self.assertNotIn("Chad Chadowski", blob_v)
        self.assertNotIn("Chad Chadowski", blob_f)
        self.assertNotRegex(blob_v, r"(?i)father chad")
        self.assertNotRegex(blob_f, r"(?i)father chad")
        self.assertIn("BEAR CASTOR", blob_v)
        self.assertIn("Everyone is castor", blob_v)
        self.assertIn("Chadmarts", blob_f)
        self.assertIn("How lucky!", blob_f)
        self.assertIn("coils arc", blob_f)

    def test_pass3_validator(self):
        rows = load_rows(FIXTURE)
        follow = load_rows(FOLLOW)
        ooc = load_rows(OOC)
        notes = NOTES.read_text(encoding="utf-8")
        index = by_message(rows)
        ooc_index = by_message(ooc)
        checks = [
            ("verified_count", lambda: self.assertEqual(len(rows), 620)),
            ("follow_count", lambda: self.assertEqual(len(follow), 12035)),
            ("no_avrae", lambda: self.assertTrue(all(r["link"] == "adjacency" for r in follow))),
            ("no_orpheus", lambda: self.assertTrue(all("orpheus" not in r["player_line"].lower() for r in rows))),
            ("no_discord_ping", lambda: self.assertTrue(all("<@" not in r["player_line"] + r["my_ruling"] for r in rows))),
            ("chadmarts_kept", lambda: self.assertTrue(any("Chadmarts" in r["source_line"] + r["my_ruling"] for r in follow))),
            ("bear_castor_kept", lambda: self.assertIn("BEAR CASTOR", index[JOKE_ID]["player_line"])),
            ("everyone_is_castor", lambda: self.assertTrue(any("Everyone is castor" in r["my_ruling"] for r in rows))),
            ("no_everyone_is_pc", lambda: self.assertTrue(all("Everyone is PC" not in r["player_line"] + r["my_ruling"] for r in rows))),
            ("no_at_kiln", lambda: self.assertTrue(all("@kiln" not in (r["source_line"] + r["my_ruling"]).lower() for r in follow))),
            ("no_at_gneiss", lambda: self.assertTrue(all("@gneiss" not in (r["source_line"] + r["my_ruling"]).lower() for r in follow))),
            ("no_at_dwendal", lambda: self.assertTrue(all("@dwendal" not in (r["source_line"] + r["my_ruling"]).lower() for r in follow))),
            ("no_chadowski", lambda: self.assertTrue(all("chadowski" not in (r["player_line"] + r["my_ruling"]).lower() for r in rows))),
            ("how_lucky_kept", lambda: self.assertTrue(any("How lucky!" in r["source_line"] for r in follow))),
            ("coils_arc_kept", lambda: self.assertTrue(any("coils arc" in r["my_ruling"] for r in follow))),
            ("ooc_not_just_let_it_happen", lambda: self.assertTrue(all(not r["my_ruling"].startswith("just let it happen;") for r in rows if r["intent"] == "ooc/meta"))),
            ("row226_ooc", lambda: self.assertEqual(index[ROW226_ID]["intent"], "ooc/meta")),
            ("row351_ooc", lambda: self.assertEqual(index[ROW351_ID]["intent"], "ooc/meta")),
            ("row361_ooc", lambda: self.assertEqual(index[ROW361_ID]["intent"], "ooc/meta")),
            ("row426_social", lambda: self.assertEqual(index[ROW426_ID]["intent"], "social/speech")),
            ("row476_ooc", lambda: self.assertEqual(ooc_index[ROW476_ID]["intent"], "ooc/meta")),
            ("row553_ooc", lambda: self.assertEqual(ooc_index[ROW553_ID]["intent"], "ooc/meta")),
            ("narration_prefix", lambda: self.assertTrue(index[NARRATION_ID]["my_ruling"].startswith("just let it happen;"))),
            ("table_id_ooc", lambda: self.assertEqual(index[TABLE_ID]["intent"], "ooc/meta")),
            ("numbered_pcs", lambda: self.assertEqual(index[NUMBERED_ID]["player_line"], "Sylric PC1 PC2 PC3 PC4 PC5 PC6")),
            ("notes_55", lambda: self.assertIn("55%", notes)),
            ("notes_not_only_castor", lambda: self.assertIn("not a claim that only the castor jokes remain", notes)),
            ("notes_avrae_dropped", lambda: self.assertIn("embed title", notes)),
            ("hold_action_moved", lambda: self.assertTrue(ooc_index[ROW553_ID]["player_line"].startswith("(Can I hold an action?)"))),
            ("forever_moved", lambda: self.assertTrue(ooc_index[ROW476_ID]["player_line"].startswith("(does that last forever?)"))),
        ]
        self.assertEqual(len(checks), 30)
        for name, fn in checks:
            with self.subTest(name):
                fn()


if __name__ == "__main__":
    unittest.main()

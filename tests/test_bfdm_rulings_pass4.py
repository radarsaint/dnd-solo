"""Pass 4 checks. These fail on ce28790 and pass after the fixture fix.

They do not load Kit and do not treat the fixture as doctrine.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rulings"
FIXTURE = ROOT / "bfdm_rulings.jsonl"
FOLLOW = ROOT / "bfdm_rulings_followup.jsonl"

# 1-indexed rows 227, 500, and 522 on ce28790.
ALSO_MOVE = (
    "735964040999862305",
    "738296479025725490",
    "739036043273043969",
)
# The roll-call line "PC1 IT PC2 PC3 PC4".
ROLL_CALL = "866252748714541076"

# Eighteen leading speaker labels on player lines at ce28790.
PREFIXES = (
    "PC1",
    "Action",
    "headcanon",
    "Summoner",
    "message",
    "pov",
    "BA",
    "Ba",
    "Reaction",
    "raven",
    "re",
    "Items",
    "gf",
    "Me",
    "Ps4",
    "Serious question",
    "Fun fact",
    "Full disclosure",
)
assert len(PREFIXES) == 18
PREFIX_RE = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in sorted(PREFIXES, key=len, reverse=True)) + r"):\s*"
)
PAREN_Q = re.compile(r"^\([^)\n]*\?[^)\n]*\)\s*$")
CASTORS = re.compile(r"(?i)\bcastors\b")
CASTPR = re.compile(r"(?i)\bcastpr\b")
CASTER = re.compile(r"(?i)\bcasters?\b")
CASTOR_WORD = re.compile(r"(?i)(?<![A-Za-z])castor(?![A-Za-z])")


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def message_id(row):
    return re.search(r"message (\d+)", row["note"]).group(1)


class TestBfdmRulingsPass4(unittest.TestCase):
    def test_no_castors_name_variants(self):
        """Every form of the Castor name is the spelling used in the set."""
        for path, fields in (
            (FIXTURE, ("player_line", "my_ruling")),
            (FOLLOW, ("source_line", "my_ruling")),
        ):
            for n, row in enumerate(load(path), 1):
                blob = " ".join(row.get(f) or "" for f in fields)
                self.assertNotRegex(blob, CASTORS, (path.name, n))
                self.assertNotRegex(blob, CASTPR, (path.name, n))
                if CASTOR_WORD.search(blob):
                    self.assertNotRegex(blob, CASTER, (path.name, n, blob[:160]))

    def test_roll_call_is_not_a_ruling(self):
        ids = {message_id(row) for row in load(FIXTURE)}
        self.assertNotIn(ROLL_CALL, ids)
        lines = [row["player_line"] for row in load(FIXTURE)]
        self.assertNotIn("PC1 IT PC2 PC3 PC4", lines)

    def test_parenthetical_questions_are_not_rulings(self):
        for n, row in enumerate(load(FIXTURE), 1):
            self.assertNotIn(message_id(row), ALSO_MOVE, n)
            self.assertNotRegex(row["player_line"].strip(), PAREN_Q, n)

    def test_no_speaker_prefixes_on_player_lines(self):
        for path, field in ((FIXTURE, "player_line"), (FOLLOW, "source_line")):
            for n, row in enumerate(load(path), 1):
                self.assertNotRegex(row[field].lstrip(), PREFIX_RE, (path.name, n, row[field][:80]))


if __name__ == "__main__":
    unittest.main()

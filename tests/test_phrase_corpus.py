"""Data-driven phrase corpus: every playtest phrasing that misrouted (/workspace/kit2
pr145-bugs.md, pr145*-log.md, pr150-log.md) plus paraphrases (other verbs, word order, speech
mixed with action, Avrae lines with words in front). Expected value is the resolution kind,
'kind/simple_act' for a declared simple act, or 'ruling' for Kit's call (PendingRuling).
Precedence between overlapping intents: docs/INTENT_PRECEDENCE.md. Watchroom, inside, dice pinned."""
import unittest

from runtime.kit_agent import PendingRuling
from test_kit_watchroom_stalls import Stalls

SIMPLE = 'observe/simple_act'
INSIDE = [
    # Simple acts (PR 145: refused as "needs the DM's call")
    ('I hold up a light at the doorway.', SIMPLE),
    ('I sweep the cobwebs off the table with my staff.', SIMPLE),
    ('I brush the dust off the chest.', SIMPLE),
    ('With my staff I wipe the cobwebs away from the table.', SIMPLE),
    ('I crouch by the table.', SIMPLE),
    ('I tap the chest with my staff.', SIMPLE),
    ('I knock on the chest twice.', SIMPLE),
    ('I walk over to the table.', SIMPLE),
    ('I step closer to the table.', SIMPLE),
    ('I raise my lantern and look in.', 'observe'),
    # Risky acts stay Kit's ruling
    ('I smash the chest.', 'ruling'),
    ('I break the chest open with my staff.', 'ruling'),
    # Search beats a simple act (#150 playtest: walk the wall ... search it for seams)
    ('I walk the wall and search it for seams.', 'ruling'),
    ('I pace along the wall, searching for seams.', 'ruling'),
    ('Walking the wall, I check it for hidden seams.', 'ruling'),
    ('I walk to the table and examine the ledger.', 'ruling'),
    ('I kneel and inspect the floor.', 'ruling'),
    ('I step over and check the chest for traps.', 'inspect_feature'),
    # Mixed talk + act + question keep the act (PR 145 bug 3)
    ('Matching set, never good. I back up to the door and look over the chest. Does it look trapped?', 'observe'),
    ('I look over the chest and the ledger. Do either look valuable?', 'observe'),
    ('Looks over the chest. Does it glow?', 'observe'),
    ('Hmm, okay. I look at the ledger. Anything written in it?', 'observe'),
    ('I tap the chest. Is it hollow?', SIMPLE),
    ('I knock on the table. Sturdy?', SIMPLE),
    # Check requests with an act beside them
    ('Hmm. I crouch by the table. Could I roll Perception?', 'check_request'),
    ('Can I make an Investigation check on the chest?', 'check_request'),
    # Spells out of combat, rituals (PR 145 bug 1)
    ('I cast Detect Magic as a ritual.', 'spell_cast'),
    ('I cast detect magic.', 'spell_cast'),
    ('Casting Detect Magic as a ritual, I wait ten minutes.', 'spell_cast'),
    ('I cast Light on my hat brim.', 'spell_cast'),
    # Speech stays speech
    ('Hello there, who are you?', 'social'),
    ('"Nice weather," I say.', 'social'),
    # Likeliest misfires of the #150 fixes, pinned before pushing
    ('I walk over and check on the warden.', SIMPLE),        # 'check on' someone is not a search
    ('I step back and check my pack.', SIMPLE),              # own gear is not a search
    ('I tap the wall, feeling for a hollow spot.', 'ruling'),  # feeling for = searching
    ('I cast detect magic on the chest.', 'spell_cast'),     # 'on the' is not an attack
    ('I cast detect magic. Anything?', 'spell_cast'),
    ('I cast Detect Magic as a ritual while we talk.', 'spell_cast'),
    # Known: waiting is read as a social beat (harmless: nothing is refused)
    ('Holding my torch up, I wait by the door.', 'social'),
]


def outcome(case, line):
    try:
        result = case.resolve(case.runtime, line)
    except PendingRuling:
        return 'ruling'
    simple = any('simple_act' in (e.get('tags') or ()) for e in result.events)
    return result.kind + ('/simple_act' if simple else '')


class Corpus(Stalls):
    def test_inside_the_watchroom(self):
        self.go_in()
        for line, expected in INSIDE:
            with self.subTest(line):
                self.assertEqual(outcome(self, line), expected)


class Precedence(Stalls):
    """One message per overlap in docs/INTENT_PRECEDENCE.md."""
    PAIRS = [
        ('check request > simple act', 'I kneel by the chest. Can I roll Investigation?', 'check_request'),
        ('search > simple act', 'I step along the wall and search for a draft.', 'ruling'),
        ('look > simple act', 'I crouch and look under the table.', 'observe'),
        ('spell > simple act', 'I kneel and cast detect magic.', 'spell_cast'),
        ('risky act > simple act', 'I walk over and smash the chest.', 'ruling'),
        ('simple act > speech', 'Right then. I tap the table with my staff.', SIMPLE),
    ]

    def test_overlaps_follow_the_documented_order(self):
        self.go_in()
        for label, line, expected in self.PAIRS:
            with self.subTest(label):
                self.assertEqual(outcome(self, line), expected)

    def test_the_order_is_documented(self):
        from pathlib import Path
        doc = (Path(__file__).parents[1] / 'docs/INTENT_PRECEDENCE.md').read_text(encoding='utf-8')
        self.assertIn('A search **always**', doc)


if __name__ == '__main__':
    unittest.main()

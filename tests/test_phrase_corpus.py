"""Data-driven phrase corpus: every playtest phrasing that misrouted (/workspace/kit2
pr145-bugs.md, pr145*-log.md, pr150-log.md, pr150b-log.md) plus paraphrases (other verbs, word
order, speech mixed with action, Avrae lines with words in front).

Every case runs end to end through KitChatBridge.prepare and asserts what the player gets:
CHECK (a check request Kit calls or declines), LOOK (free description), ACT (a simple act done
as declared), MOVE, SPELL, SPEECH, or REFUSED (the "needs the DM's call" refusal). Asserting the
intent label let a search that ended in a refusal pass (#150 retest). Precedence between
overlapping intents: docs/INTENT_PRECEDENCE.md. Watchroom, inside, dice pinned."""
import unittest

from runtime.kit_agent import PendingRuling
from test_kit_watchroom_stalls import Stalls

CHECK, LOOK, ACT, MOVE, SPELL, SPEECH, REFUSED, RULED = 'check', 'look', 'act', 'move', 'spell', 'speech', 'refused', 'ruled'
_KINDS = {'kit_ruling': RULED, 'check_request': CHECK, 'observe': LOOK, 'threshold_look': LOOK, 'inspect_feature': LOOK,
          'exit': MOVE, 'spell_cast': SPELL, 'social': SPEECH}

INSIDE = [
    # Simple acts (PR 145: refused as "needs the DM's call")
    ('I hold up a light at the doorway.', ACT),
    ('I sweep the cobwebs off the table with my staff.', ACT),
    ('I brush the dust off the chest.', ACT),
    ('With my staff I wipe the cobwebs away from the table.', ACT),
    ('I crouch by the table.', ACT),
    ('I tap the chest with my staff.', ACT),
    ('I knock on the chest twice.', ACT),
    ('I walk over to the table.', ACT),
    ('I step closer to the table.', ACT),
    ('I raise my lantern and look in.', LOOK),
    # A physical act on a thing in the room is an ordinary turn Kit rules, not a refusal
    # (#150 retest 2b); exploits and acts on a person stay refused
    ('I smash the chest.', RULED),
    ('I break the chest open with my staff.', RULED),
    ('I yank the lid of the chest.', 'physical_act'),     # the room file handles it (kit_acts)
    ('I pry at the floorboards with my dagger.', RULED),
    ('I wedge my dagger under the table leg.', RULED),
    ('I pour water over the ledger.', RULED),
    ('I steal everything in the room.', REFUSED),            # exploit
    ('I instantly open every lock.', REFUSED),               # exploit
    ("I steal the warden's keys.", REFUSED),                # a person's things: refused
    # Kit II #150 retest 2 lines (from the Old Gate room), as watchroom paraphrases
    ('I run my fingers along the mortar lines, hunting for a hidden catch.', CHECK),
    ('I run my hands over the table, hunting for a hidden drawer.', CHECK),
    ('I go over the west wall inch by inch for anything odd.', CHECK),
    ('I go over the chest carefully.', CHECK),
    ('I poke around in the cobwebs with my staff.', CHECK),
    ('I poke around under the table.', CHECK),
    ('I study the ledger closely.', CHECK),
    ('I study the writing on the wall.', CHECK),
    ('I sift through the ashes in the corner.', CHECK),
    ('Sifting through the dust, I look for anything dropped.', CHECK),
    ('I look behind the table.', CHECK),
    ('I peer under the chest.', CHECK),                      # a search on a handled (trapped) feature: a check
    ('I comb through the papers on the table.', CHECK),
    ('I rifle through the drawers.', CHECK),
    ('I scrutinise the floorboards.', CHECK),
    # Kit II retest 3: an act after 'wait' is an act, not talk
    ('Wait, before I roll, I yank the manacles off the wall.', RULED),
    ('Wait. I pull the torch out of its bracket.', RULED),
    ('Hold on, I kick the chest.', RULED),
    # Search beats a simple act and reaches a called check (#150 playtest; #150 retest: these
    # were refused, and the corpus pinned the refusal because it asserted labels, not outcomes)
    ('I walk along the north wall, checking each mirror frame for seams.', CHECK),
    ('I walk the north wall checking frames.', CHECK),
    ('I pace along the wall, feeling along the stone for any gaps.', CHECK),
    ('I pace, feeling for gaps.', CHECK),
    ("I step up to each niche and examine the mirrors.", CHECK),
    ("I examine each niche's mirrors.", CHECK),
    ('Along the wall I go, searching every stone for a seam.', CHECK),
    ('I run my hands over the wall looking for a catch.', CHECK),
    ('I check behind the table.', CHECK),  # was a free look; behind something is a search now
    ('I walk the wall and search it for seams.', CHECK),
    ('I pace along the wall, searching for seams.', CHECK),
    ('Walking the wall, I check it for hidden seams.', CHECK),
    ('I walk to the table and examine the ledger.', CHECK),
    ('I kneel and inspect the floor.', CHECK),
    ('I step over and check the chest for traps.', CHECK),
    # Mixed talk + act + question keep the act (PR 145 bug 3)
    ('Matching set, never good. I back up to the door and look over the chest. Does it look trapped?', LOOK),
    ('I look over the chest and the ledger. Do either look valuable?', LOOK),
    ('Looks over the chest. Does it glow?', LOOK),
    ('Hmm, okay. I look at the ledger. Anything written in it?', LOOK),
    ('I tap the chest. Is it hollow?', ACT),
    ('I knock on the table. Sturdy?', ACT),
    # Check requests with an act beside them
    ('Hmm. I crouch by the table. Could I roll Perception?', CHECK),
    ('Can I make an Investigation check on the chest?', CHECK),
    # Spells out of combat, rituals (PR 145 bug 1)
    ('I cast Detect Magic as a ritual.', SPELL),
    ('I cast detect magic.', SPELL),
    ('Casting Detect Magic as a ritual, I wait ten minutes.', SPELL),
    ('I cast Light on my hat brim.', SPELL),
    # Speech stays speech
    ('Hello there, who are you?', SPEECH),
    ('"Nice weather," I say.', SPEECH),
    # Likeliest misfires of the #150 fixes, pinned before pushing
    ('I walk over and check on the warden.', ACT),        # 'check on' someone is not a search
    ('I step back and check my pack.', ACT),              # own gear is not a search
    ('I tap the wall, feeling for a hollow spot.', CHECK),  # feeling for = searching
    ('I cast detect magic on the chest.', SPELL),     # 'on the' is not an attack
    ('I cast detect magic. Anything?', SPELL),
    ('I cast Detect Magic as a ritual while we talk.', SPELL),
    # Misfires of the search route, pinned: none of these is a search
    ('I walk over and check on the warden.', ACT),
    ('I walk the length of the room.', ACT),
    # Known: waiting is read as a social beat (harmless: nothing is refused)
    ('Holding my torch up, I wait by the door.', LOOK),  # a position at the door (was a social beat on #150)
    # Backing up to a doorway is a position, not leaving (stacked PR, item 3) + misfires
    ('I step back to the door and look over the chest.', LOOK),
    ('I back up to the doorway and look around.', LOOK),
    ('I back up to the door.', LOOK),
    ('I step back to the door and listen.', LOOK),
    ('I step back to the door and go out.', MOVE),            # misfire: leaving still leaves
    ('I go out through the iron door.', MOVE),                # misfire: a plain exit
    ('I look at the doorway.', LOOK),                         # misfire: no position from a look
]


# From the landing: entering with an act keeps the act; 'not going in yet' is a look (item 2)
LANDING = [
    ("I'm not going in yet, just peeking through the door.", LOOK),
    ("I don't go in yet; I listen at the door.", LOOK),
    ('Not stepping in, I peek through the keyhole.', LOOK),
    ('I go through the iron door and look around.', MOVE),
    ('I go in and knock on the chest.', MOVE),
    ('I step through the iron door and search the chest.', LOOK),
    # Misfires pinned: a real entry with 'not' elsewhere, and a peek with no negation
    ("I go through the iron door, not waiting any longer.", MOVE),
    ('I peek through the gap in the door.', LOOK),
]


def outcome(case, line, turn='c'):
    """The end-to-end outcome of one player message: prepared (and what for), or refused."""
    try:
        packet = case.bridge.prepare(line, turn, one_pass=True)
    except PendingRuling:
        return REFUSED
    public = packet['input']['public']
    if public['accepted_public_event'].startswith('You go ahead: '):
        return ACT
    return _KINDS.get(public['action_kind'], public['action_kind'])


class Corpus(Stalls):
    def test_inside_the_watchroom(self):
        self.go_in()
        for i, (line, expected) in enumerate(INSIDE):
            with self.subTest(line):
                self.assertEqual(outcome(self, line, f'c{i}'), expected)


class LandingCorpus(Stalls):
    def test_from_the_landing(self):
        for i, (line, expected) in enumerate(LANDING):
            with self.subTest(line):
                self.assertEqual(outcome(self, line, f'l{i}'), expected)


class Precedence(Stalls):
    """One message per overlap in docs/INTENT_PRECEDENCE.md."""
    PAIRS = [
        ('check request > simple act', 'I kneel by the chest. Can I roll Investigation?', CHECK),
        ('search > simple act', 'I step along the wall and search for a draft.', CHECK),
        ('search (look under) > simple act', 'I crouch and look under the table.', CHECK),
        ('spell > simple act', 'I kneel and cast detect magic.', SPELL),
        ('risky act > simple act', 'I walk over and smash the chest.', RULED),
        ('simple act > speech', 'Right then. I tap the table with my staff.', ACT),
    ]

    def test_overlaps_follow_the_documented_order(self):
        self.go_in()
        for i, (label, line, expected) in enumerate(self.PAIRS):
            with self.subTest(label):
                self.assertEqual(outcome(self, line, f'p{i}'), expected)

    def test_the_order_is_documented(self):
        from pathlib import Path
        doc = (Path(__file__).parents[1] / 'docs/INTENT_PRECEDENCE.md').read_text(encoding='utf-8')
        self.assertIn('**whole sentence**', doc)
        self.assertIn("Kit's ruling as an ordinary turn", doc)
        self.assertIn('never refused', doc)


if __name__ == '__main__':
    unittest.main()

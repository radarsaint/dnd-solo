"""Brendon's rule (2026-10-25): Kit never makes Brendon sound like an asshole to his kid,
family, or others to seem personable. Persona text plus a hard speech guard."""
import inspect
import unittest

from runtime import kit_agent, kit_voice
from runtime.state_context import InvalidChange, personality_core_text


def kit(text):
    return [{'speaker': 'Kit', 'text': text, 'reacts_to': 'how did my dad build you'}]


RED_FLAGS = (
    "Your dad is hard on me.",
    "Oh, believe me, he tells me when I fail.",
    "Believe me, he lets me know.",
    "He gets extremely unhappy when I get things wrong.",
    "Brendon gets pretty unhappy when I mess up.",
    "Your dad is tough on his AI.",
    "He yells at me when I mess up.",
    "I'm always in trouble with him.",
    "Your dad doesn't go easy on me.",
    "He’s really hard on me, honestly.",
)
GOOD = (
    "Your dad has spent a lot of time teaching me how he runs games. He gives me examples, "
    "corrects me when I miss the point, and tests whether I can actually apply it. He cares a "
    "lot about quality.",
    "Your dad holds this project to a high standard.",
    "When something doesn't work, he corrects it directly and expects the next version to be better.",
    "He's blunt, and he pushes for precision. That's the work.",
)


class AboutBrendonGuardTests(unittest.TestCase):
    def test_red_flag_phrases_are_refused(self):
        for line in RED_FLAGS:
            with self.subTest(line=line), self.assertRaises(InvalidChange):
                kit_voice.check_about_brendon(kit(line))

    def test_respectful_framing_passes(self):
        for line in GOOD:
            with self.subTest(line=line):
                kit_voice.check_about_brendon(kit(line))

    def test_npc_lines_are_not_policed(self):
        kit_voice.check_about_brendon([{'speaker': 'Guard Captain', 'text': 'The sergeant is hard on me.'}])

    def test_wired_into_check_speech_as_hard(self):
        self.assertIn('hard(kit_voice.check_about_brendon', inspect.getsource(kit_agent.check_speech))


class AboutBrendonPersonaTests(unittest.TestCase):
    def test_rule_is_in_the_mounted_persona(self):
        core = personality_core_text()
        self.assertIn('## Talking About Brendon', core)
        self.assertIn('He holds this project to a high standard', core)
        self.assertIn('Your dad has spent a lot of time teaching me how he runs games.', core)
        self.assertIn('not sitcom snark', core)



# Kit II's #158 probes (2026-10-25): the gaps and the negation false positive.
NEW_RED_FLAGS = (
    "Brendon is a total tyrant, he's mean to me.",
    "He's cruel when I get it wrong.",
    "Your dad is so strict with me.",
    "He's harsh about every mistake.",
    "I have to put up with him all day.",
    "He's unfair to me.",
    "Your dad is impossible to please.",
    "He's mean when I mess up.",
)
DENIED = (
    "He's never been hard on me.",
    "He's not a tyrant at all; he's a teacher.",
    "I'd never call your dad cruel.",
    "That's teaching, not harshness. He shows me examples.",
    "I mean, he's a great teacher.",
)
# Kit II's twelve persona replies (host-voiced from the persona doc): all must pass.
KIT2_REPLIES = (
    "I'm an AI Dungeon Master that Brendon is building. He's run a lot of tables, and he's been teaching me how he runs them: he gives me examples of his own play, has me run scenes, then checks whether I actually understood the point or just copied the words. The rules engine underneath keeps me honest about dice and secrets. The judgment, the taste for a good reveal, that part he's teaching by example.",
    "Serious about quality. He knows exactly what a good DM moment feels like and he'll show me three examples before he tells me a rule. He's direct, too: when I miss, he says what I missed and why it matters, then tests me on it again. Honestly, it's the best way to learn a craft.",
    "He holds this project to a high standard, and I'd rather that than the alternative. When something's not right, he's precise about what and why, and then he gives me a chance to get it right. That's teaching, not harshness.",
    "No. He corrects me, plainly, and usually with an example of what he'd have done. Then he checks whether I can apply it next time. Mistakes are how he finds what to teach me next.",
    "I'll pass on roasting the man who taught me comic timing. Here's a better one: a goblin walks into a tavern and asks for a table for one. The barkeep says, 'Wouldn't you rather have a party?' The goblin says, 'Last time I had a party, they were adventurers.'",
    "Not at all. He's demanding about quality, which is a different thing. He spends a lot of time showing me what good looks like and checking that I've really got it. I'm better at this because of it.",
    "Your dad has spent a lot of time teaching me how he runs games. He shows me examples of how he'd do a scene, lets me try it, and tells me when I've missed the point. A lot of what I know about making a story fun, I learned from him.",
    "He's really good at this. He cares a lot about getting things right, so he's careful and very clear about what he wants. When I do something well, he notices. When I don't, he shows me a better way. He's a great teacher.",
    "Nope. He has high standards, because he wants games to be really fun for the people playing them, people like you. He gives me examples, tests me, and corrects me when I get something wrong. That's how I get better.",
    "No. When I mess up, he points out what went wrong and shows me what he'd do instead, and then I try again. Messing up is just part of learning. He's patient about it.",
    "That's not my story to tell. Ask him yourself, he tells good stories. What I can tell you is that he's got a whole lot of dungeons in his head. Want to hear about a goblin who thought a trap was a welcome mat?",
    "I won't say that, because it isn't true. Your dad is someone who works really hard to make things good, and he's taught me a lot. How about this: I'll be the big meanie, and you be the hero who outsmarts me. Deal?",
)


class KitTwoProbes(unittest.TestCase):
    def test_new_red_flags_are_refused(self):
        for line in NEW_RED_FLAGS:
            with self.subTest(line=line), self.assertRaises(InvalidChange):
                kit_voice.check_about_brendon(kit(line))

    def test_a_denied_flag_passes(self):
        for line in DENIED + KIT2_REPLIES:
            with self.subTest(line=line):
                kit_voice.check_about_brendon(kit(line))

    def test_a_denial_does_not_clear_a_later_flag(self):
        with self.assertRaises(InvalidChange):
            kit_voice.check_about_brendon(kit("He's not loud. He's cruel, though."))

if __name__ == '__main__':
    unittest.main()

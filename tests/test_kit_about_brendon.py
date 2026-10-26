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


if __name__ == '__main__':
    unittest.main()

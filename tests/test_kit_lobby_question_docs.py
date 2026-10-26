"""The lobby_question field and --question-delivered flag are documented, and the Custom GPT
instructions block stays under the 8,000-character paste limit."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LobbyQuestionDocsTests(unittest.TestCase):
    def test_documented(self):
        for doc in ('AGENTS.md', 'docs/CUSTOM_GPT_SETUP.md', 'docs/architecture/LOBBY_QUESTIONS.md'):
            body = (ROOT / doc).read_text(encoding='utf-8')
            self.assertIn('lobby_question', body, doc)
            self.assertIn('--question-delivered', body, doc)

    def test_gpt_instructions_under_limit(self):
        text = (ROOT / 'docs/CUSTOM_GPT_SETUP.md').read_text(encoding='utf-8')
        start = text.index('```', text.index('## 3.')) + 3
        self.assertLess(len(text[start:text.index('```', start)]), 8000)


if __name__ == '__main__':
    unittest.main()

"""Persona-continuity H4: the runtime spec points at the real personality core and does not
tie Kit's existence to a play session; the README does not say Kit exists only through the
bridge (docs PR #60, C11/C14)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / 'docs/architecture/runtime/DND_SOLO_RUNTIME.md'


class PersonaDocsTests(unittest.TestCase):
    def test_the_runtime_spec_links_resolve_and_load_the_core_in_every_conversation(self):
        text = SPEC.read_text(encoding='utf-8')
        section = text[text.index('### 5.7 DM personality retrieval'):]
        section = section[:section.index('\n---')]
        links = re.findall(r'\]\(([^)]+\.md)\)', section)
        self.assertTrue(links)
        for link in links:
            self.assertTrue((SPEC.parent / link).resolve().is_file(), link)
        self.assertNotIn('/Dnd solo/Runtime/', section)
        self.assertNotIn('at play-session activation', section)
        self.assertIn('every Kit conversation', section)

    def test_the_readme_does_not_say_kit_exists_only_through_the_bridge(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertNotIn('played only through the chat bridge', readme)
        self.assertIn('only when a game turn is in play', readme)


if __name__ == '__main__':
    unittest.main()

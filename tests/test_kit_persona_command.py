"""`python3 -m runtime.kit_agent persona` (persona-continuity R2): the persona text the bridge
uses, plus any voice warning and the authority note, with no database and no scene."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent
from runtime.state_context import personality_core_text

ROOT = Path(__file__).resolve().parent.parent


class PersonaCommandTests(unittest.TestCase):
    def test_persona_prints_the_bridge_core_and_touches_no_database(self):
        with tempfile.TemporaryDirectory() as temp:
            # Run from an empty folder: the default --db would be created there if it were opened.
            env = {**os.environ, 'PYTHONPATH': str(ROOT)}
            out = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'persona'], cwd=temp,
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, kit_agent.persona_text())
            self.assertTrue(out.stdout.startswith(personality_core_text().rstrip('\n')))
            self.assertTrue(out.stdout.rstrip('\n').endswith(kit_agent.PERSONA_AUTHORITY_NOTE))
            self.assertEqual(os.listdir(temp), [], 'persona opens no database')
        # A voice folder over the cap: the warning is printed with the persona.
        with tempfile.TemporaryDirectory() as voice:
            Path(voice, 'a.md').write_text('word ' * 2000)
            Path(voice, 'b.md').write_text('word ' * 2000)
            text = kit_agent.persona_text(voice)
            self.assertIn('Voice warning: Voice files over the', text)
            self.assertIn('b.md', text)


if __name__ == '__main__':
    unittest.main()

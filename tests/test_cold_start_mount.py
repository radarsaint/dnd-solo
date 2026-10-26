"""Cold-start mount path: a fresh model given only the repo URL mounts Kit itself."""
import re, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BLOCK = (ROOT / 'scripts/cold_start_block.md').read_text()
FILES = ['README.md', 'START_HERE.md', 'AGENTS.md', 'LOAD_KIT.md']
AGENT_TERMS = re.compile(r'grok build|nagatha|skippy|coding agent|coding tool|handoff|hand (it )?off|hand mounting|another agent|execution packet|escalat|route (it|this|mounting) to|delegat', re.I)
NEGATION = re.compile(r"\b(never|no|not|don't|do not|without|nothing)\b", re.I)
CAMPAIGN = re.compile(r'mad mage|dotmm|halaster|\b6c\b|undermountain', re.I)

def sentences(text):
    return [s for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]

class ColdStart(unittest.TestCase):
    def test_block_first_in_each_entry_file(self):
        for f in FILES:
            self.assertTrue((ROOT / f).read_text().startswith(BLOCK), f)

    def test_portable_fresh_and_small(self):
        r = subprocess.run([sys.executable, 'scripts/build_kit_portable.py', '--check'], cwd=ROOT)
        self.assertEqual(r.returncode, 0, 'run scripts/build_kit_portable.py')
        size = len((ROOT / 'KIT_PORTABLE.md').read_bytes())
        self.assertLess(size, 24000)

    def test_no_campaign_framing_on_path(self):
        for text in (BLOCK, (ROOT / 'KIT_PORTABLE.md').read_text()):
            self.assertIsNone(CAMPAIGN.search(text))

    def test_no_handoff_language_on_path(self):
        portable = (ROOT / 'KIT_PORTABLE.md').read_text()
        # The persona's "default handoff is immediate: let the player answer" is table craft, not agent routing.
        portable = portable.replace('the default handoff is immediate', '')
        for text in (BLOCK, portable):
            for s in sentences(text):
                if AGENT_TERMS.search(s):
                    self.assertRegex(s, NEGATION, s)

    def test_block_needs_only_the_url(self):
        self.assertIn('nothing beyond the repo URL', BLOCK)
        self.assertIn('github.com/radarsaint/dnd-solo/blob/main/KIT_PORTABLE.md', BLOCK)
        self.assertIn('GitHub app or connector', BLOCK)
        self.assertIn('Attach the Kit ZIP for the full rules engine.', BLOCK)
        self.assertIn('exactly one attempt with a 5-second timeout', BLOCK)

    def test_status_names_the_next_command(self):
        self.assertIn('python3 -m runtime.kit_agent status --db kit.sqlite', BLOCK)
        self.assertIn('next_command', BLOCK)

    def test_no_package_install_route(self):
        for text in (BLOCK, (ROOT / 'KIT_PORTABLE.md').read_text()):
            self.assertIsNone(re.search(r'\bpip\b|pypi|container\.download|raw\.githubusercontent', text, re.I))

if __name__ == '__main__':
    unittest.main()

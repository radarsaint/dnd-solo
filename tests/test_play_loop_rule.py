"""Hosts never read runtime source during play; the documented loop is exact and real."""
import re, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BLOCK = (ROOT / 'scripts/play_loop_block.md').read_text()

def gpt_instructions():
    t = (ROOT / 'docs/CUSTOM_GPT_SETUP.md').read_text()
    return t.split('```text', 1)[1].split('```', 1)[0]

class PlayLoopRule(unittest.TestCase):
    def test_block_near_top_of_host_docs(self):
        for f in ('AGENTS.md', 'LOAD_KIT.md'):
            t = (ROOT / f).read_text()
            i = t.index(BLOCK)
            self.assertLess(i, t.index('<!-- END COLD-START MOUNT BLOCK -->') + 100, f)

    def test_host_context_carries_agents(self):
        src = (ROOT / 'scripts/kit_host.py').read_text()
        self.assertIn("(root / 'AGENTS.md').read_text", src)

    def test_gpt_instructions(self):
        t = gpt_instructions()
        self.assertLess(len(t), 8000)
        self.assertLess(t.index('PLAY LOOP (hard rule)'), t.index('LOAD ('))
        self.assertIn('never open or inspect runtime source', t)
        self.assertIn('--input-file o.json', t)
        self.assertIn('Party companions are not supported yet', t)

    def test_portable_rules(self):
        t = (ROOT / 'KIT_PORTABLE.md').read_text()
        self.assertIn('Party companions aren\'t supported yet', t)
        self.assertIn("Don't write code or build an engine", t)
        self.assertIn('only from adventure text the player actually pastes or uploads', t)
        self.assertIn('Never invent rooms, NPCs or stat blocks', t)
        self.assertIn('never improvise rooms', t)
        self.assertNotIn('your own knowledge of the rules', t)

    def test_documented_flags_exist(self):
        h = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', '--help'], cwd=ROOT,
                           capture_output=True, text=True).stdout
        for flag in re.findall(r'--[a-z][a-z-]+', BLOCK):
            self.assertIn(flag, h, flag)

if __name__ == '__main__':
    unittest.main()

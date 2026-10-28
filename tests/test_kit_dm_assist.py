"""DM-assist rules are in the persona a host reads, and on the mount path."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PHRASES = (
    'DM-assist',
    'Players waiting, a roll just happened, an NPC being questioned, or an action declared',
    'next 30 seconds',
    'A full module, table, or handout is still complete.',
    'the DM can decide',
    'specific people, objects, and places',
    'what the players can gain, lose, or change',
    'Quest-linked entries are a minority',
    'stay interesting if the quest is removed',
    'appearance, NPC behavior, danger, scale, social response, or pacing',
    'playable procedures and correct mechanics come before maps and art',
    'A map must match the written geometry.',
    'stay PROPOSED until the DM uses or adopts them',
    'CONFIRMED, PROPOSED, RESOLVED_IN_PLAY, or UNKNOWN',
)
CAMPAIGN = re.compile(r'earthfall|mad mage|dotmm|halaster|\b6c\b|undermountain', re.I)


def section(text):
    text = text.replace('### DM-assist', '## DM-assist')
    start = text.index('## DM-assist')
    rest = text[start + len('## DM-assist'):]
    nxt = re.search(r'\n#{2,3} ', rest)
    return text[start:start + len('## DM-assist') + (nxt.start() if nxt else len(rest))]


class DMAssistMount(unittest.TestCase):
    def test_rules_are_reachable_from_the_mount_path(self):
        start = (ROOT / 'START_HERE.md').read_text(encoding='utf-8')
        load = (ROOT / 'LOAD_KIT.md').read_text(encoding='utf-8')
        agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        core = (ROOT / 'docs' / 'personality' / 'dm-personality-core.md').read_text(encoding='utf-8')
        portable = (ROOT / 'KIT_PORTABLE.md').read_text(encoding='utf-8')
        block = (ROOT / 'scripts' / 'cold_start_block.md').read_text(encoding='utf-8')
        self.assertIn('AGENTS.md', start)
        self.assertIn('docs/personality/dm-personality-core.md', start)
        self.assertIn('dm-personality-core.md', load)
        self.assertIn('AGENTS.md', load)
        self.assertIn('KIT_PORTABLE.md', block)
        for phrase in PHRASES:
            self.assertIn(phrase, core, phrase)
            self.assertIn(phrase, agents, phrase)
            self.assertIn(phrase, portable, phrase)
        self.assertIn('python3 -m runtime.kit_canon', agents)
        self.assertIn('supersede', agents)
        for text in (section(core), section(agents), section(portable.replace('### DM-assist', '## DM-assist'))):
            self.assertIsNone(CAMPAIGN.search(text), text[:80])


if __name__ == '__main__':
    unittest.main()

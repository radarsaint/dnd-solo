"""v0.11.7: start takes a PDF sheet and never half-mounts, start finds the room under the
save's own folder, and a what-do-I-know question calls a knowledge skill.

Synthetic book and sheet only. No published adventure text.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_perform, kit_prep, kit_skim
from runtime.state_context import Runtime
from tests import sheet_pdf

from test_kit_adventure_pdf import make_pdf
from test_kit_scene_contract_gpt import ENCOUNTER, FICTION, SCENE
from test_kit_turn_spine import CONDITION

ROOT = Path(__file__).resolve().parents[1]


def cli(cwd, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    done = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *map(str, args)], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60, env=env)
    text = done.stdout or done.stderr
    return done.returncode, json.loads(text[text.index('{'):])


class StartFromAPdfSheet(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.root), True)
        pdf = self.root / 'book.pdf'
        pdf.write_bytes(make_pdf([
            [('text', 70, 735, '1. The Road', 11), ('text', 70, 700, FICTION, 9), ('text', 70, 660, ENCOUNTER, 9),
             ('text', 70, 620, CONDITION, 9)],
            [('text', 70, 735, '2. The Tower', 11), ('text', 70, 700, 'A bell rings at a distant tower.', 9)]]))
        # A save in a subfolder, prepared from the repo root (the host's working folder).
        self.db = self.root / 'play' / 'kit.sqlite'
        self.db.parent.mkdir()
        kit_prep.prepare(str(self.db), str(pdf), reader='pdftotext', root=str(self.root / 'cache'))
        scene = copy.deepcopy(SCENE)
        scene['pressures'][0].update(quote=CONDITION, status='conditional', activation='failed_notice')
        kit_skim.accept(self.db, {'burst': FICTION, 'source_quote': FICTION, 'page_start': 1, 'page_end': 1,
                                  'alt_starts': [], 'design_start_name': 'The Road', 'scene': scene})
        # The room as a host running from its own folder recorded it: relative to that folder.
        data = kit_skim._read(self.db)
        room = Path(data['room'])
        data['room'] = str(Path('kit.sqlite.adventure') / room.relative_to(room.parents[len(room.parents) - 1])
                           if not room.is_absolute() else Path(*room.parts[room.parts.index('kit.sqlite.adventure'):]))
        kit_skim._write(self.db, data)
        self.sheet = self.root / 'hero.pdf'
        self.sheet.write_bytes(sheet_pdf.build())

    def test_pdf_sheet_starts_with_the_ready_line_from_any_folder(self):
        code, started = cli(self.root, 'start', '--db', 'play/kit.sqlite', '--sheet', self.sheet)
        self.assertEqual(code, 0, started)
        self.assertTrue(started.get('awaiting_yes'), started)
        self.assertEqual(started['table_line'], kit_skim.READY_LINE)

    def test_an_unreadable_sheet_writes_nothing_and_start_works_after(self):
        bad = self.root / 'bad.pdf'
        bad.write_bytes(b'%PDF-1.4 not a sheet')
        code, refused = cli(self.root, 'start', '--db', 'play/kit.sqlite', '--sheet', bad)
        self.assertNotEqual(code, 0, refused)
        self.assertIn('Nothing was started', refused['message'])
        runtime = Runtime(str(self.db))
        try:
            self.assertIsNone(runtime.db.execute('SELECT 1 FROM source').fetchone())
        finally:
            runtime.close()
        code, started = cli(self.root, 'start', '--db', 'play/kit.sqlite', '--sheet', self.sheet)
        self.assertEqual(code, 0, started)
        self.assertTrue(started.get('awaiting_yes'), started)


class KnowledgeQuestionsCallAKnowledgeSkill(unittest.TestCase):
    def test_lore_questions(self):
        for line, skill in (('What do I know about goblins raiding this road?', 'history'),
                            ('What do I recall about the fallen kingdom here?', 'history'),
                            ("What do I know about the wizard's wards?", 'arcana'),
                            ('Do I know anything about the temple of the sun god?', 'religion'),
                            ('What do I remember about wolves in these hills?', 'nature')):
            self.assertEqual(kit_perform.knowledge_skill(line), skill, line)

    def test_investigation_stays_the_fallback(self):
        self.assertEqual(kit_perform.knowledge_skill('I search the desk for a hidden drawer.'), 'investigation')


if __name__ == '__main__':
    unittest.main()

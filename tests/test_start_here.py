"""START_HERE.md maps the ZIP for any GPT reader. These checks keep the map from rotting:
every listed path exists, every file the engine loads by path is on the load-at-table or
runtime-fixtures list, every dev-only folder carries its README_FOR_GPT.md, and AGENTS.md and
README.md point at START_HERE.md from their first line."""
import re
import unittest
from pathlib import Path

from runtime import kit_agent, kit_prices, kit_texture, state_context

ROOT = Path(__file__).resolve().parent.parent
START = ROOT / 'START_HERE.md'
PATH = re.compile(r'`([A-Za-z0-9_.*/-]+(?:/|\.(?:md|json|py)))`')
DEV_FOLDERS = ('corpus', 'tests', 'docs/campaign', 'docs/architecture', 'docs/collab', 'scripts')


def block(name):
    text = START.read_text(encoding='utf-8')
    begin, end = f'<!-- {name}:begin -->', f'<!-- {name}:end -->'
    return text[text.index(begin) + len(begin):text.index(end)]


def paths(name):
    return PATH.findall(block(name))


class StartHereTests(unittest.TestCase):
    def test_every_listed_path_exists(self):
        for name in ('load-at-table', 'runtime-fixtures', 'reference', 'dev-only'):
            listed = paths(name)
            self.assertTrue(listed, name)
            for path in listed:
                if '*' in path:
                    self.assertTrue(list(ROOT.glob(path)), f'{name}: {path} matches nothing')
                else:
                    self.assertTrue((ROOT / path).exists(), f'{name}: {path} is missing')

    def test_files_the_engine_loads_by_path_are_listed(self):
        table = set(paths('load-at-table'))
        fixtures = set(paths('runtime-fixtures'))

        def covered(target, listed):
            rel = Path(target).resolve().relative_to(ROOT).as_posix()
            return any(rel == p or (('*' in p) and Path(rel).match(p)) or (p.endswith('/') and rel.startswith(p))
                       for p in listed)

        for target in (state_context.PERSONALITY_CORE, kit_texture.TASTE_FILE, kit_prices.SRD_FILE,
                       Path(kit_agent.__file__)):
            self.assertTrue(covered(target, table), target)
        for voice in state_context.voice_files():
            self.assertTrue(covered(voice, table), voice)
        for target in (kit_agent.DEFAULT_ROOM, kit_agent.EXAMPLE_SHEET):
            self.assertTrue(covered(target, fixtures), target)
        self.assertTrue(all(p.startswith('tests/') for p in fixtures), fixtures)

    def test_dev_only_folders_say_not_for_play(self):
        for folder in DEV_FOLDERS:
            note = ROOT / folder / 'README_FOR_GPT.md'
            self.assertTrue(note.is_file(), note)
            self.assertIn('not for play', note.read_text(encoding='utf-8').lower(), note)
            self.assertIn(f'`{folder}/`', block('dev-only'), folder)

    def test_tests_note_names_the_runtime_fixtures(self):
        note = (ROOT / 'tests/README_FOR_GPT.md').read_text(encoding='utf-8')
        for path in paths('runtime-fixtures'):
            self.assertIn(path.removeprefix('tests/'), note, path)

    def test_agents_and_readme_point_here_first(self):
        for doc in ('AGENTS.md', 'README.md'):
            first = (ROOT / doc).read_text(encoding='utf-8').splitlines()[0]
            self.assertIn('(START_HERE.md)', first, doc)


if __name__ == '__main__':
    unittest.main()

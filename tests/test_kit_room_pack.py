"""A private rooms pack (a ZIP or folder the host attaches) mounts with plain python3 on any host.

Rooms adapted from the published adventure can't go in this public repo. A host attaches them as a
pack instead: a folder or ZIP with a `manifest.json` (schema `kit-rooms-pack/v1`) that names its
`first_room` and lists its `rooms`. Everything here is synthetic: the pack is built at test time
from the repo's synthetic fixture rooms.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent, kit_pack, kit_rooms
from runtime.state_context import PROJECT_ROOT, Runtime

ROOT = PROJECT_ROOT
FIXTURES = ROOT / 'tests/fixtures/rooms'
NIK = 'tests/fixtures/characters/nik.json'


def _room(name, **changes):
    body = json.loads((FIXTURES / name).read_text(encoding='utf-8'))
    body.pop('fixture_only', None)  # a pack room is a playable room, not an engineering fixture
    body.update(changes)
    return body


def build_pack(where, name='kit-rooms', link=None):
    """A synthetic pack in the real pack's layout: <name>/manifest.json and <name>/rooms/*.json."""
    root = Path(where) / name
    (root / 'rooms').mkdir(parents=True)
    watch = _room('watchroom.json', id='synthetic-pack-watchroom')
    if link is not None:
        watch['areas']['stair_down']['room_link'] = {'room': link, 'area': 'kiln'}
    kiln = _room('kiln.json', id='synthetic-pack-kiln')
    (root / 'rooms/watchroom.json').write_text(json.dumps(watch), encoding='utf-8')
    (root / 'rooms/kiln.json').write_text(json.dumps(kiln), encoding='utf-8')
    manifest = {
        'schema': 'kit-rooms-pack/v1',
        'pack': name,
        'private': True,
        'first_room': 'rooms/watchroom.json',
        'rooms': [
            {'path': 'rooms/watchroom.json', 'room_id': 'synthetic-pack-watchroom', 'kind': 'social'},
            {'path': 'rooms/kiln.json', 'room_id': 'synthetic-pack-kiln', 'kind': 'hazard'},
        ],
    }
    (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root


def zip_pack(folder, target):
    with zipfile.ZipFile(target, 'w') as zf:
        for path in sorted(Path(folder).rglob('*')):
            zf.write(path, path.relative_to(Path(folder).parent).as_posix())
    return Path(target)


def _cli(argv, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        stack.enter_context(patch.object(sys, 'argv', ['kit_agent'] + argv))
        if cwd is not None:
            stack.enter_context(patch.object(kit_pack, 'search_dirs', lambda: [Path(cwd)]))
        code = kit_agent.main()
    text = out.getvalue() if code == 0 else err.getvalue()
    return code, json.loads(text)


class RoomPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = str(self.dir / 'kit.sqlite')
        self.empty = self.dir / 'nothing-here'
        self.empty.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_pack_folder_mounts_its_first_room(self):
        pack = build_pack(self.dir)
        code, out = _cli(['start', '--db', self.db, '--pack', str(pack), '--sheet', NIK], cwd=self.empty)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'started')
        self.assertEqual(out['room_id'], 'synthetic-pack-watchroom')
        self.assertEqual(out['pack']['pack'], 'kit-rooms')
        self.assertEqual(out['character']['name'], 'Nik')

    def test_explicit_pack_zip_mounts_and_a_named_room_is_found_by_id(self):
        zpath = zip_pack(build_pack(self.dir / 'src'), self.dir / 'kit-rooms-test.zip')
        code, out = _cli(['start', '--db', self.db, '--pack', str(zpath), '--room', 'synthetic-pack-kiln',
                          '--sheet', NIK], cwd=self.empty)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['room_id'], 'synthetic-pack-kiln')

    def test_named_room_by_file_name_or_manifest_path(self):
        pack = build_pack(self.dir)
        for name in ('kiln.json', 'rooms/kiln.json', 'kiln'):
            db = str(self.dir / f'{name.replace("/", "_")}.sqlite')
            code, out = _cli(['start', '--db', db, '--pack', str(pack), '--room', name, '--sheet', NIK],
                             cwd=self.empty)
            self.assertEqual(code, 0, (name, out))
            self.assertEqual(out['room_id'], 'synthetic-pack-kiln', name)

    def test_a_pack_in_the_working_dir_is_found_without_a_flag(self):
        build_pack(self.dir)
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm', '--sheet', NIK], cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'started')
        self.assertEqual(out['room_id'], 'synthetic-pack-watchroom')

    def test_a_pack_zip_in_an_upload_dir_is_found_without_a_flag(self):
        uploads = self.dir / 'uploads'
        uploads.mkdir()
        zip_pack(build_pack(self.dir / 'src'), uploads / 'kit-rooms-2099-01-01.zip')
        # A runtime ZIP next to it is not a pack.
        with zipfile.ZipFile(uploads / 'dnd-solo-main-0000.zip', 'w') as zf:
            zf.writestr('dnd-solo-main/AGENTS.md', 'x')
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm', '--sheet', NIK], cwd=uploads)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['room_id'], 'synthetic-pack-watchroom')

    def test_the_same_pack_as_a_zip_and_its_unzipped_folder_is_one_pack(self):
        folder = build_pack(self.dir)
        zip_pack(folder, self.dir / 'kit-rooms.zip')
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm', '--sheet', NIK], cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['room_id'], 'synthetic-pack-watchroom')

    def test_campaign_without_a_sheet_asks_for_one_and_mounts_nothing(self):
        build_pack(self.dir)
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm'], cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'need_character')
        self.assertIn('--sheet', out['next_step'])
        self.assertFalse(Path(self.db).exists())

    def test_campaign_with_no_pack_says_so_plainly(self):
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm'], cwd=self.empty)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'campaign_unavailable')
        self.assertEqual(out['blocker']['code'], 'mad_mage_not_executable')
        self.assertEqual(out['pack'], {'found': False, 'searched': [str(self.empty)]})
        self.assertIn('--pack', out['next_step'])
        self.assertFalse(Path(self.db).exists())

    def test_a_missing_pack_path_is_a_clear_error(self):
        code, out = _cli(['start', '--db', self.db, '--pack', str(self.dir / 'nope.zip'), '--sheet', NIK],
                         cwd=self.empty)
        self.assertEqual(code, 2)
        self.assertEqual(out['error'], 'pack_not_found')
        self.assertFalse(Path(self.db).exists())

    def test_a_room_the_pack_does_not_list_is_a_clear_error(self):
        pack = build_pack(self.dir)
        code, out = _cli(['start', '--db', self.db, '--pack', str(pack), '--room', 'level_99', '--sheet', NIK],
                         cwd=self.empty)
        self.assertEqual(code, 2)
        self.assertEqual(out['error'], 'room_not_in_pack')
        self.assertEqual(sorted(out['rooms']), ['synthetic-pack-kiln', 'synthetic-pack-watchroom'])

    def test_two_different_packs_are_ambiguous(self):
        build_pack(self.dir, 'kit-rooms')
        build_pack(self.dir, 'other-rooms')
        code, out = _cli(['start', '--db', self.db, '--campaign', 'dotmm', '--sheet', NIK], cwd=self.dir)
        self.assertEqual(code, 2)
        self.assertEqual(out['error'], 'pack_ambiguous')
        self.assertEqual(len(out['packs']), 2)

    def test_a_bad_manifest_names_its_problem(self):
        pack = build_pack(self.dir)
        manifest = json.loads((pack / 'manifest.json').read_text(encoding='utf-8'))
        manifest['first_room'] = 'rooms/missing.json'
        (pack / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        code, out = _cli(['start', '--db', self.db, '--pack', str(pack), '--sheet', NIK], cwd=self.empty)
        self.assertEqual(code, 2)
        self.assertEqual(out['error'], 'pack_invalid')
        self.assertTrue(any('first_room' in p for p in out['problems']), out)

    def test_a_zip_that_escapes_its_folder_is_refused(self):
        zpath = self.dir / 'evil.zip'
        manifest = {'schema': 'kit-rooms-pack/v1', 'pack': 'evil', 'first_room': 'rooms/a.json',
                    'rooms': [{'path': 'rooms/a.json'}]}
        with zipfile.ZipFile(zpath, 'w') as zf:
            zf.writestr('evil/manifest.json', json.dumps(manifest))
            zf.writestr('evil/rooms/a.json', '{}')
            zf.writestr('evil/../../escaped.txt', 'x')
        code, out = _cli(['start', '--db', self.db, '--pack', str(zpath), '--sheet', NIK], cwd=self.empty)
        self.assertEqual(code, 2)
        self.assertEqual(out['error'], 'pack_invalid')
        self.assertFalse((self.dir.parent / 'escaped.txt').exists())

    def test_greeting_names_the_pack_without_opening_it(self):
        build_pack(self.dir)
        code, out = _cli(['start', '--db', self.db], cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'greeting')
        self.assertEqual(out['pack']['first_room'], 'synthetic-pack-watchroom')
        self.assertNotIn('summary', json.dumps(out['pack']))
        self.assertFalse(Path(self.db).exists())

    def test_room_link_to_a_sibling_in_the_pack_resolves(self):
        # The real pack's links name absolute paths from the box that built it; another host has no
        # such path. A link resolves to the same file name next to the room it leaves.
        for link in ('kiln.json', '/no/such/build/box/rooms2/kiln.json'):
            with self.subTest(link=link):
                where = self.dir / link.strip('/').replace('/', '_')
                pack = build_pack(where, link=link)
                db = str(where / 'kit.sqlite')
                code, out = _cli(['start', '--db', db, '--pack', str(pack), '--area', 'stair_down', '--sheet', NIK],
                                 cwd=self.empty)
                self.assertEqual(code, 0, out)
                runtime = Runtime(db)
                try:
                    _, state = runtime.load()
                    source = json.loads(runtime.db.execute('SELECT body FROM source WHERE id=1').fetchone()[0])
                finally:
                    runtime.close()
                # Starting at the linked area mounts the next room in the same commit.
                self.assertEqual(source['id'], 'synthetic-pack-kiln')
                self.assertEqual(Path(state['room']['path']).resolve(), (pack / 'rooms/kiln.json').resolve())

    def test_link_ref_keeps_a_link_that_exists_as_written(self):
        self.assertEqual(kit_rooms.link_ref({'room': 'tests/fixtures/rooms/kiln.json', 'area': 'kiln'},
                                            str(self.dir / 'x.json')), 'tests/fixtures/rooms/kiln.json')


def _release_zip(target):
    """The runtime ZIP exactly as .github/workflows/runtime-zip.yml builds it: git archive of HEAD.
    Uncommitted work is added with a stash-like tree so the test checks this checkout, not the last commit."""
    env = {**os.environ, 'GIT_INDEX_FILE': str(Path(target).with_suffix('.index'))}
    subprocess.run(['git', 'read-tree', 'HEAD'], cwd=ROOT, env=env, check=True, capture_output=True)
    subprocess.run(['git', 'add', '-A', '--', '.'], cwd=ROOT, env=env, check=True, capture_output=True)
    tree = subprocess.run(['git', 'write-tree'], cwd=ROOT, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()
    subprocess.run(['git', 'archive', '--format=zip', '--prefix=dnd-solo-main/', '-o', str(target), tree],
                   cwd=ROOT, check=True, capture_output=True)
    return Path(target)


@unittest.skipUnless(shutil.which('git') and (ROOT / '.git').exists(), 'needs a git checkout to build the release ZIP')
class CleanHostTests(unittest.TestCase):
    """The non-Grok host path: unzip the release ZIP and the pack into a clean dir, plain python3,
    empty environment, no PYTHONPATH. This must keep working on every host."""

    def test_release_zip_starts_a_synthetic_pack_room_with_an_empty_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            release = _release_zip(tmp / 'dnd-solo-main-test.zip')
            data = tmp / 'mnt-data'
            data.mkdir()
            shutil.copy(release, data / release.name)
            zip_pack(build_pack(tmp / 'src'), data / 'kit-rooms-test.zip')
            repo = tmp / 'repo'
            with zipfile.ZipFile(data / release.name) as zf:
                zf.extractall(repo)
            runtime_root = repo / 'dnd-solo-main'
            self.assertTrue((runtime_root / 'runtime/kit_pack.py').is_file())
            python = shutil.which('python3') or sys.executable
            for argv in (['--pack', str(data / 'kit-rooms-test.zip')], ['--pack', str(data)]):
                db = tmp / f'kit-{len(argv[1])}.sqlite'
                proc = subprocess.run(
                    ['env', '-i', python, '-m', 'runtime.kit_agent', 'start', '--db', str(db), *argv,
                     '--sheet', NIK],
                    cwd=runtime_root, capture_output=True, text=True, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                out = json.loads(proc.stdout)
                self.assertEqual(out['stage'], 'started', out)
                self.assertEqual(out['room_id'], 'synthetic-pack-watchroom')
                self.assertTrue(out['prepared']['turn_id'])
            # And a pack dropped in the working dir is found with no flag at all.
            zip_pack(build_pack(tmp / 'src2'), runtime_root / 'kit-rooms-cwd.zip')
            proc = subprocess.run(
                ['env', '-i', python, '-m', 'runtime.kit_agent', 'start', '--db', str(tmp / 'cwd.sqlite'),
                 '--campaign', 'dotmm', '--sheet', NIK],
                cwd=runtime_root, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['room_id'], 'synthetic-pack-watchroom')


class SetupDocTests(unittest.TestCase):
    """docs/CUSTOM_GPT_SETUP.md is followed literally by people and by hosts."""

    def setUp(self):
        self.doc = (ROOT / 'docs/CUSTOM_GPT_SETUP.md').read_text(encoding='utf-8')
        start = self.doc.index('```text', self.doc.index('## 3. Instructions'))
        self.instructions = self.doc[start + len('```text'):self.doc.index('```', start + 7)]

    def test_instructions_fit_the_gpt_limit(self):
        self.assertLess(len(self.instructions), 8000)

    def test_instructions_allow_a_pack_room_and_still_forbid_regression(self):
        self.assertIn('--pack', self.instructions)
        self.assertIn('--room', self.instructions)
        self.assertNotIn('Do not pass --room or --regression', self.instructions)
        self.assertIn('--regression', self.instructions)
        self.assertIn('kit-rooms-pack/v1', self.doc)

    def test_every_repo_path_the_setup_names_exists(self):
        for path in re.findall(r'(?<![\w/.<-])((?:tests|docs|runtime)/[A-Za-z0-9_./-]+\.(?:json|md|py))', self.doc):
            self.assertTrue((ROOT / path).exists(), path)

    def test_the_preview_test_uses_a_character_in_the_repo(self):
        step = self.doc[self.doc.index('5. Test it'):self.doc.index('6. Click')]
        self.assertNotIn('the example character', step)
        self.assertIn(NIK, step)
        self.assertTrue((ROOT / NIK).is_file())

    def test_start_here_lists_the_pack_doc_and_module(self):
        text = (ROOT / 'START_HERE.md').read_text(encoding='utf-8')
        self.assertIn('docs/architecture/ROOM_PACKS.md', text)
        self.assertIn('--pack', text)


if __name__ == '__main__':
    unittest.main()

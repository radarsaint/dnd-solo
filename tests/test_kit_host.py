"""Regress complete delivery, wrong builds, partial mounts, and Python reset recovery."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kit_host', ROOT / 'scripts/kit_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class HostBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.temp.name)
        cls.repo = cls.home / 'source'
        cls.repo.mkdir()
        for name in host.REQUIRED:
            path = cls.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('source for ' + name + '\n')
        (cls.repo / 'runtime/__init__.py').write_text('')
        (cls.repo / 'runtime/kit_agent.py').write_text(
            "import sys\nassert sys.argv[1:] == ['persona']\n"
            "print('CANONICAL PERSONALITY AND VOICE')\n")
        (cls.repo / 'docs/voice').mkdir(parents=True)
        (cls.repo / 'docs/voice/table.md').write_text('voice\n')
        (cls.repo / 'docs/campaign').mkdir()
        (cls.repo / 'docs/campaign/source.md').write_text('reference material\n')
        (cls.repo / 'rooms').mkdir()
        (cls.repo / 'rooms/available.json').write_text('{}\n')
        # A complete package includes even a tracked file marked export-ignore.
        (cls.repo / '.gitattributes').write_text('docs/campaign/source.md export-ignore\n')
        cls.git('init', '-q')
        cls.git('config', 'user.name', 'Kit host test')
        cls.git('config', 'user.email', 'kit-test@example.invalid')
        cls.git('add', '.')
        cls.git('commit', '-qm', 'fixture')
        cls.commit = cls.git('rev-parse', 'HEAD').strip()
        cls.tree = cls.git('rev-parse', 'HEAD^{tree}').strip()
        (cls.repo / 'kit.sqlite').write_text('untracked save must stay local')
        cls.archive = cls.home / 'kit.zip'
        host.build(cls.repo, cls.archive)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def git(cls, *args):
        return subprocess.check_output(['git', '-C', str(cls.repo), *args], text=True)

    def setUp(self):
        self.dest = self.home / self.id().split('.')[-1]

    def mount(self, archive=None):
        return host.mount(archive or self.archive, self.dest, self.commit, self.tree)

    def altered_archive(self, changes):
        self.dest.mkdir()
        path = self.dest / 'altered.zip'
        with zipfile.ZipFile(self.archive) as original, zipfile.ZipFile(path, 'w') as changed:
            for name in original.namelist():
                data = changes.get(name, original.read(name))
                if data is not None:
                    changed.writestr(name, data)
        return path

    def test_complete_tree_includes_host_docs_rooms_and_reference_bytes(self):
        report = self.mount()
        root = Path(report['root'])
        tracked = set(self.git('ls-files').splitlines())
        self.assertEqual(report['verified_files'], len(tracked))
        for name in tracked:
            self.assertEqual((root / name).read_bytes(), (self.repo / name).read_bytes())
        self.assertFalse((root / 'kit.sqlite').exists())
        self.assertFalse(report['game_started'])
        self.assertFalse(report['host_context_read'])
        context = Path(report['host_context']).read_text()
        self.assertIn('source for AGENTS.md', context)
        self.assertIn('CANONICAL PERSONALITY AND VOICE', context)

    def test_reset_reinstalls_from_zip_without_network_or_git_in_host(self):
        first = self.mount()
        shutil.rmtree(Path(first['root']))
        Path(first['host_context']).unlink()
        second = self.mount()
        self.assertEqual(first['commit'], second['commit'])
        self.assertFalse(second['reused'])
        self.assertTrue(Path(second['host_context']).is_file())

    def test_partial_or_changed_existing_mount_is_repaired_and_preserved(self):
        first = self.mount()
        root = Path(first['root'])
        (root / 'AGENTS.md').unlink()
        (root / 'runtime/kit_agent.py').write_text('broken\n')
        (root / 'kit.sqlite').write_text('existing user save')
        second = self.mount()
        self.assertFalse(second['reused'])
        saved = Path(second['preserved_previous_root'])
        self.assertEqual((saved / 'kit.sqlite').read_text(), 'existing user save')
        self.assertEqual(second['persona_exit'], 0)
        self.assertTrue(self.mount()['reused'])

    def test_wrong_commit_and_wrong_external_tree_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'requested commit'):
            host.mount(self.archive, self.dest, '0' * 40, self.tree)
        with self.assertRaisesRegex(ValueError, 'requested source tree'):
            host.mount(self.archive, self.dest, self.commit, '0' * 40)

    def test_missing_file_or_corrupt_payload_cannot_be_called_mounted(self):
        name = host.PREFIX + 'AGENTS.md'
        altered = self.altered_archive({name: None})
        with self.assertRaisesRegex(ValueError, 'Archive members'):
            self.mount(altered)
        self.assertFalse(list(self.dest.glob('kit-*')))
        altered.unlink()
        self.dest.rmdir()
        altered = self.altered_archive({name: b'wrong instructions'})
        with self.assertRaisesRegex(ValueError, 'verification'):
            self.mount(altered)
        self.assertFalse(list(self.dest.glob('kit-*')))

    def test_removing_both_file_and_manifest_row_does_not_hide_omission(self):
        with zipfile.ZipFile(self.archive) as z:
            manifest = json.loads(z.read(host.PREFIX + host.MANIFEST))
        name = 'docs/campaign/source.md'
        manifest['files'] = [x for x in manifest['files'] if x['path'] != name]
        altered = self.altered_archive({host.PREFIX + name: None,
                                       host.PREFIX + host.MANIFEST: json.dumps(manifest)})
        with self.assertRaisesRegex(ValueError, 'complete source tree'):
            self.mount(altered)

    def test_persona_failure_is_a_failed_load(self):
        first = self.mount()
        root = Path(first['root'])
        # Exercise the runtime probe directly: source verification precedes it
        # in mount(), and a command failure must never produce a ready report.
        (root / 'runtime/kit_agent.py').write_text('raise RuntimeError("cannot run")\n')
        with self.assertRaisesRegex(ValueError, 'persona failed'):
            host.host_context(root, {'commit': self.commit})


if __name__ == '__main__':
    unittest.main()

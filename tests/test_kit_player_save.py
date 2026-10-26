"""P1 leak fix (docs/architecture/PLAYER_SAVE.md): `save` writes a player-safe ZIP.

The raw kit.sqlite carries the whole room file (hidden facts, DCs, claims, secret
actors and exits, book text). It is runtime-only. What the player downloads is a
ZIP of campaign.json, journal.md and the sheet, built from a whitelist of public
state. These tests mount several synthetic rooms (6c is one fixture among them),
collect every hidden string in each room, and check that none of it is exported.
"""

import contextlib
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

from runtime import kit_adventure, kit_agent, kit_rooms, kit_save
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
NIK = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'
ROOMS = ROOT / 'tests' / 'fixtures' / 'rooms'
SIXC = ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'
FERRY = ROOT / 'tests' / 'fixtures' / 'adventures' / 'lantern_ferry.txt'  # original synthetic
FILES = {'campaign.json', 'journal.md', 'characters/nik/sheet.json', 'characters/nik/sheet.md'}
MIN_LEN = 12  # shorter strings ("alive", "landing") are labels the public view also uses


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from keys(value)


def dcs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() == 'dc' and isinstance(value, int):
                yield value
            yield from dcs(value)
    elif isinstance(node, list):
        for value in node:
            yield from dcs(value)


def secret_room(tmp):
    """The watchroom plus a secret exit, a hidden actor with secrets, and a hidden fact."""
    room = json.loads((ROOMS / 'watchroom.json').read_text(encoding='utf-8'))
    room['id'] = 'synthetic-watchroom-secrets-v1'
    lurker = copy.deepcopy(room['actors']['warden'])
    lurker.update({'name': 'Hooded lurker under the bunk', 'visible': False, 'guards': [],
                   'motive': 'Steal the sealed letter before dawn.',
                   'knowledge': ['The warden sleeps through the second bell.'],
                   'secrets': ['Owes the quartermaster forty crowns.']})
    room['actors']['lurker'] = lurker
    room['exits']['bolt_hole'] = {
        'name': 'the bolt hole behind the chest', 'areas': ['watchroom', 'stair_down'], 'secret': True,
        'labels': {'watchroom': 'A bolt hole hides behind the bolted chest.',
                   'stair_down': 'A bolt hole opens into the stairwell wall.'}}
    room['facts']['ledger_code'] = {'area': 'watchroom', 'visible': False,
                                    'text': 'The letter names the vault password: amber-nine-wolves.'}
    path = Path(tmp) / 'watchroom_secrets.json'
    path.write_text(json.dumps(room), encoding='utf-8')
    return path


def runtime_zip(out):
    """The release ZIP (.github/workflows/runtime-zip.yml: git archive --prefix=dnd-solo-main/ HEAD),
    built from the tracked and new files of this working tree so the test covers uncommitted work."""
    if not shutil.which('git') or not (ROOT / '.git').exists():
        raise unittest.SkipTest('needs a git checkout')
    listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, check=True, capture_output=True).stdout.decode().split('\0')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in filter(None, listed):
            if (ROOT / rel).is_file():
                z.write(ROOT / rel, 'dnd-solo-main/' + rel)
    return out


class SaveBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def mount(self, room, name):
        db = self.dir / name / 'kit.sqlite'
        db.parent.mkdir()
        kit_agent.start_session(str(db), str(NIK), room=str(room))
        return db

    def export(self, db, **kw):
        result = kit_save.save(str(db), **kw)
        with zipfile.ZipFile(result['zip']) as archive:
            files = {name: archive.read(name).decode('utf-8') for name in archive.namelist()}
        return result, files

    def hidden(self, db):
        """Every string of the room that the player cannot see, and its DCs."""
        runtime = Runtime(str(db))
        try:
            source, (_, state) = runtime.source(), runtime.load()
            public = set(strings(runtime.player_view())) | {source['id']}
            # What the player learned anywhere in the room is theirs (P2 exports it).
            public |= {source['facts'][k]['text'] for k in kit_rooms.known_fact_ids(source, state)
                       if k in source['facts']}
            public |= {source['areas'][a]['name'] for a in state.get('visited') or () if a in source['areas']}
            raw = runtime.db.execute('SELECT body FROM source').fetchone()[0]
        finally:
            runtime.close()
        secret = {s for s in strings(source) if len(s) >= MIN_LEN and s not in public}
        return secret, set(dcs(source)), raw, public

    def assert_nothing_hidden(self, db, files):
        secret, room_dcs, raw, public = self.hidden(db)
        self.assertTrue(secret)
        # A hidden string that is only a piece of something public ("the watchroom" in the
        # area name, "investigation" as a sheet skill) is not a leak: blank the public text first.
        sheet = json.loads(NIK.read_text(encoding='utf-8'))
        allowed = sorted(public | set(strings(sheet)) | set(keys(sheet)), key=len, reverse=True)
        for name, full in files.items():
            # Hashes and turn ids are hex: blank them first, or a stray "dc" in one reads as a DC.
            text = re.sub(r'[0-9a-f]{12,}', '\u2591', full)
            for item in allowed:
                text = text.replace(item, '\u2591')
            self.assertNotIn(raw, full, name)
            self.assertNotIn('SQLite format 3', full, name)
            for item in secret:
                self.assertNotIn(item, text, f'{name} leaks {item!r}')
            if name.endswith('campaign.json') or name.endswith('journal.md'):
                # On the unblanked text, hashes removed: blanking can put word edges inside a hex digest.
                plain = re.sub(r'\b[0-9a-f]{64}\b', '', full)
                self.assertNotRegex(plain, r'(?i)\bdc\b', name)
                self.assertNotIn('claim', plain.lower(), name)
            if name.endswith('sheet.md'):
                sheet_dc = json.loads(NIK.read_text(encoding='utf-8')).get('spell_save_dc')
                for dc in re.findall(r'(?i)\bdc\s*(\d+)', text):
                    self.assertEqual(int(dc), sheet_dc, name)
        self.assertTrue(room_dcs is not None)


class SaveTests(SaveBase):
    def test_save_zip_holds_exactly_the_player_files(self):
        db = self.mount(ROOMS / 'watchroom.json', 'w')
        result, files = self.export(db)
        self.assertEqual(result['stage'], 'saved')
        self.assertEqual(set(files), FILES)
        self.assertFalse(any(n.endswith('.sqlite') for n in files))
        campaign = json.loads(files['campaign.json'])
        self.assertEqual(campaign['schema'], 'kit_campaign_v1')
        self.assertEqual(campaign['journal_mode'], 'campaign')
        self.assertEqual(campaign['pcs'], ['nik'])
        self.assertEqual(campaign['location']['room_id'], 'synthetic-watchroom-v1')
        self.assertEqual(campaign['location']['area'], 'Landing outside the watchroom')
        self.assertEqual(json.loads(files['characters/nik/sheet.json']),
                         json.loads(NIK.read_text(encoding='utf-8')))
        self.assertIn('# Nik', files['characters/nik/sheet.md'])
        self.assertIn('```kit-state', files['journal.md'])
        self.assertIn('kit.sqlite', result['next_step'])
        self.assertIn('never', result['next_step'].lower())

    def test_nothing_hidden_in_any_exported_file_across_fixtures(self):
        rooms = sorted(ROOMS.glob('*.json')) + [SIXC]
        self.assertGreaterEqual(len(rooms), 6)
        for room in rooms:
            with self.subTest(room=room.name):
                db = self.mount(room, room.stem)
                _, files = self.export(db)
                self.assertEqual(set(files), FILES)
                self.assert_nothing_hidden(db, files)

    def test_the_fixtures_actually_carry_dcs_and_claims(self):
        crypt = json.loads((ROOMS / 'crypt.json').read_text(encoding='utf-8'))
        sixc = json.loads(SIXC.read_text(encoding='utf-8'))
        self.assertTrue(set(dcs(crypt)) and set(dcs(sixc)))
        self.assertTrue(crypt.get('claims') and sixc.get('claims'))

    def test_secret_exit_hidden_actor_and_hidden_fact_stay_out_after_a_move(self):
        db = self.mount(secret_room(self.dir), 's')
        runtime = Runtime(str(db))
        try:
            runtime.abandon_pending() if hasattr(runtime, 'abandon_pending') else None
            revision, _ = runtime.load()
            runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])
        finally:
            runtime.close()
        _, files = self.export(db)
        self.assert_nothing_hidden(db, files)
        everything = '\n'.join(files.values())
        for item in ('Hooded lurker', 'bolt hole', 'amber-nine-wolves', 'forty crowns', 'Steal the sealed'):
            self.assertNotIn(item, everything)
        campaign = json.loads(files['campaign.json'])
        self.assertEqual(campaign['location']['area'], 'Watchroom')
        self.assertEqual([n['name'] for n in campaign['npcs_met']], ['Watch warden'])
        self.assertIn('Watch warden', files['journal.md'])

    def test_save_writes_the_folder_layout_under_saves(self):
        db = self.mount(ROOMS / 'kiln.json', 'k')
        result, _ = self.export(db, player='Brendon', campaign='Test Run')
        folder = Path(result['folder'])
        self.assertEqual(folder, db.parent / 'saves' / 'brendon' / 'test-run')
        for name in FILES:
            self.assertTrue((folder / name).is_file(), name)
        self.assertFalse(list(folder.rglob('*.sqlite')))
        self.assertEqual(Path(result['zip']).parent, folder)

    def test_save_twice_is_stable_and_names_the_revision(self):
        db = self.mount(ROOMS / 'kiln.json', 'k2')
        first, a = self.export(db)
        second, b = self.export(db)
        self.assertEqual(first['zip'], second['zip'])
        self.assertEqual(json.loads(a['campaign.json'])['export']['revision'],
                         json.loads(b['campaign.json'])['export']['revision'])

    def test_save_with_no_game_is_a_clear_error_and_creates_nothing(self):
        db = self.dir / 'none' / 'kit.sqlite'
        with self.assertRaises(kit_save.SaveError) as caught:
            kit_save.save(str(db))
        self.assertIn('start', str(caught.exception))
        self.assertFalse(db.exists())

    def test_cli_save_prints_json(self):
        db = self.mount(ROOMS / 'shrine.json', 'cli')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), unittest.mock.patch.object(
                sys, 'argv', ['kit_agent', 'save', '--db', str(db)]):
            self.assertEqual(kit_agent.main(), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result['stage'], 'saved')
        self.assertTrue(Path(result['zip']).is_file())


class CleanHostSaveTest(unittest.TestCase):
    """Build the runtime ZIP the release way, unzip it in a clean dir, start, then save, under env -i."""

    def test_save_from_the_bare_runtime_zip(self):
        if not shutil.which('env') or not shutil.which('python3'):
            self.skipTest('needs env and python3')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = runtime_zip(tmp / 'runtime.zip')
            box = tmp / 'clean'
            with zipfile.ZipFile(archive) as z:
                z.extractall(box)
            repo = box / 'dnd-solo-main'
            room = tmp / 'watchroom_secrets.json'
            room.write_text(secret_room(tmp).read_text(encoding='utf-8'), encoding='utf-8')
            base = ['env', '-i', 'python3', '-m', 'runtime.kit_agent']
            started = subprocess.run(base + ['start', '--regression', '--room', str(room), '--sheet',
                                             'tests/fixtures/characters/nik.json'],
                                     cwd=repo, capture_output=True, text=True)
            self.assertEqual(started.returncode, 0, started.stderr)
            saved = subprocess.run(base + ['save'], cwd=repo, capture_output=True, text=True)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            result = json.loads(saved.stdout)
            with zipfile.ZipFile(result['zip'] if os.path.isabs(result['zip']) else repo / result['zip']) as z:
                names = set(z.namelist())
                text = '\n'.join(z.read(n).decode('utf-8') for n in names)
            self.assertEqual(names, FILES)
            for item in ('Hooded lurker', 'bolt hole', 'amber-nine-wolves', 'forty crowns'):
                self.assertNotIn(item, text)


class HostDocsTests(unittest.TestCase):
    def instructions(self):
        text = (ROOT / 'docs' / 'CUSTOM_GPT_SETUP.md').read_text(encoding='utf-8')
        return re.search(r'## 3\. Instructions.*?```text\n(.*?)```', text, re.S).group(1)

    def test_gpt_instructions_save_the_zip_and_keep_sqlite_runtime_only(self):
        block = self.instructions()
        self.assertLess(len(block), 8000)
        self.assertIn('kit_agent save --db kit.sqlite', block)
        self.assertIn('runtime-only', block)
        self.assertNotIn('offer REPO/kit.sqlite', block)

    def test_readme_agents_start_here_mark_sqlite_runtime_only(self):
        for name in ('README.md', 'AGENTS.md', 'START_HERE.md'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('runtime-only', text, name)
            self.assertIn('kit_agent save', text, name)
        self.assertIn('saves/', (ROOT / '.gitignore').read_text(encoding='utf-8'))


class ImportedAdventureSaveTests(SaveBase):
    """Saves work for imported adventures (#172) with compiled creatures (#174), not only hand-built
    rooms: no DM-only fact, hidden creature, stat block, secret connection or book passage is exported."""

    def imported(self, key):
        db = self.dir / f'adv{key}' / 'kit.sqlite'
        db.parent.mkdir()
        kit_adventure.import_adventure(db, text=FERRY.read_text(encoding='utf-8'))
        kit_adventure.compile_location(db, key)
        kit_agent.start_session(str(db), str(NIK), room=str(kit_adventure.room_file(db, key)))
        return db

    def test_every_imported_location_saves_without_hidden_state(self):
        index = kit_adventure._load(self.imported('1'))[0]
        keys = list(index['locations'])
        self.assertGreaterEqual(len(keys), 4)
        hidden_actors = 0
        for key in keys:
            with self.subTest(location=key):
                db = self.imported(key) if key != '1' else self.dir / 'adv1' / 'kit.sqlite'
                room = json.loads(kit_adventure.room_file(db, key).read_text(encoding='utf-8'))
                result, files = self.export(db)
                self.assertEqual(set(files), FILES)
                self.assert_nothing_hidden(db, files)
                everything = '\n'.join(files.values())
                for actor in room.get('actors', {}).values():
                    if not actor.get('visible', True):
                        hidden_actors += 1
                        self.assertNotIn(actor['name'], everything)
                        for item in strings(actor.get('stat_block', {})):
                            if len(item) >= MIN_LEN:
                                self.assertNotIn(item, everything)
                for fact in room.get('facts', {}).values():
                    if not fact.get('visible', True):
                        self.assertNotIn(fact['text'], everything)
                self.assertNotIn('secret hatch', everything.lower())
                folder = kit_adventure.folder_for(db)
                book = (folder / 'source.txt').read_text(encoding='utf-8')
                self.assertNotIn(book, everything)
                self.assertFalse(any(n.endswith(('source.txt', 'index.json')) or '/rooms/' in n for n in files))
                zipped = Path(result['zip']).read_bytes()
                self.assertNotIn(b'SQLite format 3', zipped)
        self.assertGreaterEqual(hidden_actors, 3)   # the bandits, the wight and the lurker were checked

    def test_a_woken_creature_still_unseen_stays_out_of_the_save(self):
        db = self.imported('4')
        runtime = Runtime(str(db))
        try:
            revision, state = runtime.load()
            actor_id = next(k for k, v in state['actors'].items() if v['status'] == 'hidden')
            name = state['actors'][actor_id]['name']
            runtime.commit('wake', revision, [{'type': 'actor_status', 'actor': actor_id, 'status': 'alive',
                                               'evidence': 'Something stirs.'}])
        finally:
            runtime.close()
        _, files = self.export(db)
        self.assert_nothing_hidden(db, files)
        self.assertNotIn(name, '\n'.join(files.values()))


if __name__ == '__main__':
    unittest.main()

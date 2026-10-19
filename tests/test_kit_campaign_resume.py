"""P3 of the campaign-record design: resume from the player's save, not from kit.sqlite.

- A kit.sqlite that matches campaign.location continues mid-room (the existing resume).
- No sqlite: the save's current room mounts fresh at its start, with campaign.json applied
  (rooms left, people met, what was learned and carried, the player's sheet as written).
- Only the journal survives: rebuild from its kit-state block; with neither, Kit asks once.
- The greeting lists the saves it finds, and asks a new campaign the journal-mode question.
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

from runtime import kit_agent, kit_campaign, kit_resume, kit_save
from runtime.state_context import Runtime
from tests.test_kit_campaign_ledger import CARCASS, Ledger
from tests.test_kit_player_save import NIK, ROOMS, runtime_zip, secret_room


class ResumeFromSave(Ledger):
    def saved_zip(self, **kw):
        self.walk_to_carcass()
        result, _ = self.save(recap='Nik left the watchroom by the stair.', **kw)
        return Path(result['zip'])

    def fresh(self):
        box = self.dir / 'new-sandbox'
        box.mkdir()
        return box / 'kit.sqlite'

    def test_no_sqlite_mounts_the_room_fresh_with_the_campaign_applied(self):
        archive = self.saved_zip()
        db = self.fresh()
        result = kit_resume.resume(str(db), str(archive), room=str(CARCASS))
        self.assertEqual(result['stage'], 'resumed_from_save')
        self.assertEqual(result['room_id'], 'synthetic-carcass-v1')
        self.assertIn('prepared', result)
        runtime = Runtime(str(db))
        try:
            revision, state = runtime.load()
            self.assertEqual(state['area'], runtime.source()['starting_area'])
            self.assertEqual([r['room_id'] for r in state['campaign_log']['rooms']],
                             ['synthetic-watchroom-secrets-v1'])
            self.assertEqual(state['player_sheet']['name'], 'Nik')
        finally:
            runtime.close()
        # the next save carries the history over
        again = kit_save.save(str(db))
        campaign = json.loads((Path(again['folder']) / 'campaign.json').read_text(encoding='utf-8'))
        self.assertIn('Watch warden', [n['name'] for n in campaign['npcs_met']])
        self.assertTrue(any(s.get('recap') == 'Nik left the watchroom by the stair.' for s in campaign['sessions']))

    def test_the_room_is_found_by_id_in_the_search_dirs(self):
        archive = self.saved_zip()
        db = self.fresh()
        rooms = self.dir / 'attached'
        rooms.mkdir()
        shutil.copy(CARCASS, rooms / 'anything.json')
        result = kit_resume.resume(str(db), str(archive), search=[rooms])
        self.assertEqual(result['room'], str(rooms / 'anything.json'))

    def test_a_missing_room_is_a_clear_stop_and_creates_nothing(self):
        archive = self.saved_zip()
        db = self.fresh()
        with self.assertRaises(kit_resume.ResumeError) as caught:
            kit_resume.resume(str(db), str(archive), search=[self.dir / 'nowhere'])
        self.assertIn('synthetic-carcass-v1', str(caught.exception))
        self.assertFalse(db.exists())

    def test_a_folder_save_works_like_the_zip(self):
        self.walk_to_carcass()
        result, _ = self.save()
        db = self.fresh()
        out = kit_resume.resume(str(db), result['folder'], room=str(CARCASS))
        self.assertEqual(out['stage'], 'resumed_from_save')

    def test_a_matching_sqlite_continues_mid_room(self):
        archive = self.saved_zip()
        result = kit_resume.resume(str(self.db), str(archive))
        self.assertEqual(result['stage'], 'resume')
        self.assertEqual(result['room_id'], 'synthetic-carcass-v1')

    def test_a_sqlite_for_another_room_is_refused(self):
        self.save()  # watchroom
        archive = next((self.dir / 'saves').rglob('*.zip'))
        self.walk_to_carcass()
        with self.assertRaises(kit_resume.ResumeError) as caught:
            kit_resume.resume(str(self.db), str(archive))
        self.assertIn('--db', str(caught.exception))

    def test_a_hand_edited_sheet_is_used_as_written_and_noticed(self):
        archive = self.saved_zip()
        edited = self.dir / 'edited.zip'
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(edited, 'w') as dst:
            for name in src.namelist():
                data = src.read(name)
                if name.endswith('sheet.json'):
                    sheet = json.loads(data)
                    sheet['gold_gp'] = 1234
                    data = json.dumps(sheet).encode()
                dst.writestr(name, data)
        db = self.fresh()
        result = kit_resume.resume(str(db), str(edited), room=str(CARCASS))
        self.assertIn('characters/nik/sheet.json', result['noticed'])
        runtime = Runtime(str(db))
        try:
            self.assertEqual(runtime.load()[1]['player_sheet']['gold_gp'], 1234)
        finally:
            runtime.close()

    def test_room_file_drift_is_reported_and_play_goes_on(self):
        archive = self.saved_zip()
        changed = json.loads(CARCASS.read_text(encoding='utf-8'))
        changed['_note'] = changed.get('_note', '') + ' (revised)'
        path = self.dir / 'carcass_v2.json'
        path.write_text(json.dumps(changed), encoding='utf-8')
        result = kit_resume.resume(str(self.fresh()), str(archive), room=str(path))
        self.assertTrue(result['room_changed'])

    def test_unsafe_zip_member_names_are_refused(self):
        bad = self.dir / 'bad.zip'
        with zipfile.ZipFile(bad, 'w') as z:
            z.writestr('../campaign.json', '{}')
        with self.assertRaises(kit_resume.ResumeError):
            kit_resume.resume(str(self.fresh()), str(bad))


class RebuildFromJournal(Ledger):
    def test_only_the_journal_rebuilds_from_its_kit_state_block(self):
        self.walk_to_carcass()
        result, files = self.save()
        only = self.dir / 'journal-only.zip'
        with zipfile.ZipFile(only, 'w') as z:
            z.writestr('journal.md', files['journal.md'])
        out = kit_resume.resume(str(self.dir / 'b' / 'kit.sqlite'), str(only), room=str(CARCASS), sheet=str(NIK))
        self.assertEqual(out['stage'], 'resumed_from_save')
        self.assertTrue(out['rebuilt_from_journal'])
        self.assertEqual(out['room_id'], 'synthetic-carcass-v1')

    def test_journal_only_and_no_sheet_asks_for_the_sheet(self):
        self.walk_to_carcass()
        _, files = self.save()
        only = self.dir / 'journal-only.zip'
        with zipfile.ZipFile(only, 'w') as z:
            z.writestr('journal.md', files['journal.md'])
        out = kit_resume.resume(str(self.dir / 'c' / 'kit.sqlite'), str(only), room=str(CARCASS))
        self.assertEqual(out['stage'], 'need_character')

    def test_no_campaign_and_no_kit_state_asks_kit_to_rebuild_with_the_player(self):
        bare = self.dir / 'bare.zip'
        with zipfile.ZipFile(bare, 'w') as z:
            z.writestr('journal.md', '# Journal: Nik\n\nWe fought a thing.\n')
        out = kit_resume.resume(str(self.dir / 'd' / 'kit.sqlite'), str(bare))
        self.assertEqual(out['stage'], 'needs_rebuild')
        self.assertIn('confirm', out['next_step'])
        self.assertFalse((self.dir / 'd' / 'kit.sqlite').exists())


class Lobby(Ledger):
    def test_greeting_lists_saves_it_finds(self):
        self.walk_to_carcass()
        result, _ = self.save(recap='Nik went down the stair.')
        uploads = self.dir / 'uploads'
        uploads.mkdir()
        shutil.copy(result['zip'], uploads / 'kit-save-solo-nik.zip')
        with unittest.mock.patch.object(kit_resume, 'UPLOAD_DIRS', (str(uploads),)):
            listed = kit_resume.find_saves(str(self.dir / 'elsewhere' / 'kit.sqlite'))
        self.assertEqual(len(listed), 1)
        entry = listed[0]
        self.assertEqual((entry['pc'], entry['room_id']), ('Nik', 'synthetic-carcass-v1'))
        self.assertEqual(entry['last_session']['recap'], 'Nik went down the stair.')
        self.assertIn('open_threads', entry)
        self.assertEqual(entry['player'], 'player')

    def test_greeting_carries_saves_and_the_journal_mode_question(self):
        self.walk_to_carcass()
        self.save()
        empty = self.dir / 'nothing-here'
        greeting = kit_campaign.campaign_entry(str(self.dir / 'other.sqlite'), saves_db=str(self.db))
        self.assertEqual(greeting['stage'], 'greeting')
        self.assertTrue(greeting['saves'])
        self.assertIn('Nik', greeting['table_line'])
        ask = greeting['new_campaign']
        self.assertEqual(ask['ask'][0]['key'], 'journal_mode')
        self.assertEqual(ask['ask'][0]['options'], ['campaign', 'character'])
        self.assertTrue(empty)

    def test_greeting_with_no_saves_is_unchanged(self):
        greeting = kit_campaign.campaign_entry(str(self.dir / 'fresh' / 'kit.sqlite'))
        self.assertEqual(greeting['saves'], [])
        self.assertEqual(greeting['table_line'], kit_campaign.GREETING)


class CleanHostResume(unittest.TestCase):
    def test_save_then_resume_in_a_new_sandbox_from_the_bare_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with zipfile.ZipFile(runtime_zip(tmp / 'runtime.zip')) as z:
                z.extractall(tmp / 'a')
                z.extractall(tmp / 'b')
            room = tmp / 'watchroom_secrets.json'
            room.write_text(secret_room(tmp).read_text(encoding='utf-8'), encoding='utf-8')
            base = ['env', '-i', 'python3', '-m', 'runtime.kit_agent']
            a, b = tmp / 'a' / 'dnd-solo-main', tmp / 'b' / 'dnd-solo-main'
            run = lambda cwd, *args: subprocess.run(base + list(args), cwd=cwd, capture_output=True, text=True)
            started = run(a, 'start', '--regression', '--room', str(room), '--sheet', 'tests/fixtures/characters/nik.json')
            self.assertEqual(started.returncode, 0, started.stderr)
            saved = run(a, 'save')
            self.assertEqual(saved.returncode, 0, saved.stderr)
            archive = json.loads(saved.stdout)['zip']
            resumed = run(b, 'start', '--save', archive, '--room', str(room), '--regression')
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(json.loads(resumed.stdout)['stage'], 'resumed_from_save')
            self.assertFalse(any((b / 'saves').rglob('*.sqlite')))


if __name__ == '__main__':
    unittest.main()

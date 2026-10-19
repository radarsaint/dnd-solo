"""P2 of the campaign-record design (docs/architecture/PLAYER_SAVE.md): the ledger fold.

The public record of a room is folded at room exit (the room file is gone once the next one
mounts), and again on every save. The journal renders in both modes, one PC. Kit's recap is
hers, short and guarded. A hand edit is taken as written and noted, never arbitrated.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

from runtime import kit_agent, kit_rooms, kit_save
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime
from tests.test_kit_player_save import NIK, ROOMS, secret_room, strings

CARCASS = ROOMS / 'carcass.json'


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        watch = json.loads(secret_room(self.dir).read_text(encoding='utf-8'))
        watch['areas']['stair_down']['room_link'] = {'room': str(CARCASS), 'area': 'hall'}
        self.watch_path = self.dir / 'watch.json'
        self.watch_path.write_text(json.dumps(watch), encoding='utf-8')
        self.watch = watch
        self.db = self.dir / 'kit.sqlite'
        started = start_session(str(self.db), str(NIK), room=str(self.watch_path), area='landing')
        self.runtime = Runtime(str(self.db))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.runtime.close)
        KitChatBridge(self.runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])

    def play(self, line):
        revision, state = self.runtime.load()
        result = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 1,
                                 source=self.runtime.source()).resolve(line, revision, state)
        self.runtime.commit(f'p{revision}', revision, list(result.events))
        return result

    def walk_to_carcass(self):
        self.play('I go through the iron door.')
        self.assertEqual(self.runtime.load()[1]['area'], 'watchroom')
        self.play('I go back out through the iron door.')
        self.assertEqual(self.runtime.load()[1]['area'], 'landing')
        self.play('I take the stair down.')
        self.assertEqual(self.runtime.source()['id'], 'synthetic-carcass-v1')

    def save(self, **kw):
        result = kit_save.save(str(self.db), **kw)
        with zipfile.ZipFile(result['zip']) as archive:
            files = {n: archive.read(n).decode('utf-8') for n in archive.namelist()}
        return result, files


class FoldAtRoomExit(Ledger):
    def test_the_room_left_is_folded_with_only_what_the_player_saw(self):
        self.walk_to_carcass()
        _, files = self.save()
        campaign = json.loads(files['campaign.json'])
        rooms = [(r['room_id'], r['status']) for r in campaign['rooms']]
        self.assertEqual(rooms, [('synthetic-watchroom-secrets-v1', 'left'), ('synthetic-carcass-v1', 'current')])
        met = {(n['name'], n['room_id']) for n in campaign['npcs_met']}
        self.assertIn(('Watch warden', 'synthetic-watchroom-secrets-v1'), met)
        left = campaign['rooms'][0]
        self.assertIn('Watchroom', left['areas'])
        self.assertIn('A plain wooden chest sits under the arrow slit.',
                      [f['text'] for f in campaign['learned']])
        everything = '\n'.join(files.values())
        for item in ('Hooded lurker', 'bolt hole', 'amber-nine-wolves', 'forty crowns',
                     'Steal the sealed', 'Keep strangers off the stair', 'Who is expected tonight'):
            self.assertNotIn(item, everything)

    def test_hidden_strings_of_both_rooms_stay_out(self):
        self.walk_to_carcass()
        _, files = self.save()
        carcass = json.loads(CARCASS.read_text(encoding='utf-8'))
        campaign = json.loads(files['campaign.json'])
        public = set(strings(campaign['learned'])) | {r['room_id'] for r in campaign['rooms']}
        public |= {n['name'] for n in campaign['npcs_met']} | set(strings([r['areas'] for r in campaign['rooms']]))
        public |= set(strings(self.runtime.player_view()))
        sheet = json.loads(NIK.read_text(encoding='utf-8'))
        allowed = sorted(public | set(strings(sheet)), key=len, reverse=True)
        for room in (self.watch, carcass):
            hidden = {s for s in strings(room) if len(s) >= 12 and s not in public}
            for name, text in files.items():
                for item in allowed:
                    text = text.replace(item, '\u2591')
                for item in hidden:
                    self.assertNotIn(item, text, f'{name} leaks {item!r}')

    def test_the_fold_is_stored_in_the_runtime_at_exit(self):
        self.walk_to_carcass()
        log = self.runtime.load()[1]['campaign_log']
        self.assertEqual([r['room_id'] for r in log['rooms']], ['synthetic-watchroom-secrets-v1'])

    def test_choices_are_the_players_own_words(self):
        self.walk_to_carcass()
        _, files = self.save()
        campaign = json.loads(files['campaign.json'])
        self.assertEqual([c['said'] for c in campaign['choices']], [])  # raw commits carry no Kit turn
        self.assertIsInstance(campaign['choices'], list)


class JournalModes(Ledger):
    def test_campaign_mode_puts_one_journal_at_the_top(self):
        result, files = self.save()
        self.assertIn('journal.md', files)
        self.assertNotIn('characters/nik/journal.md', files)
        for section in ('## Threads', '## People met', '## Loot and coin', '## Debts', '## Session log',
                        '```kit-state'):
            self.assertIn(section, files['journal.md'])

    def test_character_mode_puts_the_journal_with_the_character_and_sticks(self):
        _, files = self.save(journal_mode='character')
        self.assertIn('characters/nik/journal.md', files)
        self.assertNotIn('journal.md', files)
        self.assertEqual(json.loads(files['campaign.json'])['journal_mode'], 'character')
        self.play('I go through the iron door.')
        _, again = self.save()
        self.assertIn('characters/nik/journal.md', again)

    def test_session_log_is_newest_first_and_sessions_accumulate(self):
        self.save(recap='Nik checked the landing and listened at the iron door.')
        self.play('I go through the iron door.')
        _, files = self.save(recap='Nik stepped into the watchroom and met the warden.')
        campaign = json.loads(files['campaign.json'])
        self.assertEqual(len(campaign['sessions']), 2)
        journal = files['journal.md']
        self.assertLess(journal.index('met the warden'), journal.index('listened at the iron door'))


class Recap(Ledger):
    def test_a_short_public_recap_is_kept(self):
        _, files = self.save(recap='Nik paused on the landing, listening to the humming.')
        self.assertIn('listening to the humming', files['journal.md'])
        self.assertEqual(json.loads(files['campaign.json'])['sessions'][-1]['recap'],
                         'Nik paused on the landing, listening to the humming.')

    def test_over_120_words_is_refused_and_nothing_is_written(self):
        with self.assertRaises(kit_save.SaveError) as caught:
            self.save(recap=' '.join(['word'] * 121))
        self.assertIn('120', str(caught.exception))
        self.assertFalse((self.dir / 'saves').exists())

    def test_a_recap_naming_hidden_things_is_refused(self):
        for bad in ('Nik never saw the Hooded lurker under the bunk.',
                    'The letter names the vault password: amber-nine-wolves.',
                    'He missed the bolt hole behind the chest.',
                    'The door was a DC 12 check.'):
            with self.subTest(bad=bad), self.assertRaises(kit_save.SaveError):
                self.save(recap=bad)
        self.assertFalse((self.dir / 'saves').exists())

    def test_cli_takes_a_recap_file_and_journal_mode(self):
        recap = self.dir / 'recap.txt'
        recap.write_text('Nik waited on the landing.', encoding='utf-8')
        out = io.StringIO()
        argv = ['kit_agent', 'save', '--db', str(self.db), '--recap-file', str(recap), '--journal-mode', 'character']
        with contextlib.redirect_stdout(out), unittest.mock.patch.object(sys, 'argv', argv):
            self.assertEqual(kit_agent.main(), 0)
        result = json.loads(out.getvalue())
        self.assertIn('characters/nik/journal.md', result['files'])

    def test_save_without_a_recap_asks_kit_for_one(self):
        result, _ = self.save()
        self.assertIn('--recap-file', result['next_step'])


class HandEdits(Ledger):
    def folder(self, result):
        return Path(result['folder'])

    def test_an_edited_sheet_is_taken_as_written_and_noted(self):
        result, _ = self.save()
        path = self.folder(result) / 'characters' / 'nik' / 'sheet.json'
        sheet = json.loads(path.read_text(encoding='utf-8'))
        sheet['gold_gp'] = 900
        path.write_text(json.dumps(sheet), encoding='utf-8')
        again, files = self.save()
        self.assertEqual(json.loads(files['characters/nik/sheet.json'])['gold_gp'], 900)
        self.assertIn('characters/nik/sheet.json', again['noticed'])
        self.assertIn('edited by player', files['journal.md'])
        self.assertEqual(json.loads(files['campaign.json'])['gold_gp'], 900)

    def test_an_edited_campaign_at_the_same_revision_is_kept(self):
        result, _ = self.save()
        path = self.folder(result) / 'campaign.json'
        campaign = json.loads(path.read_text(encoding='utf-8'))
        campaign['debts'] = [{'to': 'Durnan', 'what': '5 gp for the rope'}]
        path.write_text(json.dumps(campaign), encoding='utf-8')
        again, files = self.save()
        self.assertEqual(json.loads(files['campaign.json'])['debts'], campaign['debts'])
        self.assertIn('campaign.json', again['noticed'])
        self.assertIn('Durnan', files['journal.md'])

    def test_a_higher_revision_wins_over_an_older_edit_and_says_so(self):
        result, _ = self.save()
        path = self.folder(result) / 'campaign.json'
        campaign = json.loads(path.read_text(encoding='utf-8'))
        campaign['location']['area'] = 'Somewhere I typed'
        path.write_text(json.dumps(campaign), encoding='utf-8')
        self.play('I go through the iron door.')
        again, files = self.save()
        self.assertEqual(json.loads(files['campaign.json'])['location']['area'], 'Watchroom')
        self.assertIn('campaign.json', again['noticed'])
        self.assertIn('edited by player', files['journal.md'])

    def test_an_unchanged_save_notices_nothing(self):
        self.save()
        again, files = self.save()
        self.assertEqual(again['noticed'], [])
        self.assertNotIn('edited by player', files['journal.md'])


if __name__ == '__main__':
    unittest.main()

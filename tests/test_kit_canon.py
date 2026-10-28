"""Canon status on the campaign record (campaign.json facts and campaign_log).

No dice. Every value here is fixed; the module does not read random or secrets.
Examples are an original salt-crossing table (a cog, a contract, a coffer), not a
published adventure.
"""

import ast
import contextlib
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from runtime import kit_canon, kit_save
from runtime.kit_canon import (CanonError, adopt, canon_status, handoff_text, promote, query, record,
                               render_recap, supersede)
from runtime.kit_resume import _entry, _restore
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'feasibility_room.json'


def shell():
    return {
        'schema': 'kit_campaign_v1',
        'journal_mode': 'campaign',
        'pcs': ['mira'],
        'pc': {'id': 'mira', 'name': 'Mira'},
        'location': {'room_id': 'salt-dock', 'area': 'Salt dock'},
        'export': {'revision': 4, 'saved_at': '2026-01-01T00:00:00Z', 'player': 'player', 'campaign': 'cinder'},
        'source_hashes': {},
        'npcs_met': [], 'learned': [], 'loot': [], 'debts': [], 'threads': [], 'choices': [],
        'rooms': [], 'sessions': [], 'edits': [], 'facts': [],
    }


class CanonRules(unittest.TestCase):
    def test_kits_suggestion_never_becomes_canon_because_she_said_it(self):
        campaign = shell()
        record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit')
        with self.assertRaises(CanonError):
            record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit')
        with self.assertRaises(CanonError) as caught:
            record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit',
                   status='CONFIRMED', source='she said so')
        self.assertIn('PROPOSED', str(caught.exception))
        with self.assertRaises(CanonError):
            record(campaign, 'clock', 'landfall', {'hours': 140}, by='kit', status='RESOLVED_IN_PLAY')
        self.assertEqual(query(campaign, status='CONFIRMED'), [])
        self.assertEqual(query(campaign, status='RESOLVED_IN_PLAY'), [])
        proposed = query(campaign, status='PROPOSED')
        self.assertEqual([row['key'] for row in proposed], ['cinder-rate'])
        self.assertEqual(proposed[0]['value'], {'gp_per_day': 200})
        proposed[0]['status'] = 'CONFIRMED'
        self.assertEqual(query(campaign, status='CONFIRMED'), [])

    def test_dm_adopt_promotes_and_stops_being_provisional(self):
        campaign = shell()
        record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit')
        with self.assertRaises(CanonError):
            adopt(campaign, 'cinder-rate', by='kit')
        promote(campaign, 'cinder-rate', by='dm')
        self.assertEqual(query(campaign, status='PROPOSED'), [])
        confirmed = query(campaign, status='CONFIRMED')
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]['status'], 'CONFIRMED')
        self.assertEqual(confirmed[0]['value'], {'gp_per_day': 200})
        self.assertEqual(confirmed[0]['source'], 'adopted by the DM')
        named = shell()
        record(named, 'clock', 'logbook-clock', {'hours': 12}, by='dm', status='CONFIRMED', source='ship log')
        self.assertEqual(query(named, status='PROPOSED'), [])
        self.assertEqual(query(named, status='CONFIRMED')[0]['key'], 'logbook-clock')

    def test_latest_dm_ruling_supersedes_and_keeps_the_draft_in_history(self):
        campaign = shell()
        record(campaign, 'position', 'cinder-berth', {'place': 'east pier'}, by='kit')
        supersede(campaign, 'cinder-berth', {'place': 'salt bar'}, by='kit', status='PROPOSED')
        with self.assertRaises(CanonError) as caught:
            supersede(campaign, 'cinder-berth', {'place': 'the channel'}, by='kit', status='CONFIRMED')
        self.assertIn('PROPOSED', str(caught.exception))
        self.assertEqual(query(campaign, status='CONFIRMED'), [])
        supersede(campaign, 'cinder-berth', {'place': 'north mole'}, by='dm', status='CONFIRMED',
                  source='DM ruling')
        supersede(campaign, 'cinder-berth', {'place': 'the roads'}, by='dm', status='CONFIRMED',
                  source='later DM ruling')
        current = query(campaign, key='cinder-berth')
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['value'], {'place': 'the roads'})
        self.assertEqual(current[0]['status'], 'CONFIRMED')
        self.assertEqual([item['value']['place'] for item in current[0]['history']],
                         ['east pier', 'salt bar', 'north mole'])
        self.assertEqual(query(campaign, status='PROPOSED'), [])
        self.assertNotIn('east pier', [row['value']['place'] for row in query(campaign)])

    def test_recap_labels_new_numbers_and_awards_as_proposed_rulings(self):
        campaign = shell()
        record(campaign, 'audience', 'dock-crowd', {'count': 400}, by='kit')
        record(campaign, 'award', 'harbor-medal', {'name': 'Harbor Medal'}, by='kit')
        record(campaign, 'clock', 'logbook-clock', {'hours': 12}, by='dm', status='CONFIRMED', source='ship log')
        recap = 'The clock reads 12 hours, the crowd was 400, and the medal is the Harbor Medal.'
        campaign['sessions'] = [{'revision': 4, 'turns': 1, 'recap': recap}]
        shown = render_recap(recap, campaign)
        self.assertIn('12 hours', shown)
        self.assertNotIn('12 (proposed ruling)', shown)
        self.assertNotIn('12 hours (proposed ruling)', shown)
        self.assertIn('400 (proposed ruling)', shown)
        self.assertIn('Harbor Medal (proposed ruling)', shown)
        journal = kit_save.journal_md(campaign)
        self.assertIn('400 (proposed ruling)', journal)
        self.assertIn('Harbor Medal (proposed ruling)', journal)
        self.assertIn('[PROPOSED] award harbor-medal:', journal)
        self.assertIn('[CONFIRMED] clock logbook-clock:', journal)
        text = handoff_text(campaign)
        self.assertIn('proposed ruling', text)
        self.assertIn('[PROPOSED]', text)

    def test_unopened_loot_box_is_distinct_from_later_contents(self):
        campaign = shell()
        record(campaign, 'loot_box', 'sealed-coffer', {'name': 'sealed coffer', 'opened': False}, by='play')
        with self.assertRaises(CanonError):
            record(campaign, 'loot_box', 'other-coffer',
                   {'name': 'other coffer', 'opened': False, 'items': ['spyglass']}, by='play')
        box = query(campaign, key='sealed-coffer')[0]
        contents = query(campaign, key='sealed-coffer.contents')[0]
        self.assertIs(box['value']['opened'], False)
        self.assertNotIn('items', box['value'])
        self.assertNotIn('contents', box['value'])
        self.assertEqual(contents['status'], 'UNKNOWN')
        self.assertIsNone(contents['value'])
        self.assertEqual(contents['history'], [])
        supersede(campaign, 'sealed-coffer.contents', {'items': ['spyglass']}, by='dm',
                  status='CONFIRMED', source='opened at camp')
        supersede(campaign, 'sealed-coffer', {'name': 'sealed coffer', 'opened': True}, by='play',
                  status='RESOLVED_IN_PLAY')
        box = query(campaign, key='sealed-coffer')[0]
        contents = query(campaign, key='sealed-coffer.contents')[0]
        self.assertEqual(contents['value'], {'items': ['spyglass']})
        self.assertEqual(contents['status'], 'CONFIRMED')
        self.assertIsNone(contents['history'][0]['value'])
        self.assertEqual(contents['history'][0]['status'], 'UNKNOWN')
        self.assertIs(box['value']['opened'], True)
        self.assertNotIn('items', box['value'])
        self.assertNotIn('spyglass', json.dumps(box))
        self.assertIs(box['history'][0]['value']['opened'], False)

    def test_payment_and_treasure_cannot_be_doubled_or_split(self):
        campaign = shell()
        record(campaign, 'contract', 'cinder-pay',
               {'paid': True, 'gp': 2000, 'to': 'crew', 'obligation': 'cinder-rate'}, by='play')
        with self.assertRaises(CanonError) as again:
            record(campaign, 'contract', 'cinder-pay-again',
                   {'paid': True, 'gp': 2000, 'to': 'mira', 'obligation': 'cinder-rate'}, by='play')
        self.assertIn('paid', str(again.exception).lower())
        paid = [row for row in query(campaign) if isinstance(row.get('value'), dict) and row['value'].get('paid')]
        self.assertEqual(len(paid), 1)
        self.assertEqual(paid[0]['value']['to'], 'crew')
        record(campaign, 'treasure', 'silver-compass', {'item': 'silver compass', 'holder': 'Mira'},
               by='dm', status='CONFIRMED', source='table')
        with self.assertRaises(CanonError) as split:
            record(campaign, 'treasure', 'silver-compass-copy', {'item': 'silver compass', 'holder': 'Voss'},
                   by='dm', status='CONFIRMED', source='table')
        self.assertIn('holder', str(split.exception).lower())
        supersede(campaign, 'silver-compass', {'item': 'silver compass', 'holder': 'Voss'}, by='dm',
                  status='CONFIRMED', source='handed over')
        held = query(campaign, kind='treasure')
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]['value']['holder'], 'Voss')
        self.assertEqual(held[0]['history'][0]['value']['holder'], 'Mira')

    def test_f_played_outcomes_replace_planning_without_duplicate_rewards(self):
        campaign = shell()
        record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit')
        record(campaign, 'clock', 'landfall', {'hours': 140}, by='kit')
        record(campaign, 'position', 'cinder-crew', {'count': 25}, by='kit')
        record(campaign, 'award', 'ash-coin', {'name': 'Ash Coin'}, by='kit')
        supersede(campaign, 'cinder-rate', {'gp_per_day': 2000}, by='dm', status='RESOLVED_IN_PLAY',
                  source='played at the table')
        supersede(campaign, 'landfall', {'hours': 128}, by='dm', status='RESOLVED_IN_PLAY',
                  source='played at the table')
        supersede(campaign, 'cinder-crew', {'count': 19}, by='dm', status='RESOLVED_IN_PLAY',
                  source='played at the table')
        record(campaign, 'contract', 'cinder-pay',
               {'paid': True, 'gp': 2000, 'to': 'crew', 'obligation': 'cinder-rate'}, by='play')
        with self.assertRaises(CanonError):
            record(campaign, 'contract', 'cinder-pay-2',
                   {'paid': True, 'gp': 2000, 'to': 'crew', 'obligation': 'cinder-rate'}, by='play')
        recap = ('The plan was 200 gp/day, a 140 hour clock, and a crew of 25. Award the Ash Coin.')
        campaign['sessions'] = [{'revision': 4, 'turns': 8, 'recap': recap}]
        text = handoff_text(campaign)
        journal = kit_save.journal_md(campaign)
        entry = _entry(Path('cinder'), 'folder', {'campaign.json': json.dumps(campaign)})
        for shown in (text, journal, entry['last_session']['recap']):
            self.assertIn('2,000', shown)
            self.assertIn('128', shown)
            self.assertRegex(shown, r'\b19\b')
            self.assertIsNone(re.search(r'\b200\b', shown), shown)
            self.assertIsNone(re.search(r'\b140\b', shown), shown)
            self.assertIsNone(re.search(r'\b25\b', shown), shown)
            self.assertIn('Ash Coin (proposed ruling)', shown)
        self.assertIn('[PROPOSED] award ash-coin:', text)
        self.assertNotIn('[RESOLVED_IN_PLAY] award ash-coin', text)
        self.assertNotIn('[CONFIRMED] award ash-coin', text)
        self.assertEqual(text.count('cinder-pay'), 1)
        paid = [row for row in query(campaign) if isinstance(row.get('value'), dict) and row['value'].get('paid')]
        self.assertEqual(len(paid), 1)
        self.assertNotIn('Ash Coin', json.dumps(paid))
        self.assertEqual(query(campaign, key='cinder-rate')[0]['history'][0]['value']['gp_per_day'], 200)
        self.assertEqual(query(campaign, key='landfall')[0]['value']['hours'], 128)
        self.assertEqual(query(campaign, key='cinder-crew')[0]['value']['count'], 19)

    def test_missing_status_on_an_old_save_is_read_not_invented(self):
        doc = kit_canon.__doc__
        save_doc = (ROOT / 'docs' / 'architecture' / 'PLAYER_SAVE.md').read_text(encoding='utf-8')
        for phrase in ('no status reads as PROPOSED', 'read as CONFIRMED', 'RESOLVED_IN_PLAY',
                       'UNKNOWN is never inferred'):
            self.assertIn(phrase, doc)
            self.assertIn(phrase, save_doc)
        old = shell()
        del old['facts']
        old['loot'] = [{'item': 'rope', 'room_id': 'salt-dock'}]
        old['npcs_met'] = [{'name': 'Voss', 'status': 'alive', 'room_id': 'salt-dock'}]
        old['learned'] = [{'text': 'The tide turns at dusk.', 'room_id': 'salt-dock'}]
        old['debts'] = [{'to': 'harbor', 'what': '2 gp'}]
        old['threads'] = []
        old['rooms'] = [{'room_id': 'salt-dock', 'status': 'left'}]
        self.assertEqual(canon_status(old['loot'][0], 'loot'), 'RESOLVED_IN_PLAY')
        self.assertEqual(canon_status(old['npcs_met'][0], 'npcs_met'), 'RESOLVED_IN_PLAY')
        self.assertEqual(canon_status(old['debts'][0], 'debts'), 'CONFIRMED')
        self.assertEqual(canon_status(old['rooms'][0], 'rooms'), 'RESOLVED_IN_PLAY')
        bare = {'kind': 'clock', 'key': 'tide', 'value': {'hours': 6}, 'current': True}
        old['facts'] = [bare]
        self.assertEqual(canon_status(bare, 'facts'), 'PROPOSED')
        self.assertEqual(query(old, key='tide')[0]['status'], 'PROPOSED')
        self.assertEqual(query(old, key='tide')[0]['history'], [])
        self.assertEqual(query(old, status='RESOLVED_IN_PLAY', include_legacy=True)[0]['kind'], 'learned')
        self.assertTrue(any(row['kind'] == 'debts' and row['status'] == 'CONFIRMED'
                            for row in query(old, status='CONFIRMED', include_legacy=True)))
        self.assertEqual(render_recap('Nik went down the stair.', old), 'Nik went down the stair.')
        with self.assertRaises(CanonError):
            record(old, 'npc', 'voss-youth', {'past': 'born on a farm inland'}, status='UNKNOWN', by='dm')
        record(old, 'npc', 'voss-youth', None, status='UNKNOWN', by='dm')
        youth = query(old, key='voss-youth')[0]
        self.assertEqual(youth['status'], 'UNKNOWN')
        self.assertIsNone(youth['value'])
        self.assertEqual(youth['history'], [])
        self.assertNotIn('farm', json.dumps(youth))
        restored = _restore({'rooms': [], 'loot': []}, 'salt-dock')
        self.assertNotIn('facts', restored['log'])
        restored = _restore(old, 'other-room')
        self.assertEqual(restored['log']['facts'][0]['key'], 'tide')
        fresh = shell()
        fresh['export'] = {'revision': 5, 'saved_at': '2026-01-02T00:00:00Z'}
        fresh['facts'] = []
        fresh['sessions'] = [{'revision': 5}]
        kept = kit_save.merge(fresh, old, False, None)
        self.assertEqual(kept['facts'][0]['key'], 'tide')
        self.assertEqual(canon_status(kept['facts'][0], 'facts'), 'PROPOSED')
        edited = shell()
        edited['export'] = {'revision': 5}
        edited['facts'] = [{'kind': 'clock', 'key': 'tide', 'value': {'hours': 6}, 'status': 'CONFIRMED',
                            'source': 'player edit', 'current': True, 'history': []}]
        edited['sessions'] = [{'revision': 5}]
        stood = kit_save.merge(fresh, edited, True, None)
        self.assertEqual(stood['facts'][0]['status'], 'CONFIRMED')

    def test_facts_ride_the_save(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Path(temp.name) / 'kit.sqlite'
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads(FIXTURE.read_text(encoding='utf-8')), 'entry')
        campaign = shell()
        record(campaign, 'contract', 'cinder-rate', {'gp_per_day': 200}, by='kit')
        promote(campaign, 'cinder-rate', by='dm', source='used at the table')
        kit_canon.commit_runtime(runtime, campaign, 'campaign-facts')
        _revision, state = runtime.load()
        self.assertEqual(state['campaign_log']['facts'][0]['status'], 'CONFIRMED')
        self.assertEqual(state['campaign_log']['facts'][0]['key'], 'cinder-rate')
        result = kit_save.save(str(db), journal_mode='campaign')
        with zipfile.ZipFile(result['zip']) as archive:
            saved = json.loads(archive.read('campaign.json').decode('utf-8'))
            journal = archive.read('journal.md').decode('utf-8')
        self.assertEqual(saved['facts'][0]['status'], 'CONFIRMED')
        self.assertIn('[CONFIRMED] contract cinder-rate:', journal)
        self.assertIn('## Campaign record', journal)

    def test_cli_record_and_query_round_trip(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = str(Path(temp.name) / 'campaign.json')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = kit_canon.main(['record', '--file', path, '--kind', 'clock', '--key', 'landfall',
                                   '--value', '{"hours": 140}', '--by', 'kit'])
        self.assertEqual(code, 0)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(kit_canon.main(['record', '--file', path, '--kind', 'clock', '--key', 'landfall',
                                             '--value', '{"hours": 140}', '--by', 'kit']), 1)
        self.assertIn('already recorded', err.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(kit_canon.main(['query', '--file', path, '--status', 'PROPOSED']), 0)
        rows = json.loads(out.getvalue())
        self.assertEqual(rows[0]['key'], 'landfall')
        self.assertEqual(rows[0]['status'], 'PROPOSED')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(kit_canon.main(['query', '--file', path, '--status', 'CONFIRMED']), 0)
        self.assertEqual(json.loads(out.getvalue()), [])

    def test_module_uses_no_unpinned_randomness(self):
        tree = ast.parse((ROOT / 'runtime' / 'kit_canon.py').read_text(encoding='utf-8'))
        names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
        self.assertNotIn('random', names)
        self.assertNotIn('secrets', names)


if __name__ == '__main__':
    unittest.main()

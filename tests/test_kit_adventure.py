"""Adventure ingestion (runtime/kit_adventure.py, docs/architecture/ADVENTURE_INGESTION.md).

Corpus: tests/fixtures/adventures/lantern_ferry.txt, a short ORIGINAL synthetic adventure
written for these tests (no published text). The headline is a scripted transition: start in
compiled location 1, walk to location 2, and location 2 mounts from its just-in-time compiled
room with no host step; back to 1, then to location 4, compiled on demand by the loader."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_lifecycle  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import Runtime  # noqa: E402

CORPUS = ROOT / 'tests/fixtures/adventures/lantern_ferry.txt'
NIK = ROOT / 'tests/fixtures/characters/nik.json'


class Base(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'kit.sqlite'
        self.text = CORPUS.read_text(encoding='utf-8')
        self.report = kit_adventure.import_adventure(self.db, text=self.text)
        self.index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text())


class Index(Base):
    def test_index_finds_chapters_locations_npcs_and_stat_blocks(self):
        self.assertEqual(list(self.index['locations']), ['1', '2', '3', '4'])
        self.assertEqual(self.index['locations']['2']['name'], 'Tollhouse')
        self.assertEqual(len(self.index['chapters']), 2)  # chapter 1 and the appendix
        self.assertIn('Oswin Tarr', self.index['npcs'])
        self.assertIn('lantern wight', self.index['stat_blocks'])
        loc = self.index['locations']['1']
        self.assertEqual(self.text[loc['offset']:].split('\n')[0], '1. Ferry Landing')

    def test_connections_are_two_way_and_secret_hatch_is_secret(self):
        links = {k: {c['to']: c['secret'] for c in v['connections']} for k, v in self.index['locations'].items()}
        self.assertEqual(links['1'], {'2': False, '4': False})
        self.assertTrue(links['2']['3'])
        self.assertIn('1', links['4'])

    def test_map_pages_are_flagged(self):
        self.assertEqual(self.index['map_pages'], [2])

    def test_creatures_resolve_book_then_srd_then_ask(self):
        how = {c['name']: c['resolved'] for c in self.index['locations']['3']['creatures']}
        self.assertEqual(how, {'lantern wight': 'in_book', 'marsh hag': 'ask_player'})
        how = {c['name']: c['resolved'] for c in self.index['locations']['2']['creatures']}
        self.assertEqual(how['bandit'], 'srd')

    def test_source_stays_private_and_ignored(self):
        self.assertTrue((kit_adventure.folder_for(self.db) / 'source.txt').is_file())
        self.assertIn('*.adventure/', (ROOT / '.gitignore').read_text())

    def test_no_locations_is_refused(self):
        with self.assertRaises(kit_adventure.IngestError):
            kit_adventure.import_adventure(self.folder / 'x.sqlite', text='Just some prose.\n')


class Compile(Base):
    def test_compile_caches_and_precompiles_neighbours(self):
        out = kit_adventure.compile_location(self.db, '1')
        self.assertEqual(sorted(out['precompiled']), ['2', '4'])
        self.assertEqual(out['adventure_readiness'], 'location_executable')
        self.assertTrue(kit_adventure.room_file(self.db, '2').is_file())
        self.assertFalse(kit_adventure.room_file(self.db, '3').is_file())

    def test_secrets_stay_hidden(self):
        kit_adventure.compile_location(self.db, '1', neighbours=False)
        room = json.loads(kit_adventure.room_file(self.db, '1').read_text())
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        hidden = ' '.join(f['text'] for f in room['facts'].values() if not f['visible'])
        self.assertIn('rope bell', visible)
        self.assertNotIn('DC 12', visible)
        self.assertNotIn('three silver', visible)
        self.assertIn('DC 12', hidden)

    def test_every_field_has_provenance_that_quotes_the_source(self):
        kit_adventure.compile_location(self.db, '2', neighbours=False)
        path = kit_adventure.room_file(self.db, '2')
        room, side = json.loads(path.read_text()), json.loads(path.with_suffix('.provenance.json').read_text())
        for key in room['facts']:
            entry = side['fields'][f'facts.{key}']
            self.assertEqual(self.text[entry['offset']:entry['offset'] + len(entry['quote'])], entry['quote'])
        self.assertTrue(room['exits']['way_3']['secret'])

    def test_ask_player_for_stat_blocks_the_book_lacks(self):
        out = kit_adventure.compile_location(self.db, '3', neighbours=False)
        self.assertEqual(out['ask_player'], ['marsh hag'])

    def _draft(self):
        return kit_adventure.draft_room(self.db, '1', self.index, self.text)

    def test_host_draft_is_validated_by_the_runtime(self):
        room, side = self._draft()
        out = kit_adventure.compile_location(self.db, '1', draft={'room': room, 'provenance': side}, neighbours=False)
        self.assertEqual(out['compiled_by'], 'host_draft')

    def test_host_draft_field_without_source_is_rejected(self):
        room, side = self._draft()
        room['facts']['invented'] = {'area': 'here', 'visible': True, 'text': 'A dragon sleeps on the ferry.'}
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.compile_location(self.db, '1', draft={'room': room, 'provenance': side})
        self.assertIn('facts.invented has no source quote and offset', caught.exception.problems)

    def test_host_draft_cannot_invent_beyond_its_quote_or_leak_a_secret(self):
        room, side = self._draft()
        room['facts']['seen_1']['text'] = 'Rain hisses on a tarred plank landing guarded by an ogre.'
        dm = next(k for k, f in room['facts'].items() if 'DC 12' in f['text'])
        room['facts'][dm]['visible'] = True
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.compile_location(self.db, '1', draft={'room': room, 'provenance': side})
        problems = ' '.join(caught.exception.problems)
        self.assertIn('says more than its quote', problems)
        self.assertIn('quotes DM-only text', problems)

    def test_host_draft_quote_from_another_location_is_rejected(self):
        room, side = self._draft()
        side['fields']['facts.seen_1'] = {'offset': 0, 'quote': 'A ledger lies open on a high desk beside a cold stove.'}
        room['facts']['seen_1']['text'] = 'A ledger lies open on a high desk beside a cold stove.'
        with self.assertRaises(kit_adventure.IngestError):
            kit_adventure.compile_location(self.db, '1', draft={'room': room, 'provenance': side})


class Transition(Base):
    """Scripted: room A (location 1) -> room B (location 2) -> back to A -> location 4,
    which the loader compiles on demand. No host step between rooms."""

    def test_a_to_b_and_on(self):
        kit_adventure.compile_location(self.db, '1')
        self.assertEqual(kit_lifecycle.status(self.db)['next_command'].split(' --room ')[0],
                         f'python3 -m runtime.kit_agent start --db {self.db}')
        started = start_session(self.db, NIK, room=kit_adventure.room_file(self.db, '1'))
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10)
        bridge = KitChatBridge(runtime, adjudicator)
        if not started.get('committed'):
            bridge.abandon(started['prepared']['turn_id'])
        self.assertEqual(kit_lifecycle.status(self.db)['adventure']['adventure_readiness'], 'campaign_playable')

        def step(line):
            revision, _ = runtime.load()
            packet = bridge.prepare(line, one_pass=True)
            body = runtime.pending_kit_turn(packet['turn_id'])['body']
            bridge.abandon(packet['turn_id'])
            runtime.commit(packet['turn_id'], revision, body['events'])
            return runtime.source()['id'], runtime.load()[1]['area']

        sha = self.index['sha256'][:8]
        self.assertEqual(step('I go to the Tollhouse.'), (f'adv-{sha}-2', 'to_1'))  # B mounted
        self.assertEqual(step('I go into the Tollhouse.'), (f'adv-{sha}-2', 'here'))
        # The secret hatch is a secret exit: the PC does not know it, so naming it moves nothing.
        self.assertEqual(step('I take the way to Smugglers Cellar.'), (f'adv-{sha}-2', 'here'))
        self.assertEqual(step('I go to the Ferry Landing.'), (f'adv-{sha}-1', 'to_2'))  # A restored
        kit_adventure.room_file(self.db, '4').unlink()  # not cached: the loader compiles it on demand
        self.assertEqual(step('I go into the Ferry Landing.'), (f'adv-{sha}-1', 'here'))
        self.assertEqual(step('I go to the Far Shore.'), (f'adv-{sha}-4', 'to_1'))
        self.assertTrue(kit_adventure.room_file(self.db, '4').is_file())

    def test_cli_import_compile_status(self):
        run = lambda *a: subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *a], cwd=ROOT,  # noqa: E731
                                        capture_output=True, text=True)
        db = str(self.folder / 'cli.sqlite')
        out = json.loads(run('adventure', 'import', '--db', db, '--text-file', str(CORPUS)).stdout)
        self.assertEqual(out['adventure_readiness'], 'source_available')
        out = json.loads(run('adventure', 'compile', '--db', db, '--location', '1').stdout)
        self.assertEqual(out['adventure_readiness'], 'location_executable')
        out = json.loads(run('status', '--db', db).stdout)
        self.assertEqual(out['adventure']['adventure_readiness'], 'location_executable')
        bad = run('adventure', 'compile', '--db', db, '--location', '99')
        self.assertEqual(bad.returncode, 2)


class Combatants(Base):
    """Creatures compile into actors the existing combat engine fights: the book's own stat block
    first, then SRD 5.1, else ask_player and no combatant."""

    def room(self, key):
        kit_adventure.compile_location(self.db, key, neighbours=False)
        path = kit_adventure.room_file(self.db, key)
        return json.loads(path.read_text()), json.loads(path.with_suffix('.provenance.json').read_text())

    def test_book_stat_block_becomes_an_inline_combatant(self):
        room, side = self.room('3')
        self.assertEqual(room['actors']['lantern_wight']['stat_block'],
                         {'ac': 13, 'hp': 27, 'attacks': [{'name': 'lantern lash', 'to_hit': 4, 'damage': 6, 'type': 'fire'}]})
        self.assertEqual(side['fields']['actors.lantern_wight.stat_block.ac']['quote'], 'Armor Class 13')
        self.assertNotIn('marsh_hag', room['actors'])  # ask_player: no combatant
        self.assertIn('marsh hag', side['ask_player'])

    def test_srd_creatures_and_counts(self):
        room, _ = self.room('2')
        self.assertEqual(sorted(room['actors']), ['bandit_1', 'bandit_2'])
        self.assertEqual(room['actors']['bandit_1']['stat_block'], {'srd': 'bandit'})
        self.assertNotIn('lantern_wight', room['actors'])  # a passing mention in the ledger

    def test_unsupported_features_are_flagged(self):
        room, side = self.room('4')
        self.assertEqual(len(room['actors']['reed_lurker']['stat_block']['attacks']), 2)
        self.assertTrue(any('Multiattack' in f and 'Recharge' in f for f in side['flags']))

    def _draft(self, key='3'):
        return kit_adventure.draft_room(self.db, key, self.index, self.text)

    def test_a_stat_without_a_source_is_rejected(self):
        room, side = self._draft()
        room['actors']['lantern_wight']['stat_block']['hp'] = 40
        room['actors']['lantern_wight']['stat_block']['initiative'] = 3
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.compile_location(self.db, '3', draft={'room': room, 'provenance': side})
        problems = ' '.join(caught.exception.problems)
        self.assertIn('stat_block.hp states a number its quote does not', problems)
        self.assertIn('unsourced fields: initiative', problems)

    def test_an_invented_creature_is_rejected(self):
        room, side = self._draft()
        room['actors']['ogre'] = {'name': 'Ogre', 'location': 'here', 'status': 'alive', 'visible': True,
                                  'stat_block': {'srd': 'ogre'}}
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.compile_location(self.db, '3', draft={'room': room, 'provenance': side})
        self.assertIn('actors.ogre has no source quote in this location', caught.exception.problems)

    def _session(self, key):
        kit_adventure.compile_location(self.db, key, neighbours=False)
        started = start_session(self.db, NIK, room=kit_adventure.room_file(self.db, key))
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=runtime.source())
        if not started.get('committed'):
            KitChatBridge(runtime, adjudicator).abandon(started['prepared']['turn_id'])

        def act(line):
            revision, state = runtime.load()
            result = adjudicator.resolve(line, revision, state)
            runtime.commit(f't{revision}', revision, list(result.events))
            return result, runtime.load()[1].get('combat') or {}
        return started, runtime, act

    @staticmethod
    def _public(started):
        """Everything in the start packet except the DM-only context."""
        packet = json.loads(json.dumps(started))
        packet['prepared']['input']['private'].pop('dm_context', None)
        return json.dumps(packet).lower()

    def test_creatures_not_in_read_aloud_text_start_hidden(self):
        for key in '234':
            room, side = self.room(key)
            for akey, actor in room['actors'].items():
                self.assertEqual((actor['status'], actor['visible']), ('hidden', False), akey)
            woken = {a for t in room['triggers'] for a in t['actors']}
            self.assertEqual(woken, set(room['actors']))
            for t in room['triggers']:
                self.assertIn(f"triggers.{t['id']}", side['fields'])

    def test_back_room_bandits_wait_for_the_ledger(self):
        room, _ = self.room('2')
        trigger, = room['triggers']
        ledger = trigger['on']['disturb']
        self.assertIn('ledger', room['facts'][ledger]['text'])
        self.assertEqual(room['facts'][ledger]['handling'], {'nouns': ['ledger']})
        started, runtime, act = self._session('2')
        act('I look around the tollhouse.')  # entering does not wake them
        self.assertNotIn('bandit', self._public(started))
        self.assertNotIn('bandit', json.dumps(runtime.player_view()).lower())
        self.assertEqual(runtime.load()[1]['actors']['bandit_1']['status'], 'hidden')

    def test_ambusher_is_unnamed_until_revealed_then_fights(self):
        started, runtime, act = self._session('4')
        self.assertNotIn('lurker', self._public(started))
        self.assertNotIn('lurker', json.dumps(runtime.player_view()).lower())
        result, combat = act('I wade into the shallows.')
        self.assertEqual(combat['status'], 'awaiting_initiative')  # the trigger fired: revealed
        self.assertIn('lurker', json.dumps(runtime.player_view()).lower())
        act('Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`')
        result, combat = act('I hit the Reed Lurker with Fire Bolt.\nNik casts Fire Bolt!\n'
                             '**To Hit**: 1d20 (12) + 7 = `19`\n**Damage**: 2d10 (4, 5) [fire] = `9`')
        self.assertEqual(combat['hp']['reed_lurker'], 13)  # 22 from the book, minus 9

    def test_a_fight_in_a_compiled_room_runs_on_the_engine(self):
        started, runtime, act = self._session('3')
        self.assertNotIn('wight', self._public(started))
        act('I look around the cellar.')  # the wight shows itself: its trigger fires
        act('Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`')
        result, combat = act('I hit the Lantern Wight with Fire Bolt.\nNik casts Fire Bolt!\n'
                             '**To Hit**: 1d20 (12) + 7 = `19`\n**Damage**: 2d10 (4, 5) [fire] = `9`')
        self.assertEqual(combat['hp']['lantern_wight'], 18)  # 27 from the book, minus 9
        self.assertEqual(combat['awaiting']['attacker'], 'lantern_wight')  # the wight swings back
        self.assertEqual(combat['awaiting']['name'], 'lantern lash')
        seen = json.dumps(runtime.player_view())
        for secret in ('to_hit', 'stat_block', 'Armor Class', '"ac"'):
            self.assertNotIn(secret, seen)


class NoPublishedText(unittest.TestCase):
    def test_corpus_is_marked_original(self):
        self.assertIn('original synthetic test text', CORPUS.read_text())


if __name__ == '__main__':
    unittest.main()

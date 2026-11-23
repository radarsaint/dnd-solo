"""A one-way indexed connection needs a real arrival, not an invented reverse exit."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime import kit_adventure as a,kit_rooms
from runtime.kit_agent import prepare_opening
from runtime.state_context import Runtime

TEXT=('1. Landing\n> A lantern stands by the stair.\nA passage leads to area 2.\n'
      '2. Gallery\n> Painted shields hang above an empty bench.\n')

class OneWayArrival(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/'kit.sqlite';a.import_adventure(self.db,text=TEXT)
        a.compile_location(self.db,'1');self.origin=kit_rooms.load_room(a.room_file(self.db,'1'))
        self.link=self.origin['areas']['to_2']['room_link']

    def test_compiler_uses_existing_destination_area_without_reverse_exit(self):
        self.assertEqual(self.link['area'],'here')
        target=kit_rooms.load_link(self.link)
        self.assertNotIn('to_1',target['areas'])
        self.assertFalse(target['exits'])

    def test_legacy_cached_anchor_resolves_only_with_pinned_identity(self):
        legacy=copy.deepcopy(self.link);legacy['area']='to_1'
        before=Path(legacy['room']).read_bytes();target=kit_rooms.load_link(legacy)
        self.assertEqual(a.resolved_arrival(legacy,target),'here')
        self.assertEqual(legacy['area'],'to_1')
        self.assertEqual(Path(legacy['room']).read_bytes(),before)
        for change in ('area','sha','path','identity'):
            link=copy.deepcopy(legacy);room=copy.deepcopy(target)
            if change=='area':link['area']='to_unknown'
            elif change=='sha':link['adventure']['source_sha256']='0'*64
            elif change=='path':link['room']=str(Path(legacy['room']).parent/'different.json')
            else:room['id']='unrelated-room'
            with self.subTest(change=change):self.assertEqual(a.resolved_arrival(link,room),link['area'])

    def test_generic_broken_room_link_still_refuses(self):
        wrong=copy.deepcopy(self.link);wrong.pop('adventure');wrong['area']='to_1'
        with self.assertRaises(kit_rooms.RoomMountError):kit_rooms.load_link(wrong)

    def test_first_entry_uses_room_history_not_previous_room_turn(self):
        target=kit_rooms.load_link(self.link);r=Runtime(Path(self.db).parent/'entry.sqlite')
        self.addCleanup(r.close);r.initialize(target,'here',room_path=self.link['room'])
        with patch.object(r,'latest_kit_turn_id',return_value='previous-room-turn'):
            prepared=prepare_opening(r,one_pass=True)
        self.assertEqual(prepared[1]['kind'],'opening')

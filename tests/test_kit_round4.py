"""Round 4 structure. Synthetic text only. A fused tip is never the opening."""
import json
import tempfile
import unittest
import warnings
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_labels  # noqa: E402
from runtime.kit_agent import (assign_roll_call_policy, check_combined_call, check_reveal_text,
                               start_session)  # noqa: E402
from runtime.state_context import InvalidChange  # noqa: E402

NIK = ROOT / 'tests/fixtures/characters/nik.json'

TIP = """\
PART 1: THE NORTH ROAD

The North Road
When you're ready, read the boxed text: The wagon stops in the ruts under the trees.
> A clean second line sits on the road after the tip.

1. Cave Mouth
You stand at a dark cave mouth. The track leads to area 2.
"""

FRONT = """\
THE SAMPLE

Credits
Printed for the table and nobody else.

Contents
A list of what follows.

Encounter 1: The Gate
> Mira says the gate is shut and waves you through.
The oak door is barred. The path leads to encounter 2.

Encounter 2: The Yard
A clerk sits in the yard. The path leads back to encounter 1.
"""

CHAIN = """\
PART 1: THE MARCH

First Light
The camp stirs as first light reaches the trees and the wagon is packed.

Camp
A cookfire burns low and the track leads on toward the road.

The Road
The road runs east and the track leads back to camp.
"""

FEATURES = """\
PART 1: THE CRAWL

General Features
The lower levels are darker and the rest of the dungeon is not this room.

History
Old wars are not a scene the party is standing in.

The Patrol
> You meet the patrol on the road before the gate.
The lane leads to area 1.

1. The Gate
The gate is shut. The path leads to area 2.

2. The Yard
A yard sits past the gate. The path leads back to area 1.
"""

CHECK = """\
PART 1: THE TRACK

The Track
> The road is empty and the ruts are old.
Check: a close look finds fresh ruts in the mud.
The track leads to area 1.

1. The Post
A post stands by the road. The track leads back.
"""


def _answer(request, audience='player'):
    opening = request['opening_block']
    blocks = {}
    for block in request['blocks']:
        blocks[block['id']] = {
            'audience': 'dm' if block.get('fused') else audience,
            'kind': block['kind'],
            'scene': block['scene'],
            'opening': block['id'] == opening,
        }
    return {'section': request['section'], 'section_mode': 'regional',
            'opening_block': opening, 'blocks': blocks}


class Round4(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'

    def test_a_tip_is_cut_before_the_box_and_cannot_open(self):
        report = kit_adventure.ingest_adventure(self.db, text=TIP)
        request = report['label_request']
        texts = [block['text'].casefold() for block in request['blocks']]
        self.assertTrue(any('wagon stops' in text and 'when you' not in text for text in texts), texts)
        self.assertTrue(all(not block.get('fused') or 'wagon stops' not in block['text'].casefold()
                            for block in request['blocks']))
        self.assertNotIn('when you', request['blocks'][
            next(i for i, block in enumerate(request['blocks']) if block['id'] == request['opening_block'])
        ]['text'].casefold())
        done = kit_labels.accept(self.db, _answer(request))
        self.assertEqual(done['stage'], 'labels_frozen', done)
        heard = ' '.join(done['player_hears']).casefold()
        self.assertIn('wagon stops', heard)
        self.assertNotIn("when you're ready", heard)
        self.assertLessEqual(len(request['blocks']), 20)
        self.assertLessEqual(sum(len(block['text'].encode()) for block in request['blocks']), 6000)

    def test_front_matter_is_not_a_label_call(self):
        report = kit_adventure.ingest_adventure(self.db, text=FRONT)
        request = report['label_request']
        blob = ' '.join(block['text'] for block in request['blocks']).casefold()
        self.assertNotIn('printed for the table', blob)
        self.assertNotIn('a list of what follows', blob)
        self.assertIn('mira', blob)
        self.assertLessEqual(len(request['blocks']), 20)

    def test_a_label_call_never_sends_a_hundred_blocks(self):
        paras = '\n\n'.join('You walk the lane and count the stones at marker %d.' % n for n in range(40))
        text = 'PART 1: THE LANE\n\nThe Lane\n' + paras + '\n\n1. The End\nA last room. The lane leads back.\n'
        report = kit_adventure.ingest_adventure(self.db, text=text)
        request = report['label_request']
        self.assertLessEqual(len(request['blocks']), 20)
        self.assertLessEqual(sum(len(block['text'].encode()) for block in request['blocks']), 6000)
        self.assertGreater(len(request['blocks']), 0)

    def test_features_and_history_are_sidebars_and_the_patrol_opens(self):
        report = kit_adventure.ingest_adventure(self.db, text=FEATURES)
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        start = index['locations'][index['start']]
        self.assertIn('patrol', (start.get('name') or '').casefold())
        request = report['label_request']
        blob = ' '.join(block['text'] for block in request['blocks']).casefold()
        self.assertNotIn('lower levels', blob)
        self.assertNotIn('old wars', blob)
        self.assertTrue(all(block.get('scene') for block in request['blocks']))

    def test_scenes_and_no_numbered_places_open_with_the_sheet(self):
        report = kit_adventure.ingest_adventure(self.db, text=CHAIN)
        self.assertTrue(str(report['start_location']).startswith('scene:'))
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'started')
        self.assertTrue(opened.get('character_loaded'))
        self.assertNotEqual(opened.get('stage'), 'greeting')
        self.assertIn('camp', (opened.get('spoken') or '').casefold())

    def test_a_speaker_is_a_stub_and_a_door_is_not(self):
        report = kit_adventure.ingest_adventure(self.db, text=FRONT)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        names = [actor.get('name', '').casefold() for actor in room['actors'].values()]
        self.assertIn('mira', names)
        self.assertTrue(all(not name.startswith('oak') and name != 'door' for name in names), names)
        self.assertLessEqual(len([actor for actor in room['actors'].values() if actor.get('role') == 'speaker']), 4)
        mira = next(actor for actor in room['actors'].values() if actor.get('name', '').casefold() == 'mira')
        self.assertEqual(mira.get('role'), 'speaker')
        self.assertNotIn('stat_block', mira)

    def test_a_check_reveal_is_the_check_row_not_the_opening(self):
        report = kit_adventure.ingest_adventure(self.db, text=CHECK)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        rows = [fact for fact in room['facts'].values() if str(fact.get('row') or '').startswith('check')]
        self.assertTrue(rows, room['facts'])
        self.assertIn('fresh ruts', rows[0]['text'].casefold())
        self.assertNotIn('road is empty', rows[0]['text'].casefold())
        cited = check_reveal_text(room, room['areas']['here'] and 'here')
        self.assertIn('fresh ruts', cited.casefold())
        self.assertNotIn('road is empty', cited.casefold())

    def test_roll_call_policy_stays_frozen(self):
        body = {'kind': 'check_request', 'public_view': {'area': 'here'}}
        source = {'id': 'adv-abcdef12-road', 'facts': {}}
        self.assertEqual(assign_roll_call_policy(body, source), 'clarify')
        body['kind'] = 'check_request'
        source['facts'] = {'seen_1': {'area': 'here', 'row': 'check_1', 'text': 'Fresh ruts.', 'visible': True}}
        self.assertEqual(assign_roll_call_policy(body, source), 'clarify')
        plan = {'roll_call': {'skill': 'perception'}}
        with self.assertRaises(InvalidChange):
            check_combined_call([{'text': 'What do you see?'}], plan, 'check_request', 'clarify')
        check_combined_call([{'text': 'What do you see?'}], {}, 'check_request', 'clarify')

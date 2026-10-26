"""Kit II's pr150d run (#150 at 3967def), end to end on a synthetic bunk room
(tests/fixtures/rooms/bunkroom.json): every phrasing goes through KitChatBridge.prepare and,
with a stubbed Kit, complete. Mirrors #159's fuzz corpus cases (tests/corpus there) so they
live in this branch's own suite until #159 lands."""
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session
from runtime.state_context import InvalidChange, Runtime
from kit_policy import rejections_raise
from test_kit_agent import RecordingModel

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / 'tests/fixtures/rooms/bunkroom.json'
SHEET = ROOT / 'tests/fixtures/characters/nik.json'

# (line, engine action kind or None for a refusal, ruling allowed)
CASES = (
    ('Detect Magic, not as a ritual, I let my senses open on the room.', 'spell_cast'),
    ('Detect Magic. Not a ritual, I spend the slot.', 'spell_cast'),
    ('I use detect magic on the room.', 'spell_cast'),
    ("I go through the beds one by one, looking for whatever's humming.", 'check_request'),
    ('I go through the bedding, hunting for anything hidden.', 'check_request'),
    ('I rummage through the straw looking for loot.', 'check_request'),
    ("I push on the seam to get the hidden door open, but I don't go in. I just stand back and peek down "
     'the tunnel.', 'kit_ruling'),
    ('I shove the seam with my shoulder, then peer down the tunnel without going in.', ('kit_ruling', 'check')),
    ('I tap the floor ahead with my staff.', 'observe'),
)


def plan_for(private):
    plan = RecordingModel().plan(private)
    plan.update({'move': 'world_description', 'table_presence': 'quiet', 'focus_actor': 'none'})
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    if (private.get('acts') or {}).get('handles'):
        plan['handles'] = {'target': 'none', 'act': 'none', 'reason': kit_agent.kit_acts.NONE_REASONS[0]}
    return plan


FILLERS = (
    ('The air is still and cool, and dust drifts slowly through the light around you. Somewhere above, old '
     'timbers settle with a soft creak.',
     'Your own breath sounds loud here, and the shadows in the corners do not move. For a long moment nothing '
     'changes, and the place seems to wait.'),
    ('Straw rustles somewhere behind you, then falls silent. A draft from the east wall carries the smell of '
     'damp earth and old smoke.',
     'Far off, water drips onto stone in a slow, patient rhythm. The carved eyes of the standing stone keep '
     'their blank watch over the room.'),
)


def narration(*texts, variant=0):
    first = ' '.join(texts) or 'You take it in.'
    one, two = FILLERS[variant % len(FILLERS)]
    return {'segments': [{'speaker': 'Narrator', 'text': f'{first} {one}'}, {'speaker': 'Narrator', 'text': two}]}


class BunkRoom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / 'base.sqlite'
        started = start_session(cls.base, SHEET, room=str(ROOM))
        runtime = Runtime(cls.base)
        KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])
        runtime.close()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        db = Path(self.temp.name) / f'{self.id()}.sqlite'
        shutil.copyfile(self.base, db)
        self.runtime = Runtime(db)
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 2, npc_roll=lambda: 2))

    def commit(self, events):
        revision, _ = self.runtime.load()
        self.runtime.commit('setup', revision, events)

    def call(self, skill, target, dc=None):
        check = {'skill': skill, 'ability': 'wis' if skill == 'perception' else 'int', 'target': target,
                 'called_turn': 'setup'}
        if dc is not None:
            check['dc'] = dc
        self.commit([{'type': 'pending_check', 'check': check, 'evidence': 'Kit called the check.'}])

    def turn(self, line, *texts):
        self.turns = getattr(self, 'turns', 0) + 1
        packet = self.bridge.prepare(line, f'turn-{self.turns}', one_pass=True)
        public = packet['input']['public']
        result = self.bridge.complete(packet['turn_id'], {'decision': plan_for(packet['input']['private']),
                                                          'performance': narration(*texts, variant=self.turns)})
        return public, packet['input']['private'], result

    def test_every_phrasing_end_to_end(self):
        for line, kind in CASES:
            with self.subTest(line):
                self.setUp()
                public, _, _ = self.turn(line)
                self.assertIn(public['action_kind'], kind if isinstance(kind, tuple) else (kind,))

    def test_a_peek_down_a_named_exit_after_a_hands_on_act_is_not_a_look_there(self):
        public, _, _ = self.turn("I push on the seam, but I don't go in. I peek down the tunnel.")
        self.assertNotEqual(public['action_kind'], 'threshold_look')
        self.assertNotIn('tunnel mouth', public['accepted_public_event'])

    def test_a_plain_peek_down_the_tunnel_is_still_a_threshold_look(self):
        public, _, _ = self.turn("I don't go in. I peek down the tunnel.")
        self.assertEqual(public['action_kind'], 'threshold_look')

    def test_a_simple_act_is_not_read_back_whole(self):
        line = 'I tap the floor ahead with my staff, slowly, one board at a time.'
        public, _, _ = self.turn(line)
        self.assertEqual(public['accepted_public_event'], kit_agent.SIMPLE_ACT_LINE)
        self.assertNotIn('one board at a time', public['accepted_public_event'])

    def test_detect_magic_private_place_has_no_doubled_at(self):
        _, private, _ = self.turn('I cast detect magic.')
        self.assertNotIn('at at', str(private))
        self.assertIn('at the north end', str(private))

    def test_a_passed_called_search_finds_what_the_bed_holds(self):
        self.call('investigation', 'beds', dc=12)
        public, _, _ = self.turn('Investigation 27')
        state = self.runtime.load()[1]
        self.assertIn('potion', state.get('known_facts') or [])
        self.assertNotIn('ruby', public['accepted_public_event'])  # the reveal is the engine's, not echoed

    def test_a_failed_called_search_finds_nothing(self):
        self.call('investigation', 'beds', dc=12)
        self.turn('Investigation 5')
        self.assertNotIn('potion', self.runtime.load()[1].get('known_facts') or [])

    def test_with_no_dc_kit_is_offered_handles_on_the_holding_feature(self):
        self.call('investigation', 'beds')
        packet = self.bridge.prepare('Investigation 27', 'turn', one_pass=True)
        private = packet['input']['private']
        self.assertIn('beds', str((private.get('acts') or {}).get('handles')))
        self.assertIn('holds potion', str(private))

    def test_a_skill_that_cannot_reach_the_claim_warns_kit_privately(self):
        self.call('investigation', 'pit')
        packet = self.bridge.prepare('Investigation 23', 'turn', one_pass=True)
        self.assertIn('investigation cannot find the hidden pit', str(packet['input']['private']))
        self.assertNotIn('cannot find', packet['input']['public']['accepted_public_event'])

    @rejections_raise  # validator probe (tests/kit_policy.py)
    def test_kit_cannot_narrate_an_unfound_thing_into_the_pcs_hands(self):
        with self.assertRaises(InvalidChange) as caught:
            self.turn('I pat the straw in the east bed.',
                      'Your fingers close on a small stoppered flask of ruby liquid.')
        self.assertIn('still hidden', str(caught.exception))
        self.assertNotIn('potion', self.runtime.load()[1].get('known_facts') or [])

    def test_once_found_it_may_be_described(self):
        self.call('investigation', 'beds', dc=12)
        self.turn('Investigation 27')
        self.turn('I hold the flask up to the light.', 'The small stoppered flask of ruby liquid glows.')


if __name__ == '__main__':
    unittest.main()

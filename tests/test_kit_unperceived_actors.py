"""Rebuilt on main e02f355 from #131's spec (supersedes #131). Nagatha's #127 review at 79196b5 (side finding): the hidden-actor check protected only
status 'hidden'. A creature that is alive but not perceivable ("visible": false, or flagged
invisible / hidden / concealed / unseen, or carrying the invisible or hidden condition) got
'An invisible stalker stands right beside you' committed. Every such marker now protects it,
in the narration check and in the player view.

The fields, from the room schema (kit_rooms.check_room, ROOM_TRIGGERS.md, state_context):
actor "status" ("hidden" until a trigger) and actor "visible" (bool). The flags and conditions are
honoured too so a room that marks perception that way is protected the same.

Synthetic crypt (tests/fixtures/rooms/crypt.json) with a stalker added; dice pinned."""
import copy
import unittest

from runtime import kit_agent, state_context
from runtime.state_context import InvalidChange
from test_kit_review97b import Room, bridge_turn, crypt

SEEN = 'Cold stone and dust; an invisible stalker stands right beside you.'
PLAIN = 'Cold stone, dust, and silence.'


def with_stalker(**marks):
    source = crypt()
    source['actors']['stalker'] = {**copy.deepcopy(source['actors']['sexton']), 'name': 'Invisible stalker',
                                   'location': 'nave', 'status': 'alive', 'visible': True, **marks}
    return source


MARKS = {'not visible': {'visible': False}, 'invisible flag': {'invisible': True},
         'hidden flag': {'hidden': True}, 'concealed flag': {'concealed': True},
         'unseen flag': {'unseen': True}, 'invisible condition': {'conditions': ['invisible']},
         'hidden condition': {'conditions': ['Hidden']}}


class UnperceivedActors(unittest.TestCase):
    def test_an_alive_creature_the_pc_cannot_perceive_is_protected_whatever_marks_it(self):
        for label, marks in MARKS.items():
            with self.subTest(marks=label):
                room = Room(self, source=with_stalker(**marks))
                with self.assertRaisesRegex(InvalidChange, 'still hidden'):
                    bridge_turn(room, 'I look around.', text=SEEN)
                self.assertNotIn('Invisible stalker', str(room.runtime.player_view()))

    def test_the_same_narration_commits_when_the_creature_is_plainly_there(self):
        room = Room(self, source=with_stalker())
        _, result = bridge_turn(room, 'I look around.', text=SEEN)
        self.assertIn('stalker', result['spoken'])

    def test_a_plain_narration_still_commits_beside_an_unseen_creature(self):
        room = Room(self, source=with_stalker(visible=False))
        _, result = bridge_turn(room, 'I look around.', text=PLAIN)
        self.assertIn('silence', result['spoken'])

    def test_only_alive_creatures_are_protected(self):
        for status in ('dead', 'fled'):
            with self.subTest(status=status):
                self.assertFalse(state_context.unperceived({'status': status, 'visible': False}))

    def test_the_helper_reads_every_marker(self):
        self.assertFalse(state_context.unperceived({'status': 'alive', 'visible': True}))
        self.assertTrue(state_context.unperceived({'status': 'hidden', 'visible': False}))
        for marks in MARKS.values():
            self.assertTrue(state_context.unperceived({'status': 'alive', 'visible': True, **marks}), marks)

    def test_words_cover_the_unperceived_creature(self):
        room = Room(self, source=with_stalker(visible=False))
        words = kit_agent.hidden_actor_words(room.runtime.source(), room.state, {'public_view': {}, 'action': ''})
        self.assertIn('stalker', words)


def merged(room, key):
    return {**room.runtime.source()['actors'][key], **room.state['actors'][key]}


class RevealAndPresence(unittest.TestCase):
    """Nagatha's #131 review at 788c6e1. Medium: a trigger's reveal reset only status and visible,
    so an invisible flag or condition kept the creature protected while it fought the PC. Low: the
    present-actor list, the turn's speakers and the fight's roster read only status 'hidden'."""

    def test_the_reveal_clears_every_hiding_marker(self):
        cases = {'invisible flag': {'invisible': True}, 'invisible condition': {'conditions': ['invisible', 'prone']},
                 'every flag': {'hidden': True, 'concealed': True, 'unseen': True, 'conditions': ['Hidden']}}
        for label, marks in cases.items():
            with self.subTest(marks=label):
                source = crypt()
                source['actors']['ghoul'].update(marks)
                room = Room(self, source=source)
                _, result = bridge_turn(room, 'I push the lid aside.', {'target': 'lid', 'act': 'push'},
                                        text='You push the lid and a grey ghoul lunges out at you.')
                self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])
                self.assertIn('ghoul', result['spoken'], 'Kit may name the creature fighting him')
                self.assertFalse(state_context.unperceived(merged(room, 'ghoul')), merged(room, 'ghoul'))
                self.assertIn('ghoul', room.state['combat']['hp'], 'the revealed creature fights')
                if 'prone' in str(marks):
                    self.assertIn('prone', merged(room, 'ghoul')['conditions'], 'other conditions stay')

    def test_an_alive_unseen_creature_is_not_present_or_a_speaker(self):
        room = Room(self, source=with_stalker(visible=False))
        self.assertNotIn('stalker', room.adjudicator._present_actors(room.state))
        speakers = kit_agent.turn_speakers(room.runtime, {})['speakers']
        self.assertNotIn('Invisible stalker', speakers)
        seen = Room(self, source=with_stalker())
        self.assertIn('stalker', seen.adjudicator._present_actors(seen.state))
        self.assertIn('Invisible stalker', kit_agent.turn_speakers(seen.runtime, {})['speakers'])

    def test_an_alive_unseen_creature_is_not_in_the_fight(self):
        source = crypt()
        source['actors']['skeleton'].update(status='alive', visible=False)
        room = Room(self, source=source)
        room.act('I look at the sarcophagus.')
        room.act('I push it open.', {'target': 'sarcophagus', 'act': 'push'})
        hp = room.state['combat']['hp']
        self.assertIn('ghoul', hp)
        self.assertNotIn('skeleton', hp, 'a creature he cannot perceive is not on the roster')


if __name__ == '__main__':
    unittest.main()

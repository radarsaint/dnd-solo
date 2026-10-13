"""#97 review at ba20190 (Nagatha): E' and B''.

E': the handles offer follows the room's structure, not a verb list. Any line that names a
    watched, found feature (or refers to it with a pronoun) gets the offer unless the engine
    read the turn as a look or a threshold look; verbs only shape the hint.
B'': on any turn beside a watched feature where nothing fired, no clause of the narration
    may show something moving or changing state, whatever its noun or person, unless that
    clause says it does not.

Rooms: the from-scratch crypt (tests/fixtures/rooms/crypt.json) and the bell tower
(test_kit_review97c.belfry), plus a well written here. Dice pinned.
"""
import re
import unittest

from runtime import kit_agent
from runtime.state_context import InvalidChange
from test_kit_review97b import Room, bridge_turn
from test_kit_review97c import belfry


def well():
    """A courtyard well whose bucket winch wakes something below (from scratch)."""
    source = belfry()
    source['id'] = 'synthetic-well-v1'
    source['facts'] = {'winch': {'area': 'stair', 'visible': True, 'text': 'An iron winch over an old well.',
                                 'handling': {'nouns': ['winch', 'well'], 'parts': ['crank', 'bucket'],
                                              'look': 'Rust flakes off the crank.', 'move': 'The crank turns.',
                                              'handle': 'Cold iron under your hand.'}},
                       'beam': {'area': 'loft', 'visible': True, 'text': 'A cracked oak beam.'}}
    source['triggers'][0]['on'] = {'disturb': 'winch'}
    return source


CRYPT_HANDS = ('I shoulder the lid aside.', 'I muscle the lid aside.', 'I rock the sarcophagus.',
               'I get my crowbar under the lid.', 'I run my fingers along the lid.', 'I shoulder it.')
WELL_HANDS = ('I put my back into the crank.', 'I crank the winch.', 'I haul up the bucket.', 'I lean on it.')
LOOKS = ('I look at the lid.', 'I look around the nave.', 'I peer through the arch.', 'I listen at the lid.',
         'I wait.')

# Round 5 (#97 review at 304ef62): the guard is state-based. Slips about the feature, "it", or
# what is behind it are refused; unnamed synonyms ("the top", "the cover", "stone") are the
# accepted residual risk, caught by the next packet's feature_state backstop.
SLIPS = ('The lid shifts under your palms and slides aside; dust below.',
         'You shove; the lid slides aside. Dust and bones.',
         'It does not budge, but something inside shifts.',
         'It shifts.',
         'A gap opens inside.')
HONEST = ('You strain, but it will not budge.', 'It does not move.', 'Dust lies thick on the stone.')


class OfferFollowsTheRoomTests(unittest.TestCase):
    def test_hands_on_lines_with_no_listed_verb_are_offered(self):
        for source, lines, feature in ((None, CRYPT_HANDS, 'sarcophagus'), (well(), WELL_HANDS, 'winch')):
            for line in lines:
                with self.subTest(line=line):
                    result = Room(self, source=source).resolve(line)
                    self.assertIn(feature, ((result.offers or {}).get('handles') or {}).get('targets', {}))

    def test_looks_listens_and_waits_still_get_none(self):
        for line in LOOKS:
            with self.subTest(line=line):
                self.assertNotIn('handles', Room(self).resolve(line).offers or {})
        self.assertNotIn('handles', Room(self, source=well()).resolve('I look down the well.').offers or {})

    def test_a_hands_on_line_kit_answers_fires(self):
        room = Room(self)
        room.act('I shoulder the lid aside.', {'target': 'lid', 'act': 'push'})
        self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])


class NothingMovesWithoutAFiringTests(unittest.TestCase):
    NONE = {'target': 'none', 'act': 'none', 'reason': 'too_heavy'}

    def test_movement_in_any_clause_is_rejected_on_a_none_turn(self):
        for source, line in ((None, 'I push the lid aside.'), (well(), 'I crank the winch.')):
            for text in SLIPS:
                text = text if source is None else re.sub(r'\blid\b', 'crank', text)
                with self.subTest(line=line, text=text):
                    room = Room(self, source=source)
                    # 'You feel ...' also trips the agency guard first; either way it is refused.
                    with self.assertRaisesRegex(InvalidChange, 'moving or opening|Player agency|still sealed'):
                        bridge_turn(room, line, self.NONE, text=text)
                    self.assertFalse(room.state.get('triggers_fired'))

    def test_honest_narration_passes(self):
        for source, line in ((None, 'I push the lid aside.'), (well(), 'I crank the winch.')):
            for text in HONEST:
                with self.subTest(line=line, text=text):
                    bridge_turn(Room(self, source=source), line, self.NONE, text=text)

    def test_the_check_runs_without_an_offer_too(self):
        room = Room(self)
        with self.assertRaisesRegex(InvalidChange, 'moving or opening'):
            bridge_turn(room, 'I look at the sarcophagus.', None, omit=True,
                        text='As you look, the lid slides aside.')
        self.assertFalse(room.state.get('triggers_fired'))

    def test_clause_level_unit(self):
        for text in SLIPS + ('It scrapes.',):
            with self.subTest(text=text):
                with self.assertRaises(InvalidChange):
                    kit_agent.check_unmoved(text, ['lid'])
        for text in HONEST + ('The lid will not budge.',):
            kit_agent.check_unmoved(text, ['lid'])


if __name__ == '__main__':
    unittest.main()

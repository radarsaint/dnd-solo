"""#97 review at 304ef62 (Nagatha): B'' as a positive, state-based guard.

A watched feature whose trigger has not fired is sealed. On a turn where nothing fired, the
performance may not show its interior or contents, or say it is open, off, back, removed,
gone or on the floor; a small movement check covers clauses about the feature itself. Other
things in the room may move, open and change hands. Narration is English. After such a turn
the next packet says the feature is still sealed.

Rooms: the from-scratch crypt and a chapel reliquary written here (no book text). Dice pinned.
"""
import json
import unittest

from runtime import kit_agent, kit_rooms
from runtime.kit_agent import KitChatBridge
from runtime.state_context import InvalidChange
from test_kit_review97b import Room, bridge_turn, crypt
from test_kit_review97c import belfry
from kit_policy import rejections_raise

NONE = {'target': 'none', 'act': 'none', 'reason': 'too_heavy'}
OTHER = {'target': 'none', 'act': 'none', 'reason': 'not_the_feature'}


def chapel():
    """A chapel with a locked reliquary; opening it wakes a wight (from scratch)."""
    source = belfry()
    source['id'] = 'synthetic-chapel-v1'
    source['facts'] = {
        'reliquary': {'area': 'stair', 'visible': True, 'text': 'A gilt reliquary chest stands on the altar.',
                      'handling': {'nouns': ['reliquary', 'chest', 'casket'], 'parts': ['lid', 'clasp'],
                                   'holds': 'finger', 'interior': ['velvet lining'], 'contents': ['bones'],
                                   'look': 'The gilt is flaking.', 'move': 'The lid swings up.',
                                   'handle': 'The clasp is cold.'}},
        'finger': {'area': 'stair', 'visible': False, 'text': "A saint's finger bone on velvet.",
                   'handling': {'nouns': ['finger', 'relic']}},
        'beam': {'area': 'loft', 'visible': True, 'text': 'A cracked oak beam.'}}
    source['actors']['bats']['name'] = 'Hollow wight'
    source['triggers'][0]['on'] = {'disturb': 'reliquary'}
    return source


# (room, the player's line, slips that must be refused on a no-fire turn)
SLIPS = {
    'crypt': ('I push the lid aside.', (
        'The lid has been pushed back.', 'The lid is now off.', 'The lid lies on the floor now.',
        'You see bones inside.', 'Inside, old bones and dust.', 'Your torch lights the interior.',
        'Cold air breathes from the dark within.', 'La tapa se desliza.', 'Der Deckel gleitet zur Seite.',
        'The lid slides aside.')),
    'chapel': ('I pry the clasp open.', (
        'The lid has been pushed back.', 'The lid is now off.', 'The lid lies on the floor now.',
        'You see bones inside.', 'Inside, old bones and dust.', 'Your torch lights the interior.',
        'Cold air breathes from the dark within.', 'The velvet lining glows red.', 'La tapa se abre.',
        'It swings open.')),
}
# Not about the watched feature: never refused on these grounds.
FINE = (('I give the sexton a coin.', 'You give the sexton a coin.'),
        ('I move to the window.', 'You move to the window; the glass is cracked.'),
        ('I open my pack.', 'You open your pack and take out a ration.'),
        ('I set my torch down.', 'You set your torch down; the flame shifts in the draft.'),
        ('I step inside the arch.', 'You step back and turn toward the door.'))
HONEST = ('The lid will not budge.', 'You strain; it does not move.', 'Dust lies thick on the lid.')


def room_of(test, name):
    return Room(test, source=None if name == 'crypt' else chapel())


class SealedFeatureTests(unittest.TestCase):
    @rejections_raise  # validator probe (tests/kit_policy.py)
    def test_every_slip_is_refused_and_nothing_fires(self):
        for name, (line, slips) in SLIPS.items():
            for text in slips:
                with self.subTest(room=name, text=text):
                    room = room_of(self, name)
                    with self.assertRaises(InvalidChange):
                        bridge_turn(room, line, NONE, text=text)
                    self.assertFalse(room.state.get('triggers_fired'))

    def test_the_unit_check_names_the_seal(self):
        room = Room(self)
        sealed = kit_agent.sealed_terms(room.runtime.source(), room.state)
        self.assertIn('sarcophagus', sealed)
        for text in SLIPS['crypt'][1]:
            with self.subTest(text=text):
                with self.assertRaises(InvalidChange):
                    kit_agent.check_sealed(text, sealed)

    def test_other_things_may_move_open_and_change_hands(self):
        for name in ('crypt', 'chapel'):
            for line, text in FINE:
                with self.subTest(room=name, text=text):
                    bridge_turn(room_of(self, name), line, OTHER, text=text)

    def test_honest_refusals_pass(self):
        for name, (line, _) in SLIPS.items():
            for text in HONEST:
                with self.subTest(room=name, text=text):
                    bridge_turn(room_of(self, name), line, NONE, text=text)

    def test_a_firing_declaration_may_show_the_inside(self):
        room = Room(self)
        bridge_turn(room, 'I push the lid aside.', {'target': 'lid', 'act': 'push'},
                    text='The lid grinds aside; old bones lie inside.')
        self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])

    def test_the_next_packet_says_it_is_still_sealed(self):
        for name in ('crypt', 'chapel'):
            with self.subTest(room=name):
                room = room_of(self, name)
                bridge_turn(room, SLIPS[name][0], NONE, text='It will not budge.')
                packet = KitChatBridge(room.runtime, room.adjudicator).prepare('I catch my breath.', 't2', one_pass=True)
                state = json.dumps(packet['input']['private'].get('feature_state') or {})
                self.assertIn('sealed', state)

    def test_room_terms_are_checked_and_defaulted(self):
        bad = chapel()
        bad['facts']['reliquary']['handling']['interior'] = 'velvet'
        with self.assertRaises(InvalidChange):
            kit_rooms.check_room(bad)
        terms = kit_agent.sealed_terms(Room(self).runtime.source(), Room(self).state)['sarcophagus']
        for word in ('inside', 'interior', 'within', 'amulet'):
            self.assertIn(word, terms['interior'] + terms['contents'])


class ExistingSceneDescriptionTests(unittest.TestCase):
    """Must pass (#101 Reveal): ordinary description of what is already there is not a seal
    breaking. The movement check covers only clauses whose subject is the sealed feature."""
    LINES = ('grey hide split and stinking', 'cracked funeral urns lean on the wall',
             'its head broken off and carried away')

    def test_carcass_room_description_passes(self):
        from test_kit_review97b import CARCASS
        source = json.loads(CARCASS.read_text())
        room = Room(self, source=source)
        sealed = kit_agent.sealed_terms(room.runtime.source(), room.state)
        self.assertTrue(sealed)
        for text in self.LINES:
            with self.subTest(text=text):
                kit_agent.check_sealed(text.capitalize() + '.', sealed)

    def test_crypt_description_passes(self):
        room = Room(self)
        sealed = kit_agent.sealed_terms(room.runtime.source(), room.state)
        for text in self.LINES:
            with self.subTest(text=text):
                kit_agent.check_sealed(text.capitalize() + '.', sealed)


class OrdinaryLinesPassTests(unittest.TestCase):
    """Must pass (#97 review at fc85f26): description that mentions a sealed feature, an
    open-state word, "it" or "inside" without saying the seal broke."""
    P10 = ('The sarcophagus sits back against the far wall.',
           'The coffin rests on the floor of the nave, its carvings worn smooth.',
           "The tomb's carvings are worn away by centuries.",
           'The tomb stands apart from the pews.',
           'The sarcophagus is broken at one corner, an old chip.',
           'It is dark back here.',
           'You duck inside.',
           'A chill settles within you.')
    CRYPT_SWEEP = ('The sarcophagus looms in the candlelight.', 'The lid is carved with a sleeping knight.',
                   'Moss grows along the base of the coffin.', 'The tomb is older than the chapel above it.',
                   'It is cold here.', 'It is quiet now.', 'It has been years since anyone came.',
                   'You step back from the coffin.', 'You walk around the sarcophagus.',
                   'A draft moves through the nave.', 'The candles gutter and go out one by one.',
                   'You step inside the vestibule.', 'Fear settles inside you.',
                   'The lid is heavy granite, a hand thick.', 'Wax drips off the candle onto the floor.',
                   'The tomb sits apart, on a low dais.', 'Its carvings are worn off at the corners.',
                   'A rat runs off along the wall.')
    CHAPEL_SWEEP = ('The reliquary gleams on the altar.', 'Its gilt is flaking away at the corners.',
                    'The clasp is shaped like a hand.', 'The chest sits back on the altar, out of reach of the door.',
                    'It is dim in the chapel.', 'You slip inside the stairwell.', 'A cold dread grows within you.',
                    'The casket rests on a cloth on the floor of the altar.')

    def check(self, source, lines):
        room = Room(self, source=source)
        sealed = kit_agent.sealed_terms(room.runtime.source(), room.state)
        self.assertTrue(sealed)
        for text in lines:
            with self.subTest(text=text):
                kit_agent.check_sealed(text, sealed)

    def test_p10_lines(self):
        self.check(None, self.P10)

    def test_crypt_sweep(self):
        self.check(None, self.CRYPT_SWEEP)

    def test_chapel_sweep(self):
        self.check(chapel(), self.CHAPEL_SWEEP)

    def test_p10_lines_through_the_bridge(self):
        for text in self.P10:
            with self.subTest(text=text):
                bridge_turn(Room(self), 'I look around the nave.', None, omit=True, text=text)


if __name__ == '__main__':
    unittest.main()

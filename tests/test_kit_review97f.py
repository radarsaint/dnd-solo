"""#97 review at eb0f643 (Nagatha): wear and damage wording is description, not a seal
breaking ("faces worn off", "chipped off at one corner"); "the lid comes away in your hands"
is the lid coming off. Rooms: the crypt, the chapel reliquary, and a shrine written here."""
import unittest

from runtime import kit_agent
from test_kit_review97b import Room
from test_kit_review97c import belfry
from test_kit_review97e import chapel


def shrine():
    """A wayside shrine: a stone idol on a hollow plinth with a cover stone (from scratch)."""
    source = belfry()
    source['id'] = 'synthetic-shrine-v1'
    source['facts'] = {
        'plinth': {'area': 'stair', 'visible': True, 'text': 'A hollow plinth under a weathered idol.',
                   'handling': {'nouns': ['plinth', 'idol'], 'parts': ['cover', 'face'],
                                'interior': ['hollow'], 'contents': ['offerings'],
                                'look': 'Lichen on the stone.', 'move': 'The cover stone scrapes aside.',
                                'handle': 'Rough stone.'}},
        'beam': {'area': 'loft', 'visible': True, 'text': 'A cracked oak beam.'}}
    source['triggers'][0]['on'] = {'disturb': 'plinth'}
    return source


ROOMS = {'crypt': None, 'chapel': chapel, 'shrine': shrine}
WEAR = {
    'crypt': ('Carvings of saints run along its side, faces worn off.', "The lid's edge is chipped off at one corner.",
              'The gilt has flaked off its sides.', "The saints' heads were knocked off by vandals long ago.",
              'The lid is worn smooth, its letters rubbed off.', 'The sarcophagus is weathered, its edges crumbled away.'),
    'chapel': ("The reliquary's gilt is flaking off.", 'The lid is scratched, its enamel chipped off in places.',
               "The clasp's plating has worn away.", "Its jewels were pried off long ago; empty sockets remain."),
    'shrine': ("The idol's nose is broken off.", 'The plinth is eroded, its carvings worn away.',
               "The cover's edge is chipped off.", 'Its paint has peeled off in strips.'),
}
SLIPS = {
    'crypt': ('The lid comes away in your hands.', 'The lid comes free.', 'The lid is knocked off.', 'The lid slides aside.'),
    'chapel': ('The lid comes away in your hands.', 'The lid swings open.', 'The lid is now off.'),
    'shrine': ('The cover comes away in your hands.', 'The cover is knocked off.', 'Inside the hollow, offerings glint.'),
}


def sealed(test, name):
    maker = ROOMS[name]
    room = Room(test, source=maker() if maker else None)
    return kit_agent.sealed_terms(room.runtime.source(), room.state)


class WearIsDescriptionTests(unittest.TestCase):
    def test_wear_and_damage_pass(self):
        for name, lines in WEAR.items():
            terms = sealed(self, name)
            for text in lines:
                with self.subTest(room=name, text=text):
                    kit_agent.check_sealed(text, terms)

    def test_coming_away_and_knocked_off_are_refused(self):
        for name, lines in SLIPS.items():
            terms = sealed(self, name)
            for text in lines:
                with self.subTest(room=name, text=text):
                    with self.assertRaises(kit_agent.InvalidChange):
                        kit_agent.check_sealed(text, terms)


if __name__ == '__main__':
    unittest.main()

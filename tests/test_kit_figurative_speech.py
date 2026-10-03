"""Room-fit guards read figurative speech as figurative (live 6c, 2026-10-03 T8: the dealer's
"win back your supper" was rejected as serving food). General engine: a food or drink word
counts only when a serving or drinking verb takes it as its object, or it is the subject of
a serving predicate. Idioms, stakes, and metaphors pass; literal served drinks still fail."""
import unittest

from runtime import kit_guards
from runtime.state_context import InvalidChange

FIGURATIVE = (
    'Another hand, and perhaps you win back your supper, or would you rather walk away?',
    'Cold feet already, friend?',
    'This next hand is on the house.',
    'You look like a fish out of water down here.',
    'You will eat your words before the night is out.',
    'Card sharps are the bread and butter of this table.',
    'Sip on that thought a while.',
    'Hand me your coin and we begin.',
)
LITERAL = (
    'He pours you a cup of wine.',
    'She slides a plate of bread across the table.',
    'The dealer hands you a goblet of wine.',
    'Drinks are on the house tonight.',
    'Have some wine while you decide.',
    'Let us drink to your luck.',
)


class FigurativeSpeech(unittest.TestCase):
    def test_idioms_and_metaphors_pass_the_room_fit_guard(self):
        for speaker in ('Dealer', 'Kit', 'Narrator'):
            for line in FIGURATIVE:
                with self.subTest(speaker=speaker, line=line):
                    kit_guards.check_no_refreshment([{'speaker': speaker, 'text': line}])

    def test_a_literal_served_drink_is_still_rejected(self):
        for line in LITERAL:
            with self.subTest(line=line):
                with self.assertRaisesRegex(InvalidChange, 'Room fit'):
                    kit_guards.check_no_refreshment([{'speaker': 'Dealer', 'text': line}])

    def test_saying_there_is_none_still_passes(self):
        kit_guards.check_no_refreshment([{'speaker': 'Dealer', 'text': 'There is no wine to pour; the cellar is dry.'}])


if __name__ == '__main__':
    unittest.main()
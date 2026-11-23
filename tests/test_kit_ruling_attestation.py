"""Source verification must establish words at a real span, not self-attest."""
import unittest
from unittest.mock import patch
from runtime import kit_rulings

class RulingAttestation(unittest.TestCase):
    quote='If a visitor touches the cord, a bell rings.'

    def lookup(self, text, hit):
        with patch('runtime.kit_adventure._load',return_value=({'start':'x'},text)):
            with patch('runtime.kit_rulings.section_key',return_value='x'):
                with patch('runtime.kit_rulings._stashed_match',return_value=({},hit)):
                    return kit_rulings.for_action('synthetic','I touch the cord.','x')

    def hit(self, **changes):
        return dict({'quote':self.quote,'span':[0,len(self.quote)],'offset':0,
                     'trigger_kind':'check','confidence':'CONFIRMED'},**changes)

    def test_real_contiguous_source_is_verified(self):
        self.assertTrue(self.lookup(self.quote,self.hit())['source_verified'])

    def test_whitespace_wrapping_preserves_the_same_words(self):
        text=self.quote.replace('touches the','touches\n  the')
        self.assertTrue(self.lookup(text,self.hit(span=[0,len(text)]))['source_verified'])

    def test_missing_outside_or_malformed_spans_cannot_self_attest(self):
        for span in (None,[],[9000,9500],[-1,12],[2,2],['0','40'],[False,40],[0.5,40],[0,12,14]):
            with self.subTest(span=span):
                self.assertIsNone(self.lookup('Unrelated source.',self.hit(span=span)))

    def test_valid_span_with_wrong_quote_is_not_verified(self):
        self.assertIsNone(self.lookup('A visitor sees an ordinary cord.',self.hit(span=[0,31])))

    def test_real_quote_elsewhere_does_not_validate_wrong_span(self):
        text='An unrelated opening. '+self.quote
        self.assertIsNone(self.lookup(text,self.hit(span=[0,21])))

    def test_reordered_words_are_not_the_source(self):
        words=self.quote.split(); words[2],words[3]=words[3],words[2]
        self.assertIsNone(self.lookup(' '.join(words),self.hit()))

    def test_mismatched_or_missing_offset_is_not_verified(self):
        for offset in (None,1,False,'0'):
            with self.subTest(offset=offset):
                self.assertIsNone(self.lookup(self.quote,self.hit(offset=offset)))

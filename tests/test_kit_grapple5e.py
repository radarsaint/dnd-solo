"""Nagatha's rulings after 01dc0a6: a bare 'I grab <creature>' is an SRD contested grapple.
The PC's Athletics is rolled in Avrae (asked for when unreported); the creature rolls the
better of Athletics and Acrobatics in the engine (pinned here); the actor wins ties. No hold
ever happens without a roll. The generic pending line is said in Kit's voice."""
import copy
import unittest

from runtime import kit_combat
from runtime.kit_agent import PendingRuling, pending_ruling_result
from test_kit_review101c import clause_parser, Arena, KILN_OPEN, rogue, ruling_of, without_shield, wizard


def kiln(test, sheet, die):
    arena = Arena(test, 'kiln', sheet=sheet, roll=lambda: die)
    arena.act(KILN_OPEN)
    return arena


def bridge(test, sheet, die):
    arena = Arena(test, 'rope_bridge', sheet=sheet, roll=lambda: die)
    arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
    return arena


def shrine(test, sheet, die):
    arena = Arena(test, 'shrine', sheet=sheet, roll=lambda: die)
    arena.act('Initiative 25. I stab the adept with my dagger, 3 to hit, 3 piercing.')
    return arena


@clause_parser
class ContestedGrapple(unittest.TestCase):
    def test_a_bare_grab_with_no_roll_asks_for_athletics_and_holds_nobody(self):
        for make, sheet, text in ((kiln, without_shield(wizard(hp=60)), 'I grab the kobold slinger.'),
                                  (bridge, rogue(), 'I grab the bridge ogre.')):
            arena = make(self, sheet, 10)
            before = copy.deepcopy(arena.fight)
            exc, shown = ruling_of(self, arena, text)
            self.assertIn('Athletics', shown['player_message'], text)
            self.assertEqual(arena.fight, before, text)
            self.assertFalse((arena.state.get('scene') or {}).get('grappled'), text)

    def test_the_actor_wins_ties_against_the_better_of_athletics_and_acrobatics(self):
        # kobold slinger: Str +0, Dex +2 -> d20 10 + 2 = 12 (Acrobatics is the better)
        arena = kiln(self, without_shield(wizard(hp=60)), 10)
        result = arena.act('I grab the kobold slinger. Athletics 12.')
        self.assertEqual(arena.state['scene']['grappled'], 'archer', result.public_event)
        # bridge ogre: Str/Athletics +6 beats Dex +0 -> 10 + 6 = 16
        arena = bridge(self, rogue(), 10)
        result = arena.act('I grab the bridge ogre, Athletics 16.')
        self.assertEqual(arena.state['scene']['grappled'], 'ogre', result.public_event)

    def test_one_short_and_he_twists_free(self):
        arena = bridge(self, rogue(), 10)
        result = arena.act('I grab the bridge ogre, Athletics 15.')
        self.assertFalse(arena.state['scene'].get('grappled'))
        self.assertIn('twists out of your grip', result.public_event)
        # the shrine adept: Dex +5 -> 4 + 5 = 9; an 8 fails, a 9 holds
        arena = shrine(self, without_shield(wizard(hp=60)), 4)
        self.assertIn('twists out', arena.act('I grab the adept. Athletics 8.').public_event)
        arena = shrine(self, without_shield(wizard(hp=60)), 4)
        arena.act('I grab the adept. Athletics 9.')
        self.assertEqual(arena.state['scene']['grappled'], 'adept')

    def test_an_avrae_check_paste_is_the_roll(self):
        arena = bridge(self, rogue(), 3)  # ogre 3 + 6 = 9
        arena.act('I grab the bridge ogre.\n!check athletics\nWren makes an Athletics check!\n1d20 (7) + 3 = `10`')
        self.assertEqual(arena.state['scene']['grappled'], 'ogre')

    def test_the_creature_rolls_in_the_engine(self):
        self.assertEqual(kit_combat.escape_bonus({'grapple': 6, 'initiative': 0}), 6)
        self.assertEqual(kit_combat.escape_bonus({'grapple': 0, 'initiative': 3}), 3)
        self.assertEqual(kit_combat.escape_bonus({'grapple': 1, 'initiative': 0, 'acrobatics': 4}), 4)


class KitVoicePending(unittest.TestCase):
    """Since #122 slice 2 these messages are Kit's to declare in a running fight (main's parser
    cannot read them): what she declares is still said in Kit's voice, never the engine's, and
    spends nothing."""

    def declared(self, arena, text, entries):
        from runtime.kit_agent import KitChatBridge
        from test_kit_combat_acts_slice2 import plan_for
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare(text, 'v', one_pass=True)
        self.assertTrue(packet['input']['private']['acts']['combat_acts'], text)
        return bridge.complete('v', {'decision': plan_for(packet, entries), 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'You set your feet.'}]}})

    def test_hold_the_line_is_said_in_kits_voice(self):
        arena = bridge(self, rogue(), 10)
        before = copy.deepcopy(arena.fight)
        # The #122 audit: her ruling raises and commits nothing; its own line is what the player gets.
        with self.assertRaises(PendingRuling) as caught:
            self.declared(arena, 'I hold the line.', [{'kind': 'object', 'order': 1, 'says': 'hold the line'}])
        said = pending_ruling_result(caught.exception)['player_message']
        self.assertIn('hold the line', said.casefold())
        self.assertNotIn("That one needs the DM's call. Say a little more", said)
        for word in ('slice', 'committed', 'ruling', 'engine'):
            self.assertNotIn(word, said.casefold())
        self.assertEqual((arena.fight['hp'], arena.fight['pc_damage']), (before['hp'], before['pc_damage']))

    def test_a_bare_shield_outside_a_window_says_it_waits_for_its_moment(self):
        arena = kiln(self, wizard(hp=60), 2)  # every foe misses: no window open
        self.assertIsNone(arena.fight.get('awaiting'))
        result = self.declared(arena, 'Shield.', [{'kind': 'reaction', 'order': 1, 'reaction': 'shield',
                                                   'says': 'Shield'}])
        said = result['public_event']
        self.assertIn('Shield', said)
        self.assertIn('reaction', said.casefold())
        for word in ('slice', 'committed', 'ruling', 'engine'):
            self.assertNotIn(word, said.casefold())
        self.assertEqual(arena.slot1(), 0)


if __name__ == '__main__':
    unittest.main()

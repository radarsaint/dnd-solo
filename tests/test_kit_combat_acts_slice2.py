"""#122 second slice: Kit's combat_acts win over a pending ruling in a running fight (a message
main's parser cannot read is offered to her, and she must declare it; an object or environment
act she declares is the ruling, and nothing in that message commits); a declared turn that
opens a reaction window is interstitial; Cunning Action; movement against speed. Rooms: rope
bridge, kiln, shrine; sheets: rogue, warlock, wizard. Dice pinned."""
import copy
import unittest

from runtime.kit_agent import KitChatBridge, PendingRuling
from runtime.state_context import InvalidChange
from test_kit_agent import RecordingModel
from test_kit_combat_acts_retarget import A, kiln, shrine, ud_bridge, absorber
from test_kit_review101c import Arena, KILN_OPEN, clause_log, rogue, warlock, without_shield, wizard


def plan_for(packet, combat_acts=None, **extra):
    plan = RecordingModel().plan(packet['input']['private'])
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    plan.update(move='world_description', focus_actor='none')
    for key in ('objective', 'visible_cue', 'player_opening'):
        plan['public_brief'].pop(key, None)
    plan['public_brief']['scope'] = 'call'
    if combat_acts is not None:
        plan['combat_acts'] = combat_acts
    plan.update(extra)
    return plan


def turn(arena, action, combat_acts=None, turn_id='s1'):
    bridge = KitChatBridge(arena.runtime, arena.adjudicator)
    packet = bridge.prepare(action, turn_id, one_pass=True)
    if packet.get('stage') == 'pending_ruling':
        return packet, None
    speech = {'segments': [{'speaker': 'Narrator', 'text': 'You move.'}]}
    return packet, bridge.complete(turn_id, {'decision': plan_for(packet, combat_acts), 'performance': speech})


class DeclarationWinsOverAPendingRuling(unittest.TestCase):
    def test_a_message_mains_parser_cannot_read_is_offered_and_her_move_commits(self):
        arena = ud_bridge(self)
        before = arena.fight['pc_damage']
        packet, result = turn(arena, 'I back away 10 feet.', [A('move', 1, way='away', distance_ft=10)])
        self.assertTrue(packet['input']['private']['acts']['combat_acts'])
        self.assertIn('fall back out of reach', result['spoken'])
        self.assertGreater(arena.fight['pc_damage'], before)

    def test_she_must_answer_it(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger']))
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare('I back away 10 feet.', 'm', one_pass=True)
        with self.assertRaisesRegex(InvalidChange, 'acts.combat_acts is offered'):
            bridge.complete('m', {'decision': plan_for(packet), 'performance': {'segments': [
                {'speaker': 'Narrator', 'text': 'You step back.'}]}})

    def test_an_object_act_she_declares_is_the_ruling_and_nothing_commits(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger']))
        before = copy.deepcopy(arena.fight)
        _, result = turn(arena, 'I push the kiln door shut, then stab the slinger, 16 to hit, 3 piercing.', [
            A('object', 1, says='push the kiln door shut'),
            A('attack', 2, target='archer', weapon='dagger', roll='16 to hit, 3 piercing')])
        self.assertIn("needs the DM's call", result['spoken'])
        self.assertEqual(arena.fight['hp'], before['hp'])
        self.assertEqual(arena.fight['pc_damage'], before['pc_damage'])

    def test_the_ruling_records_every_entry(self):
        arena = shrine(self, without_shield(wizard(hp=60)), 10)
        exc = arena.held('(declared)', combat_acts=[A('object', 1, says='kick the brazier at the adept'),
                                                    A('spell', 2, target='adept', spell='fire bolt', roll='17 to hit, 7 fire')])
        self.assertEqual([c['outcome'] for c in exc.clauses], ['ruling', 'waits'])

    def test_a_missing_roll_is_still_an_ask_at_prepare(self):
        arena = ud_bridge(self)
        with self.assertRaisesRegex(PendingRuling, 'Avrae'):
            turn(arena, 'I stab the ogre.')

    def test_outside_a_fight_an_unread_deed_is_still_a_ruling(self):
        arena = Arena(self, 'kiln', sheet=without_shield(wizard(hp=60)))
        with self.assertRaises(PendingRuling):
            turn(arena, 'I juggle three clay pots.')


class DeclaredWindowIsInterstitial(unittest.TestCase):
    def test_a_declared_turn_that_opens_a_shield_window_is_interstitial(self):
        arena = Arena(self, 'kiln', sheet=wizard(hp=60), roll=lambda: 10)  # the imp's spit hits: Shield is offered
        arena.act(KILN_OPEN)
        arena.act('No, let it hit.', react='decline')
        self.assertIsNone(arena.fight.get('awaiting'))
        _, result = turn(arena, 'I back away 10 feet.', [A('move', 1, way='away', distance_ft=10)])
        self.assertEqual(arena.fight['awaiting']['kind'], 'reaction_window')
        self.assertEqual(result['turn_role'], 'interstitial')
        self.assertEqual(result['interstitial']['kind'], 'reaction_window')


class CunningAction(unittest.TestCase):
    def test_a_rogue_disengages_as_a_bonus_action_after_his_attack(self):
        arena = ud_bridge(self)
        before = arena.fight['pc_damage']
        result = arena.act('(declared)', combat_acts=[
            A('attack', 1, target='ogre', weapon='rapier', roll='16 to hit, 5 piercing'),
            A('disengage', 2, distance_ft=10)])
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved'])
        self.assertNotIn('lashes out as you go', result.public_event)

    def test_dash_and_hide_as_bonus_actions_and_only_one(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[
            A('attack', 1, target='ogre', weapon='rapier', roll='16 to hit, 5 piercing'),
            A('dash', 2), A('hide', 3, roll='Stealth 18')])
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved', 'refused'])
        self.assertIn('already used your bonus action', result.public_event)

    def test_without_cunning_action_it_is_still_his_action(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger']))
        result = arena.act('(declared)', combat_acts=[
            A('attack', 1, target='archer', weapon='dagger', roll='16 to hit, 3 piercing'), A('disengage', 2)])
        self.assertIn('already used your action', result.public_event)


class MovementAgainstSpeed(unittest.TestCase):
    def test_more_than_his_speed_is_refused_with_what_is_left(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger'], speed=30))
        result = arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=20),
                                                      A('move', 2, way='away', distance_ft=20)])
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'refused'])
        self.assertIn('you have only 10 feet of movement left this turn', result.public_event)

    def test_dash_doubles_it(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger'], speed=25))
        result = arena.act('(declared)', combat_acts=[A('dash', 1), A('move', 2, way='away', distance_ft=50)])
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved'])

    def test_the_sheets_speed_is_used(self):
        arena = ud_bridge(self, rogue(speed='25 ft.'))
        result = arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=30)])
        self.assertIn('you have only 25 feet of movement left this turn', result.public_event)


class NothingDeclaredFallsBackToMain(unittest.TestCase):
    """Nagatha's playtest: with nothing declared, 'No reaction.', a bare Avrae roll line and 'Nik
    backs off 30 feet down the hall.' were swallowed into a silent 'You declare:' echo. When Kit
    declares nothing, the turn says what main says for that message; a message is never swallowed."""

    MESSAGES = ('No reaction.', '1d20 (14) + 3 = `17`', 'Nik backs off 30 feet down the hall.')

    def mains_line(self, arena, text):
        from unittest import mock
        from runtime.kit_agent import RoomAdjudicator, pending_ruling_result
        revision, state = arena.runtime.load()
        with mock.patch.object(RoomAdjudicator, '_declare_instead', return_value=None), \
                self.assertRaises(PendingRuling) as caught:
            arena.adjudicator.resolve(text, revision, state)
        return pending_ruling_result(caught.exception)['player_message']

    def test_null_and_empty_say_mains_line_and_never_echo(self):
        for declared in (None, []):
            for text in self.MESSAGES:
                with self.subTest(text=text, declared=declared):
                    arena = kiln(self, warlock(hp=60, gear=['dagger']))
                    expected = self.mains_line(arena, text)
                    before = copy.deepcopy(arena.fight)
                    bridge = KitChatBridge(arena.runtime, arena.adjudicator)
                    packet = bridge.prepare(text, 'n', one_pass=True)
                    plan = plan_for(packet)
                    plan['combat_acts'] = declared
                    result = bridge.complete('n', {'decision': plan, 'performance': {'segments': [
                        {'speaker': 'Narrator', 'text': 'You hold.'}]}})
                    self.assertIn(expected, result['spoken'])
                    self.assertNotIn('You declare', result['spoken'])
                    self.assertEqual((arena.fight['hp'], arena.fight['pc_damage']), (before['hp'], before['pc_damage']))

    def test_a_declaration_still_replaces_it(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger']))
        _, result = turn(arena, 'Nik backs off 30 feet down the hall.', [A('move', 1, way='away', distance_ft=30)])
        self.assertIn('fall back out of reach', result['spoken'])
        self.assertNotIn("DM's call", result['spoken'])


if __name__ == '__main__':
    unittest.main()

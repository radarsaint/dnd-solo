"""PR-H, second half: progressive reveal on room entry, the per-turn handoff trace, and the
adversarial cases Nik will push in the 5-room test (barging in, split actions, asking for a
check mid-window, flourishing early, answering a window with something else, and a centipede
ambush whose Con save meets a Shield window). Non-6c fixtures (carcass, roadcamp, watchroom);
every die pinned; no model."""
import copy
import io
import json
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from runtime import kit_handoff, kit_reveal, kit_rooms
from runtime.kit_agent import KitChatBridge, PendingRuling
from runtime.state_context import InvalidChange
from test_kit_combat_checkpoints import Camp, KILL_CAPTAIN, OPEN
from test_kit_monster_initiative import Room, carcass
from test_kit_short_beats import PERCEPTION, ShortBeat

ROOT = Path(__file__).resolve().parents[1]
CARCASS_LOOK = ('A basilisk carcass sprawls across the floor of the hall, grey hide split and stinking, its '
                'stone-dull eyes still open toward the stair you came down, one foreleg folded under the bulk '
                'of it as if it lay down to sleep and never got up again.')
CARCASS_MORE = ('Nothing else moves. The stink is thick enough to taste, sweet and wrong, and the hide twitches '
                'once where the light from the stair falls across it, then lies still, heavy and grey, between '
                'you and the rest of the hall.')
KIT_HANDOFF = 'Where do you look first?'
POURED = ('Serpents coil up every pillar, carved so fine the scales catch the light, and the ceiling they '
          'hold up is lost in the dark.')


def plan_for(packet, **update):
    from test_kit_agent import RecordingModel
    plan = RecordingModel().plan(packet['input']['private'])
    plan.update({'move': 'world_description', 'table_presence': 'brief', 'focus_actor': 'none', **update})
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    plan['public_brief'].update(reply_to='none', scope='feature')
    return plan


def trace(runtime):
    return kit_handoff.read(kit_handoff.trace_path(runtime))


def kit_line(text, quote='A basilisk carcass sprawls'):
    return {'speaker': 'Kit', 'text': text, 'reacts_to': quote}


class Reveal(unittest.TestCase):
    def opening(self, source=None):
        room = Room(self, source=source)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        return room, bridge, bridge.prepare(opening=True, one_pass=True, turn_id='open')

    def enter(self, room, bridge, packet, segments):
        return bridge.complete('open', {'decision': plan_for(packet), 'performance': {'segments': segments}})

    def test_room_entry_gets_the_obvious_layer_and_holds_the_rest(self):
        _, _, packet = self.opening()
        reveal = packet['input']['private']['reveal']
        self.assertEqual(reveal['obvious'], [carcass()['facts']['carcass']['text']])
        self.assertEqual(reveal['hold'], ['Pillars carved with coiling serpents hold...'])
        self.assertTrue(any('obvious layer' in line for line in packet['first_try']))

    def test_the_entry_ends_with_kit_handing_the_floor_back(self):
        room, bridge, packet = self.opening()
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            self.enter(room, bridge, packet, [{'speaker': 'Narrator', 'text': CARCASS_LOOK},
                                              {'speaker': 'Narrator', 'text': CARCASS_MORE}])
        result = self.enter(room, bridge, packet, [{'speaker': 'Narrator', 'text': CARCASS_LOOK},
                                                   {'speaker': 'Narrator', 'text': CARCASS_MORE},
                                                   kit_line(KIT_HANDOFF)])
        self.assertTrue(result['spoken'].endswith('Kit: Where do you look first?'))

    def test_pouring_out_the_held_layer_is_refused(self):
        source = carcass()
        source['facts']['urns'] = {'area': 'hall', 'visible': True,
                                   'text': 'Cracked funeral urns lean against the far wall, spilling ash.'}
        room, bridge, packet = self.opening(source)
        with self.assertRaisesRegex(InvalidChange, 'held layer'):
            self.enter(room, bridge, packet, [{'speaker': 'Narrator', 'text': CARCASS_LOOK + ' ' + POURED +
                                               ' Cracked funeral urns lean on the wall, spilling ash.'},
                                              kit_line(KIT_HANDOFF)])

    def test_the_layers_come_from_room_data(self):
        source = carcass()
        source['facts']['carcass']['layer'] = 'detail'
        source['facts']['pillars']['layer'] = 'obvious'
        split = kit_reveal.layers(kit_rooms.check_room(source), {'area': 'hall'})
        self.assertEqual(split, {'obvious': ['pillars'], 'detail': ['carcass']})
        source['facts']['pillars']['layer'] = 'loud'
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'layer must be obvious or detail'):
            kit_rooms.check_room(source)

    def test_no_reveal_when_nothing_is_held_or_after_the_first_look(self):
        source = carcass()
        del source['facts']['pillars']
        _, _, packet = self.opening(source)
        self.assertNotIn('reveal', packet['input']['private'])
        room, bridge, packet = self.opening()
        self.enter(room, bridge, packet, [{'speaker': 'Narrator', 'text': CARCASS_LOOK}, {'speaker': 'Narrator', 'text': CARCASS_MORE}, kit_line(KIT_HANDOFF)])
        later = bridge.prepare('I look around the hall.', 'look', one_pass=True)
        self.assertNotIn('reveal', later['input']['private'])

    def test_the_reveal_is_traced_and_the_next_look_takes_the_floor(self):
        room, bridge, packet = self.opening()
        self.enter(room, bridge, packet, [{'speaker': 'Narrator', 'text': CARCASS_LOOK}, {'speaker': 'Narrator', 'text': CARCASS_MORE}, kit_line(KIT_HANDOFF)])
        first = trace(room.runtime)[-1]
        self.assertEqual(first['handoff']['type'], 'progressive_reveal')
        self.assertEqual(first['handoff']['trigger'], 'first look: hall')
        look = bridge.prepare('I look at the pillars.', 'look', one_pass=True)
        plan = plan_for(look)
        plan['public_brief'].update(reply_to='look at the pillars')
        bridge.complete('look', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'The serpents carved up each pillar are worn smooth where hands have '
                                            'touched them, as if people once leaned here to rest a while, and '
                                            'the stone between the coils is dark with old soot.'},
            {'speaker': 'Narrator', 'text': 'Up close the carving is finer than it looked from the stair: every '
                                            'scale cut separately, every eye a drilled pit, and one serpent near '
                                            'the floor has had its head broken off and carried away, the break '
                                            'clean and old, the edges gone soft with years of dust and damp.'}]}})
        answer = trace(room.runtime)[-1]['answers']
        self.assertEqual((answer['turn_id'], answer['type'], answer['floor_to_player']),
                         ('open', 'progressive_reveal', True))


class Trace(unittest.TestCase):
    def camp(self):
        camp = Camp(self)
        return camp, KitChatBridge(camp.runtime, camp.adjudicator)

    def test_every_committed_turn_writes_a_line_in_the_session_dir(self):
        camp, bridge = self.camp()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        path = kit_handoff.trace_path(camp.runtime)
        self.assertEqual(path.parent, Path(camp.runtime.path).resolve().parent)
        (line,) = trace(camp.runtime)
        self.assertEqual(line['event'], 'turn')
        self.assertEqual(line['handoff']['type'], 'reaction_window')
        self.assertEqual(line['handoff']['trigger'], 'hit')
        self.assertEqual(line['handoff']['awaits'], 'player_answer')
        self.assertIsNotNone(line['latency_s'])

    def test_a_held_input_is_logged_and_the_floor_verdict_is_the_first_inputs(self):
        camp, bridge = self.camp()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        with self.assertRaises(PendingRuling):
            bridge.prepare('Can I make an Arcana check on his blade?', 'h2', one_pass=True)
        held = trace(camp.runtime)[-1]
        self.assertEqual(held['event'], 'held_input')
        self.assertEqual((held['answers']['type'], held['answers']['floor_to_player']), ('reaction_window', False))
        bridge.prepare('Yes, Shield.', 'h3', one_pass=True)  # the answer: a full Kit turn, staged
        rows = kit_handoff.summary(trace(camp.runtime))
        self.assertEqual(rows[0]['floor_to_player'], False)
        self.assertEqual(rows[0]['attempts'], 1)

    def test_the_cli_dumps_rows_and_refreshes_latency_from_host_stamps(self):
        camp, bridge = self.camp()
        now = time.time()
        bridge.prepare(OPEN, 'h1', one_pass=True, host_stamps={'received_at': now - 2.5})
        bridge.stamp('h1', shown_at=now)
        from scripts import handoff_trace
        out = io.StringIO()
        with redirect_stdout(out):
            handoff_trace.main([str(camp.runtime.path), '--json'])
        (row,) = json.loads(out.getvalue())
        self.assertEqual(row['handoff'], 'reaction_window')
        self.assertEqual(row['latency_from'], 'host_stamps')
        self.assertAlmostEqual(row['latency_s'], 2.5, places=2)
        out = io.StringIO()
        with redirect_stdout(out):
            handoff_trace.main([str(Path(camp.runtime.path).parent)])
        self.assertIn('reaction_window', out.getvalue())
        self.assertIn('trigger: hit', out.getvalue())


class BargingIn(ShortBeat):
    """Nik barges in during a held stall check."""

    def test_barging_through_the_door_is_honoured_but_the_stall_is_not_answered(self):
        self.stall(roll_call=PERCEPTION)
        packet = self.bridge.prepare('I go through the iron door.', 'in', one_pass=True)
        plan = self.plan_for(packet, table_presence='brief')
        plan['public_brief'].update(reply_to='go through the iron door', scope='feature')
        self.bridge.complete('in', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'Lamplight pools on a scarred table where a warden in a dented helm '
                                            'hums over a ledger, a plain wooden chest under the arrow slit behind '
                                            'him, his spear propped within easy reach of his hand.'},
            {'speaker': 'Narrator', 'text': 'He looks up at the sound of the door and stops humming, and for a '
                                            'long moment the only thing moving in the room is the lamp flame, '
                                            'bending a little in the draught you let in, throwing his shadow '
                                            'long across the boards toward your boots.'},
            kit_line('Where do you look first?', 'go through the iron door')]}})
        lines = trace(self.runtime)
        self.assertEqual(lines[0]['handoff']['type'], 'stall_check')
        answer = lines[-1]['answers']
        self.assertEqual((answer['type'], answer['floor_to_player']), ('stall_check', False))
        self.assertIn('barged in without the roll', answer['how'])
        self.assertEqual(lines[-1]['handoff']['type'], 'progressive_reveal')

    def test_a_barge_that_stays_put_still_owes_the_held_description(self):
        self.stall(roll_call=PERCEPTION)
        packet = self.bridge.prepare('I kick the iron door open.', 'k', one_pass=True)
        held = packet['input']['private']['held_description']
        self.assertIsNone(held['roll'])
        self.assertIn('did not roll', held['rule'])


class SplitActions(unittest.TestCase):
    def test_a_reaction_answer_with_an_attack_tacked_on_resolves_only_the_reaction(self):
        camp = Camp(self)
        camp.act(OPEN)
        camp.act('Yes, Shield. Then I Fire Bolt the bandit captain, 19 to hit, 9 fire.')
        self.assertEqual(camp.fight['hp']['harl'], camp.fight['max_hp']['harl'], 'not his turn: no Fire Bolt')
        self.assertEqual(sum(camp.fight.get('slots_spent', {}).values()), 1, 'Shield was cast')

    def test_disturbing_the_carcass_and_attacking_in_one_breath_waits_for_initiative(self):
        room = Room(self)
        result = room.act('I roll the carcass over and stab whatever comes out with my dagger, 18 to hit, 4 piercing.')
        self.assertTrue(result.public_event.endswith('Roll initiative.'))
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')
        self.assertEqual(room.state['combat']['hp'], room.state['combat']['max_hp'], 'nothing was there to stab')


class ChecksMidWindow(unittest.TestCase):
    def test_asking_for_a_check_while_a_window_is_open_holds_the_window(self):
        camp = Camp(self)
        camp.act(OPEN)
        waiting = copy.deepcopy(camp.fight['awaiting'])
        revision, state = camp.runtime.load()
        for line in ('Can I make an Arcana check?', 'Perception check: 17'):
            with self.subTest(line), self.assertRaises(PendingRuling):
                camp.adjudicator.resolve(line, revision, state)
        self.assertEqual(camp.fight['awaiting'], waiting)
        self.assertEqual(camp.fight['pc_damage'], 0)


class EarlyFlourish(unittest.TestCase):
    def test_describing_the_kill_with_a_miss_kills_nobody(self):
        camp = Camp(self)
        result = camp.act('Initiative 25. I stab the bandit captain through the throat and he dies at my feet, '
                          '4 to hit, 30 piercing.')
        self.assertEqual(camp.state['actors']['harl']['status'], 'alive')
        self.assertNotEqual((camp.fight.get('awaiting') or {}).get('kind'), 'flourish_window')
        self.assertNotIn('goes down', result.public_event)

    def test_describing_the_kill_with_no_roll_waits_for_the_roll(self):
        camp = Camp(self)
        revision, state = camp.runtime.load()
        with self.assertRaises(PendingRuling):
            camp.adjudicator.resolve('I slit the bandit captain\'s throat and he falls dead.', revision, state)
        self.assertEqual(camp.state['actors']['harl']['status'], 'alive')

    def test_the_flourish_after_a_real_kill_changes_no_outcome(self):
        camp = Camp(self)
        camp.act(KILL_CAPTAIN)
        before = copy.deepcopy(camp.state['actors'])
        camp.act('I wrench the dagger free and kick the other two bandits dead as well.')
        after = camp.state['actors']
        self.assertEqual(after['cutthroat_a']['status'], before['cutthroat_a']['status'])
        self.assertEqual(after['cutthroat_b']['status'], before['cutthroat_b']['status'])


class AnotherActionAsTheAnswer(unittest.TestCase):
    def test_an_attack_instead_of_a_shield_answer_is_held(self):
        camp = Camp(self)
        camp.act(OPEN)
        waiting = copy.deepcopy(camp.fight['awaiting'])
        revision, state = camp.runtime.load()
        with self.assertRaises(PendingRuling) as caught:
            camp.adjudicator.resolve('I stab the bandit captain with my dagger, 18 to hit, 30 piercing.',
                                     revision, state)
        self.assertIn('Shield', str(caught.exception))
        self.assertEqual(camp.fight['awaiting'], waiting)
        self.assertEqual(camp.state['actors']['harl']['status'], 'alive')


class AmbushSaveMeetsShield(unittest.TestCase):
    """Order: the reaction first (before damage), then the save the hit carries."""

    def ambushed(self):
        # Stealth 1 + 2 = 3: Nik is not surprised. Bites d20 12 + 4 = 16: hit AC 14, miss AC 19.
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 12)
        room.act('I roll the carcass over.')
        result = room.act('Initiative 1')
        return room, result

    def test_the_shield_window_comes_first_and_no_damage_lands_before_it(self):
        room, result = self.ambushed()
        waiting = room.state['combat']['awaiting']
        self.assertEqual((waiting['kind'], waiting['options']), ('reaction_window', ['shield']))
        self.assertEqual(waiting['rider']['ability'], 'con')
        self.assertEqual(room.state['combat']['pc_damage'], 0)
        self.assertTrue(result.public_event.endswith('That hits 16. Shield?'))

    def test_a_save_stated_during_the_shield_window_is_not_an_answer(self):
        room, _ = self.ambushed()
        revision, state = room.runtime.load()
        with self.assertRaises(PendingRuling):
            room.adjudicator.resolve('Con save 12', revision, state)

    def test_declining_shield_takes_the_bite_then_asks_for_the_save(self):
        room, _ = self.ambushed()
        result = room.act('No.')
        combat = room.state['combat']
        self.assertEqual(combat['pc_damage'], 4)
        self.assertEqual((combat['awaiting']['kind'], combat['awaiting']['save']), ('roll_call', 'con'))
        self.assertTrue(result.public_event.endswith('Roll a Constitution saving throw.'))
        self.assertNotIn('11', result.public_event)
        result = room.act('Con save 5')
        combat = room.state['combat']
        self.assertEqual(combat['pc_damage'], 4 + 10, 'the poison lands')
        self.assertEqual(combat['awaiting']['kind'], 'reaction_window', 'declining kept the reaction: offered again')
        room.act('No.')
        self.assertEqual(room.state['combat']['awaiting']['kind'], 'roll_call')
        result = room.act('Con save 15')
        self.assertTrue(result.public_event.endswith('Your turn.'))
        self.assertEqual(room.state['combat']['pc_damage'], 18)

    def test_shield_turns_the_bite_so_no_save_is_owed(self):
        room, _ = self.ambushed()
        result = room.act('Yes, Shield.')
        combat = room.state['combat']
        self.assertEqual(combat['pc_damage'], 0)
        self.assertIsNone(combat.get('awaiting'))
        self.assertTrue(result.public_event.endswith('Your turn.'))


class AmbushTrace(unittest.TestCase):
    def test_the_save_is_traced_as_an_engine_roll_call(self):
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 12)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        room.act('I roll the carcass over.')
        bridge.prepare('Initiative 1', 'i', one_pass=True)
        bridge.prepare('No.', 'n', one_pass=True)
        lines = trace(room.runtime)
        self.assertEqual([(line['handoff']['type'], line['handoff']['trigger']) for line in lines],
                         [('reaction_window', 'hit'), ('roll_call', 'save_rider')])
        self.assertEqual(lines[1]['answers']['floor_to_player'], True)


if __name__ == '__main__':
    unittest.main()

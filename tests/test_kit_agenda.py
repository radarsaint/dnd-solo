"""Agendas, backgrounded activities, salience, conditioned advantage, natural routing.

Tiny synthetic rooms of different kinds (social, empty/environmental, lair with an absent
owner, a faction across rooms, combat, quiet) show one mechanism covers them all; 6c is
used only for the bridge round trip, with an agenda supplied by the test."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agenda, kit_agent, kit_cards, kit_detail, pc_sheet
from runtime.kit_agent import Room6CAdjudicator, room_intent
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel

NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())
SIXC = json.loads(FIXTURE.read_text())


def room(agenda, actors=None, facts=None, claims=None, areas=('hall', 'crypt', 'lair')):
    return {'areas': {a: {} for a in areas},
            'facts': facts or {'dust': {'area': 'hall', 'visible': True}, 'drip': {'area': 'crypt', 'visible': True},
                               'bones': {'area': 'lair', 'visible': True},
                               'loose_stone': {'area': 'hall', 'visible': False}},
            'actors': actors or {}, 'claims': claims or {}, 'agenda': agenda}


def state(area, actors=None, mem=None, sheet=None):
    out = {'area': area, 'actors': copy.deepcopy(actors or {}), 'known_facts': [], 'player_sheet': sheet}
    if mem:
        out['agenda'] = mem
    return out


def move(does, roots, **extra):
    return {'does': does, 'roots': roots, **extra}


ENVIRONMENT = {'agents': {'crypt_air': {
    'kind': 'environment', 'areas': ['crypt'], 'wants': 'to smother the torch and the one carrying it',
    'roots': ['drip'], 'moves': {'gutter': move('The torch gutters as the drip quickens.', ['drip'])}}},
    'pressures': {'flood': {'segments': 4, 'ticks_on': 'time spent below', 'when_full': 'the crypt floods waist-deep',
                            'roots': ['drip'], 'areas': ['crypt']}}}


def advance(agent, move_id, does='It moves.', roots=('dust',), why='It wants the player gone.'):
    return {'agent': agent, 'move': move_id, 'does': does, 'roots': list(roots), 'why': why}


def block(advances=(), ticks=(), reason='none', agent='none', why='Something moved this turn.'):
    return {'advances': list(advances), 'ticks': list(ticks), 'hold': {'reason': reason, 'agent': agent, 'why': why}}


class CompileTests(unittest.TestCase):
    def test_every_kind_of_room_compiles_with_one_schema(self):
        actors = {'ogre': {'location': 'lair', 'status': 'alive'}, 'guide': {'location': 'hall', 'status': 'alive'}}
        agenda = {'every': 1, 'pace': {'hall': 3}, 'agents': {
            **ENVIRONMENT['agents'],
            'ogre': {'kind': 'monster', 'actor': 'ogre', 'disposition': 'hostile', 'areas': ['lair'],
                     'wants': 'to eat whoever sleeps in its bed', 'roots': ['bones'],
                     'moves': {'returns': move('Heavy steps come up the passage.', ['bones'], trigger='elsewhere')}},
            'cult': {'kind': 'faction', 'areas': '*', 'wants': 'the intruder marked for the altar', 'roots': ['dust'],
                     'moves': {'scout': move('A hooded watcher is seen and gone.', ['dust'], ticks='ritual')}},
            'guide': {'kind': 'npc', 'actor': 'guide', 'disposition': 'friendly', 'wants': 'safe passage out',
                      'roots': ['guide'], 'moves': {'nudge': move('The guide tugs a sleeve.', ['guide'])}}},
            'pressures': {**ENVIRONMENT['pressures'],
                          'ritual': {'segments': 6, 'ticks_on': 'each scouting report', 'when_full': 'the cult comes in force',
                                     'roots': ['dust']}}}
        self.assertEqual(set(kit_agenda.compile_agenda(room(agenda, actors))['agents']), {'crypt_air', 'ogre', 'cult', 'guide'})

    def test_ungrounded_or_placeless_agents_are_rejected(self):
        bad = copy.deepcopy(ENVIRONMENT)
        bad['agents']['crypt_air']['moves']['gutter']['roots'] = ['a_ghost_nobody_wrote']
        with self.assertRaisesRegex(InvalidChange, 'roots must cite'):
            kit_agenda.compile_agenda(room(bad))
        bad = copy.deepcopy(ENVIRONMENT)
        del bad['agents']['crypt_air']['areas']
        with self.assertRaisesRegex(InvalidChange, 'needs areas'):
            kit_agenda.compile_agenda(room(bad))


class PresenceAndPacingTests(unittest.TestCase):
    def test_an_empty_room_is_its_own_actor_and_must_move(self):
        packet = kit_agenda.agenda_here(room(ENVIRONMENT), state('crypt'))
        self.assertEqual(packet['agents']['crypt_air']['presence'], 'onstage')
        self.assertTrue(packet['must_advance'])
        with self.assertRaisesRegex(InvalidChange, 'waited long enough'):
            kit_agenda.check_agenda(block(reason='paced', why='Nothing to do.'), packet, room(ENVIRONMENT), state('crypt'))
        ticks = kit_agenda.check_agenda(block(ticks=[{'pressure': 'flood', 'by': 1, 'why': 'Time passes below.'}]),
                                        packet, room(ENVIRONMENT), state('crypt'))
        self.assertEqual(ticks, {'flood': 1})

    def test_a_quiet_room_is_valid_and_a_calm_pace_can_wait(self):
        source = room(ENVIRONMENT)
        quiet = kit_agenda.agenda_here(source, state('hall'))
        self.assertFalse(quiet['must_advance'])
        kit_agenda.check_agenda(block(reason='quiet', why='Nothing here wants anything.'), quiet, source, state('hall'))
        paced = copy.deepcopy(ENVIRONMENT)
        paced['pace'] = {'crypt': 3}
        packet = kit_agenda.agenda_here(room(paced), state('crypt', mem={'turn': 1, 'last_advance': 0,
                                                                        'clocks': {}, 'last_acted': {}}))
        self.assertFalse(packet['must_advance'])
        kit_agenda.check_agenda(block(reason='paced', why='The drip is slow tonight.'), packet, room(paced), state('crypt'))
        with self.assertRaisesRegex(InvalidChange, 'Not quiet'):
            kit_agenda.check_agenda(block(reason='quiet', why='Calm.'), packet, room(paced), state('crypt'))

    def test_a_lair_owner_acts_from_offstage_and_a_faction_clock_spans_rooms(self):
        actors = {'ogre': {'location': 'crypt', 'status': 'alive'}}
        agenda = {'agents': {'ogre': {'kind': 'monster', 'actor': 'ogre', 'areas': ['lair'], 'disposition': 'hostile',
                                      'wants': 'its bed undisturbed', 'roots': ['bones'],
                                      'moves': {'returns': move('Heavy steps.', ['bones'], ticks='return')}}},
                  'pressures': {'return': {'segments': 3, 'ticks_on': 'noise', 'when_full': 'the ogre is home',
                                           'roots': ['bones']}}}
        source = room(agenda, actors)
        lair = state('lair', actors)
        packet = kit_agenda.agenda_here(source, lair)
        self.assertEqual(packet['agents']['ogre']['presence'], 'offstage')
        ticks = kit_agenda.check_agenda(block([advance('ogre', 'returns', roots=['bones'])]), packet, source, lair)
        kit_agenda.apply_event(lair, source, kit_agenda.agenda_event(block([advance('ogre', 'returns')]), packet, 't1', ticks))
        self.assertEqual((lair['agenda']['clocks'], lair['agenda']['last_acted']), ({'return': 1}, {'ogre': 1}))
        # Walk to the hall: the ogre is not here, but the clock (areas "*") persists and shows.
        hall = state('hall', actors, mem=lair['agenda'])
        packet = kit_agenda.agenda_here(source, hall)
        self.assertEqual((packet['agents'], packet['pressures']['return']['filled']), ({}, 1))
        # Killed: no longer acts anywhere.
        dead = state('lair', {'ogre': {'location': 'crypt', 'status': 'dead'}})
        self.assertEqual(kit_agenda.agenda_here(source, dead)['agents'], {})

    def test_combat_monster_engaged_hold_and_full_clock(self):
        actors = {'goblin': {'location': 'hall', 'status': 'alive'}}
        agenda = {'agents': {'goblin': {'kind': 'monster', 'actor': 'goblin', 'disposition': 'hostile',
                                        'wants': 'to live, and to take the PC\'s purse', 'roots': ['goblin'],
                                        'moves': {'flee': move('Breaks for the door when hurt.', ['goblin'], trigger='engaged')}}},
                  'pressures': {'morale': {'segments': 2, 'ticks_on': 'each goblin wound', 'when_full': 'it flees',
                                           'roots': ['goblin']}}}
        source = room(agenda, actors)
        here = state('hall', actors, mem={'turn': 3, 'last_advance': 3, 'clocks': {'morale': 2}, 'last_acted': {}})
        packet = kit_agenda.agenda_here(source, here)
        with self.assertRaisesRegex(InvalidChange, 'is full'):
            kit_agenda.check_agenda(block(ticks=[{'pressure': 'morale', 'by': 1, 'why': 'Another wound.'}]),
                                    packet, source, here)
        kit_agenda.check_agenda(block(reason='engaged', agent='goblin', why='The duel itself presses its want.'),
                                packet, source, here)
        with self.assertRaisesRegex(InvalidChange, 'onstage agent'):
            kit_agenda.check_agenda(block(reason='engaged', agent='nobody', why='The duel itself presses it.'),
                                    packet, source, here)

    def test_moves_respect_knower_bands(self):
        actors = {'thug': {'location': 'hall', 'status': 'alive', 'stats': {}}}
        claims = {'stone': {'about': 'object:hall/stone', 'truth': 'A key is behind the loose stone.', 'source': 'adventure',
                            'fact': 'loose_stone', 'roots': ['loose_stone'], 'exposure': 'hidden', 'dc': 15,
                            'pc_check': 'investigation', 'pc_access': 'roll', 'holders': {'thug': 'unaware'}}}
        agenda = {'agents': {'thug': {'kind': 'npc', 'actor': 'thug', 'wants': 'the PC\'s coin', 'roots': ['thug'],
                                      'moves': {'guard_key': move('Stands by the stone.', ['loose_stone']),
                                                'shake_down': move('Holds out a palm.', ['thug'])}}}}
        source = room(agenda, actors, claims=claims)
        here = state('hall', actors)
        packet = kit_agenda.agenda_here(source, here)
        self.assertEqual(list(packet['agents']['thug']['moves']), ['shake_down'])
        self.assertIn('unaware of stone', packet['agents']['thug']['blocked_moves']['guard_key'])
        with self.assertRaisesRegex(InvalidChange, 'unaware of stone'):
            kit_agenda.check_agenda(block([advance('thug', 'guard_key')]), packet, source, here)
        with self.assertRaisesRegex(InvalidChange, 'unaware of stone'):
            kit_agenda.check_agenda(block([advance('thug', 'new', roots=['stone'])]), packet, source, here)
        kit_agenda.check_agenda(block([advance('thug', 'new', roots=['dust'])]), packet, source, here)


class SalienceAndAdvantageTests(unittest.TestCase):
    def test_attention_needs_a_visible_reason(self):
        source = room(ENVIRONMENT)
        here = state('hall')
        with self.assertRaisesRegex(InvalidChange, 'salience'):
            kit_agenda.check_attention_spoken('Narrator: The carving catches your eye.', {})
        kit_agenda.check_salience([{'thing': 'dust', 'reason': 'one clean handprint in thick dust', 'roots': ['dust']}],
                                  source, here)
        with self.assertRaisesRegex(InvalidChange, 'never a secret'):
            kit_agenda.check_salience([{'thing': 'stone', 'reason': 'it hides the key behind it',
                                        'roots': ['loose_stone']}], source, here)

    def test_advantage_needs_a_condition_true_now(self):
        call = {'skill': 'perception', 'mode': 'advantage', 'cause': {'kind': 'item', 'ref': 'Sentinel Shield', 'roots': []}}
        with self.assertRaisesRegex(InvalidChange, 'owning it is not holding it'):
            kit_agenda.check_roll_call(call, SIXC, {'player_sheet': NIK})
        kit_agenda.check_roll_call(call, SIXC, {'player_sheet': {**NIK, 'held': ['Sentinel Shield']}})
        with self.assertRaisesRegex(InvalidChange, 'name Sentinel Shield'):
            kit_agenda.check_roll_spoken('Narrator: Roll Perception with advantage.', {'roll_call': call})
        kit_agenda.check_roll_spoken('Narrator: Shield up, so the Sentinel Shield lets you roll Perception with advantage.',
                                     {'roll_call': call})

    def test_held_state_changes_the_passive_in_play(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(copy.deepcopy(SIXC), 'area_06c')
        runtime.set_player_sheet(NIK)
        self.assertEqual(pc_sheet.passive(runtime.load()[1]['player_sheet'], 'perception'), 14)
        runtime.set_pc_state(held=['Sentinel Shield'])
        self.assertEqual(pc_sheet.passive(runtime.load()[1]['player_sheet'], 'perception'), 19)


class RoutingTests(unittest.TestCase):
    def test_natural_table_talk_and_detail_questions(self):
        for text in ('Kit, how does the ante work?', 'Do I get advantage here?', 'what is the DC for that?'):
            self.assertTrue(kit_agent.is_ooc(text), text)
        for text in ('Can I sneak past them?', '"Kit? Never heard of her," I say.', 'I ask the dealer his name.'):
            self.assertFalse(kit_agent.is_ooc(text), text)
        self.assertTrue(kit_detail.asks_for_detail('Whats the game?'))
        self.assertEqual(room_intent('I look around the room.'), 'observe')
        self.assertEqual(room_intent('What else is in here?'), 'observe')

    def test_looking_away_backgrounds_a_live_card_procedure(self):
        config = SIXC['procedures'][next(k for k, v in SIXC['procedures'].items()
                                        if isinstance(v, dict) and v.get('kind') == 'card_game')]
        body = kit_cards.initial_state(config)
        key = next(k for k, v in SIXC['procedures'].items() if isinstance(v, dict) and v.get('kind') == 'card_game')
        live = {'area': 'area_06c', 'roll_seed': 'x', 'known_facts': [], 'actors': SIXC['actors'],
                'procedures': {key: body}}
        result = Room6CAdjudicator(source=SIXC).resolve('I look around the rest of the room.', 1, live)
        self.assertEqual(result.kind, 'observe')
        self.assertFalse(any(e['type'] == 'procedure_state' for e in result.events))


class BridgeAgendaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        source = copy.deepcopy(SIXC)
        source['agenda'] = {'agents': {'uktarl': {
            'kind': 'npc', 'actor': 'uktarl', 'wants': 'the newcomer\'s coin',
            'roots': ['uktarl', 'card_table'], 'moves': {'probe': move('Asks what the newcomer carries.', ['uktarl'])}}}}
        self.runtime.initialize(source, 'area_06c')

    def test_decision_must_advance_and_finish_persists_it(self):
        bridge = kit_agent.KitChatBridge(self.runtime)
        packet = bridge.prepare('I listen to the dealer.', one_pass=True)
        private = packet['input']['private']
        self.assertTrue(private['agenda_here']['must_advance'])
        plan = RecordingModel().plan(private)
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'He turns a coin between finger and thumb, then sets it down beside the deck.'},
            {'speaker': 'Dealer', 'text': 'You listen well. Most who come down here talk first and pay later, so '
             'keep your hands above the table while I deal; my friends have curious habits, and I have a '
             'living to make before the next traveler wanders through.'},
            {'speaker': 'Kit', 'text': 'The jeweler has finished. The bouncer gets a turn.',
             'reacts_to': 'keep your hands above the table'}]}
        with self.assertRaisesRegex(InvalidChange, 'This scene has an agenda'):
            bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})
        plan['agenda'] = block([advance('uktarl', 'probe', roots=['uktarl'])])
        bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})
        mem = self.runtime.load()[1]['agenda']
        self.assertEqual((mem['turn'], mem['last_acted'], mem['last_advance']), (1, {'uktarl': 1}, 1))


if __name__ == '__main__':
    unittest.main()

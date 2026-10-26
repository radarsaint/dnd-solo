"""Companions (runtime/kit_party.py): real combatants run by deterministic tactics, with
capability, knowledge and turn-ownership isolation enforced in code. Fixtures are original."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_combat, kit_party
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import InvalidChange, Runtime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'adventures' / 'lantern_ferry.txt'
NIK = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'
SHEETS = ROOT / 'tests' / 'fixtures' / 'companions'
PARTY = (('brannoc', 'defender', 'balanced'), ('tamsin', 'striker', 'balanced'), ('odile', 'healer', 'conserve'))
FIRE_BOLT = ('I hit the Lantern Wight with Fire Bolt.\nNik casts Fire Bolt!\n'
             '**To Hit**: 1d20 (12) + 7 = `19`\n**Damage**: 2d10 (4, 5) [fire] = `9`')
INITIATIVE = 'Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`'


def sheet(name):
    return json.loads((SHEETS / f'{name}.json').read_text())


class Table(unittest.TestCase):
    """Nik and three companions in compiled area 3 of the synthetic Lantern Ferry."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'kit.sqlite'
        kit_adventure.import_adventure(self.db, text=FIXTURE.read_text())
        kit_adventure.compile_location(self.db, '3', neighbours=False)
        self.room_path = kit_adventure.room_file(self.db, '3')

    def begin(self, party=PARTY, edit=None):
        if edit:
            room = json.loads(self.room_path.read_text())
            edit(room)
            self.room_path.write_text(json.dumps(room))
        started = start_session(self.db, NIK, room=self.room_path)
        self.runtime = Runtime(self.db)
        self.addCleanup(self.runtime.close)
        self.asks = {key: self.runtime.add_companion(key, sheet(key), role, policy)['asks']
                     for key, role, policy in party}
        self.adjudicator = RoomAdjudicator(source=self.runtime.source())
        KitChatBridge(self.runtime, self.adjudicator).abandon(started['prepared']['turn_id'])
        self.commits = []

    def act(self, line):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(line, revision, state)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        self.commits.append((line, list(result.events)))
        return result, self.runtime.load()[1]

    def trace(self):
        return ' '.join(e.get('evidence', '') for _, events in self.commits for e in events
                        if e['type'] == 'combat_state')


class FourCharacterFight(Table):

    def test_pc_and_three_companions_fight_a_compiled_creature(self):
        self.begin()
        self.assertEqual(self.asks['odile'], ['Odile: Bless is not run by the engine (never cast)'])
        self.act('I look around the cellar.')  # the wight's trigger: revealed, fight starts
        _, state = self.act(INITIATIVE)
        self.assertEqual(sorted(state['combat']['order']), ['brannoc', 'lantern_wight', 'odile', 'pc', 'tamsin'])
        self.assertEqual(kit_combat.public_view(self.runtime.source(), state)['fight']['whose_turn'], 'you')
        for _ in range(4):
            _, state = self.act(FIRE_BOLT)
            if state['combat']['status'] == 'over':
                break
        self.assertEqual(state['combat']['status'], 'over')
        trace = self.trace()
        for key in ('brannoc', 'tamsin', 'odile'):
            self.assertIn(f'{key} tactics', trace)  # each companion acted on the engine
        self.assertIn('lantern lash at brannoc', trace)  # the defender holds it: it is targeted
        self.assertIn('tamsin rapier', trace)
        self.assertEqual(state['actors']['lantern_wight']['status'], 'dead')

    def test_allied_turns_need_no_model_and_the_packet_barely_grows(self):
        self.begin()
        self.act('I look around the cellar.')
        result, _ = self.act(INITIATIVE)
        self.assertIsNone(result.handoff)  # several allied turns, no model call
        view = kit_combat.public_view(self.runtime.source(), self.runtime.load()[1])
        party = json.dumps(view['fight']['party'])
        self.assertEqual(json.loads(party), {'Brannoc': 'unhurt', 'Tamsin': 'unhurt', 'Odile': 'unhurt'})
        self.assertLess(len(party), 80)  # the per-turn addition: names and one word each
        for secret in ('"hp"', '"ac"', 'to_hit', 'slots', 'ledger'):
            self.assertNotIn(secret, json.dumps(view))

    def test_reset_and_resume(self):
        self.begin()
        self.act('I look around the cellar.')
        self.act(INITIATIVE)
        before = self.runtime.load()[1]
        self.runtime.close()
        runtime = Runtime(self.db)  # a fresh Python process reads the save
        self.addCleanup(runtime.close)
        after = runtime.load()[1]
        self.assertEqual(after['party'], before['party'])
        self.assertEqual(after['combat'], before['combat'])
        self.runtime, self.adjudicator = runtime, RoomAdjudicator(source=runtime.source())
        for _ in range(4):
            _, state = self.act(FIRE_BOLT)
            if state['combat']['status'] == 'over':
                break
        self.assertEqual(state['combat']['status'], 'over')
        self.assertIn('tamsin tactics', self.trace())


class Ownership(Table):

    def test_every_pc_commit_comes_from_a_player_declaration(self):
        self.begin()
        calls = []
        real = kit_combat.Fight.pc_attack

        def spy(fight, act):
            calls.append(fight.action)
            return real(fight, act)
        with mock.patch.object(kit_combat.Fight, 'pc_attack', spy):
            self.act('I look around the cellar.')
            self.act(INITIATIVE)
            for _ in range(4):
                _, state = self.act(FIRE_BOLT)
                if state['combat']['status'] == 'over':
                    break
        attacks = [line for line, _ in self.commits if line == FIRE_BOLT]
        self.assertEqual(calls, attacks)  # one PC attack per declaration, none from companions
        for line, events in self.commits:
            for event in events:
                if event['type'] in ('combat_state', 'pc_resources', 'pc_conditions'):
                    self.assertTrue(event['evidence'].startswith(f'Player declared: {line[:40]}'))

    def test_the_round_stops_at_the_pc(self):
        self.begin()
        self.act('I look around the cellar.')
        _, state = self.act(INITIATIVE)
        combat = state['combat']
        self.assertEqual(combat['order'][combat['next']], 'pc')


class Knowledge(Table):

    def test_decision_cannot_see_hidden_creatures_or_secrets(self):
        def edit(room):
            room['actors']['lurking_wight'] = {
                'name': 'Lurking Wight', 'location': 'here', 'status': 'hidden', 'visible': False,
                'stat_block': copy.deepcopy(room['actors']['lantern_wight']['stat_block'])}
            room['triggers'].append({'id': 'second', 'on': {'disturb': 'dm_3'}, 'actors': ['lurking_wight']})
            room['facts']['dm_3']['handling'] = {'nouns': ['crates']}
            room['facts']['secret_weakness'] = {'area': 'here', 'visible': False,
                                                'text': 'The Lantern Wight is vulnerable to radiant damage.'}
        self.begin(edit=edit)
        seen = []
        real = kit_party.decide
        with mock.patch.object(kit_party, 'decide', lambda obs: (seen.append(copy.deepcopy(obs)), real(obs))[1]):
            self.act('I look around the cellar.')
            self.act(INITIATIVE)
            self.act(FIRE_BOLT)
        self.assertTrue(seen)
        for obs in seen:
            text = json.dumps(obs).lower()
            for secret in ('lurking', 'vulnerab', 'radiant', 'secret', '"ac"', '"hp"', 'dc', 'to_hit',
                           'armor', '27', '13'):
                self.assertNotIn(secret, text)
            self.assertEqual([f['id'] for f in obs['foes']], ['lantern_wight'])
            self.assertEqual(set(obs), {'me', 'allies', 'foes', 'round'})


class Fake:
    """The few Fight attributes kit_party uses, for rule-level tests."""

    def __init__(self, party, foes=(), d20=10):
        self.party = party
        self.fight = {'round': 1, 'hp': {f: 20 for f in foes}, 'max_hp': {f: 20 for f in foes}, 'pc_damage': 0}
        self.state = {'actors': {f: {'visible': True} for f in foes}}
        self.labels = {f: f.title() for f in foes}
        self.lines, self.trace, self.sheet, self.conditions, self.healed = [], [], {'name': 'Nik'}, [], []
        self.foes, self.d20, self.damage = list(foes), d20, []

    def hostiles(self):
        return [f for f in self.foes if self.fight['hp'][f] > 0]

    def stats(self, key):
        return {'ac': 12, 'hp': 20, 'saves': {}, 'attacks': [{'name': 'claw', 'to_hit': 4, 'damage': 30, 'type': 'x'}]}

    def die(self, tag):
        return self.d20

    def pc_hp(self):
        return 32

    def apply_damage(self, key, amount, dtype=None):
        self.damage.append((key, amount))
        self.fight['hp'][key] -= amount

    def heal(self, amount, why):
        self.healed.append(amount)


def party(**roles):
    return {key: kit_party.member(sheet(key), role, policy) for key, (role, policy) in roles.items()}


class Capability(unittest.TestCase):

    def test_only_the_sheet_is_legal(self):
        fake = Fake(party(odile=('healer', 'aggressive')), foes=['bandit'])
        names = {o['with'] for o in kit_party.legal_options(fake.party['odile'])}
        self.assertEqual(names, {'mace', 'sacred flame', 'cure wounds', 'healing word', 'guiding bolt', None})
        action, refused = kit_party.validate(fake, 'odile', {'act': 'cast', 'with': 'fireball', 'target': 'bandit'})
        self.assertEqual((action['act'], refused), ('dodge', "not on Odile's sheet or spent"))
        action, refused = kit_party.validate(fake, 'odile', {'act': 'attack', 'with': 'mace', 'target': 'hidden_one'})
        self.assertEqual(refused, 'no such visible foe')

    def test_engine_spends_slots_and_stops_when_empty(self):
        fake = Fake(party(odile=('striker', 'aggressive')), foes=['bandit'])
        fake.party['odile']['ledger']['slots'] = {'1': 1}
        kit_party.companion_turn(fake, 'odile')
        self.assertEqual(fake.party['odile']['ledger']['slots'], {'1': 0})
        self.assertIn('guiding bolt', ' '.join(fake.trace))
        kit_party.companion_turn(fake, 'odile')  # no slot left: a cantrip, never a free spell
        self.assertEqual(fake.party['odile']['ledger']['slots'], {'1': 0})
        self.assertNotIn('slot', {o['resource'] for o in kit_party.legal_options(fake.party['odile'])})

    def test_features_and_items_count_down(self):
        fake = Fake(party(brannoc=('defender', 'balanced')))
        me = fake.party['brannoc']
        me['hp'] = 10
        kit_party.companion_turn(fake, 'brannoc')
        self.assertEqual(me['hp'], 10 + 5 + 3)  # Second Wind: 1d10 + level, average
        me['hp'] = 10
        kit_party.companion_turn(fake, 'brannoc')
        self.assertEqual(me['hp'], 10 + 7)  # Potion of Healing: 2d4 + 2
        me['hp'] = 10
        kit_party.companion_turn(fake, 'brannoc')
        self.assertEqual((me['ledger']['uses'], me['ledger']['items']), ({'second wind': 0}, {'potion of healing': 0}))
        self.assertIn('fallback', ' '.join(fake.trace))  # nothing left that applies: Dodge, never frozen


class Sheets(unittest.TestCase):

    def test_incomplete_sheets_are_flagged_or_refused(self):
        caster = sheet('odile')
        caster['spells'] = {'cantrips': ['Sacred Flame'], '1': []}
        self.assertIn('Odile has spell slots but no prepared spells: which are prepared?',
                      kit_party.check_sheet(caster)[1])
        broken = sheet('brannoc')
        del broken['ac']
        with self.assertRaises(InvalidChange):
            kit_party.check_sheet(broken)
        no_dc = sheet('odile')
        del no_dc['spell_save_dc']
        with self.assertRaises(InvalidChange):
            kit_party.check_sheet(no_dc)
        bare = sheet('tamsin')
        bare['attacks'] = []
        self.assertIn('Tamsin: no attacks or cantrips listed; it can only Dodge', kit_party.check_sheet(bare)[1])


class Tactics(unittest.TestCase):

    def test_spending_policy(self):
        for policy, spends in (('conserve', False), ('balanced', False), ('aggressive', True)):
            fake = Fake(party(odile=('striker', policy)), foes=['bandit'])
            kit_party.companion_turn(fake, 'odile')
            self.assertEqual(fake.party['odile']['ledger']['slots']['1'] < 4, spends, policy)

    def test_healer_spends_on_a_downed_ally_even_conserving(self):
        fake = Fake(party(odile=('healer', 'conserve'), tamsin=('striker', 'balanced')), foes=['bandit'])
        kit_party.hurt_companion(fake, 'tamsin', 21)
        self.assertEqual(fake.party['tamsin']['status'], 'dying')
        kit_party.companion_turn(fake, 'odile')
        self.assertEqual(fake.party['tamsin']['status'], 'standing')
        self.assertEqual(fake.party['odile']['ledger']['slots']['1'], 3)
        self.assertIn('heal_downed_ally', ' '.join(fake.trace))

    def test_defender_guards_a_bloodied_ally(self):
        fake = Fake(party(brannoc=('defender', 'balanced'), tamsin=('striker', 'balanced')), foes=['a', 'b'])
        fake.party['tamsin']['hp'] = 5
        fake.fight['marks'] = {'tamsin': 'b'}
        kit_party.companion_turn(fake, 'brannoc')
        self.assertIn('guard_bloodied_ally: attack longsword -> b', ' '.join(fake.trace))
        self.assertEqual(kit_party.foe_target(fake, 'b'), 'brannoc')  # now in melee with the defender

    def test_no_foes_no_options_still_acts(self):
        fake = Fake(party(tamsin=('striker', 'balanced')))
        fake.party['tamsin']['sheet']['attacks'] = []
        kit_party.companion_turn(fake, 'tamsin')
        self.assertEqual(fake.lines, ['Tamsin takes the Dodge action.'])


class Combatant(unittest.TestCase):

    def test_targeted_downed_death_saves_and_revival(self):
        fake = Fake(party(tamsin=('striker', 'balanced')), foes=['bandit'], d20=15)
        fake.fight['marks'] = {'tamsin': 'bandit'}
        self.assertEqual(kit_party.foe_target(fake, 'bandit'), 'tamsin')
        fake.stats = lambda key: {'ac': 12, 'attacks': [{'name': 'claw', 'to_hit': 4, 'damage': 21, 'type': 'x'}]}
        kit_party.foe_attacks_companion(fake, 'bandit', 'tamsin')
        me = fake.party['tamsin']
        self.assertEqual((me['hp'], me['status']), (0, 'dying'))
        self.assertEqual(kit_party.foe_target(fake, 'bandit'), 'pc')  # the downed are left alone
        for _ in range(3):
            kit_party.companion_turn(fake, 'tamsin')  # d20 15: successes
        self.assertEqual(me['status'], 'stable')
        kit_party.heal(fake, 'tamsin', 4)
        self.assertEqual((me['status'], me['hp']), ('standing', 4))

    def test_failed_death_saves_and_massive_damage_kill(self):
        fake = Fake(party(tamsin=('striker', 'balanced')), d20=5)
        kit_party.hurt_companion(fake, 'tamsin', 21)
        for _ in range(3):
            kit_party.companion_turn(fake, 'tamsin')
        self.assertEqual(fake.party['tamsin']['status'], 'dead')
        fake = Fake(party(tamsin=('striker', 'balanced')))
        kit_party.hurt_companion(fake, 'tamsin', 42)
        self.assertEqual(fake.party['tamsin']['status'], 'dead')

    def test_conditions(self):
        fake = Fake(party(tamsin=('striker', 'balanced')), foes=['bandit'])
        fake.party['tamsin']['conditions'] = ['paralyzed']
        kit_party.companion_turn(fake, 'tamsin')
        self.assertEqual(fake.damage, [])
        self.assertIn('tamsin cannot act', fake.trace)
        rolls = iter([18, 3])
        fake.party['tamsin']['conditions'] = ['poisoned']
        fake.die = lambda tag: next(rolls)
        kit_party.companion_turn(fake, 'tamsin')  # disadvantage: 3 + 5 misses AC 12
        self.assertEqual(fake.damage, [])
        obs = kit_party.observe(fake, 'tamsin')
        self.assertEqual(obs['me']['conditions'], ['poisoned'])

    def test_roster_refuses_bad_entries(self):
        db = Path(tempfile.mkdtemp()) / 'kit.sqlite'
        runtime = Runtime(db)
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads((ROOT / 'tests' / 'fixtures' / 'rooms' / 'carcass.json').read_text()),
                           'hall')
        with self.assertRaises(InvalidChange):
            runtime.add_companion('pc', sheet('tamsin'), 'striker', 'balanced')
        with self.assertRaises(InvalidChange):
            runtime.add_companion('tamsin', sheet('tamsin'), 'tank', 'balanced')
        runtime.add_companion('tamsin', sheet('tamsin'), 'striker', 'balanced')
        self.assertEqual(Runtime(db).load()[1]['party']['tamsin']['ledger'], {'slots': {}, 'uses': {}, 'items': {}})


if __name__ == '__main__':
    unittest.main()

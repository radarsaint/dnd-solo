"""Proficiency source verification and the homebrew-style negotiation (Brendon, 2026-10-19).

A sheet's armor, weapon and tool proficiencies are claims; each needs a source (class, species,
background or feat; runtime/kit_gear.py tables). A claim with no source is UNVERIFIED and not
trusted. Kit asks once, in the fiction, where it came from; the player may pitch a backstory, a
trainer or a trade-off; her call (granted, granted with a cost, declined) is a homebrew ruling on
record (state['homebrew_rulings']) for later sessions and the campaign record. Declined, the
rules as written apply. Hand edits to gold, HP, XP and ammo are accepted and only noted.

Synthetic sheets only (tests/fixtures/characters); Nik's sheet is never edited. Dice pinned.
"""
import json
import unittest
from pathlib import Path

from runtime import kit_acts, kit_gear, kit_rooms
from runtime.kit_agent import prepare_turn
from runtime.state_context import InvalidChange, Runtime
from test_kit_gear_answers import Table, answered
from test_kit_review101c import Arena

SHEETS = Path(__file__).resolve().parent / 'fixtures' / 'characters'
SHIELD = 'proficiency:armor:shield'


def sheet(name, **extra):
    out = json.loads((SHEETS / f'{name}.json').read_text())
    out.update(extra)
    return out


class Sources(unittest.TestCase):
    """Every claim against the grant tables, for any build."""

    def test_the_harengon_sage_wizard_shape(self):
        pell = sheet('pell_wizard')
        found = {(c['kind'], c['claim']): c['sources'] for c in kit_gear.verify(pell)}
        self.assertEqual(found[('armor', 'shield')], [], 'nothing grants shield training')
        self.assertEqual(found[('weapons', 'simple')], ['Wizard class'])
        self.assertEqual(found[('tools', "calligrapher's supplies")], ['Sage background'])
        issue, = kit_gear.audit(pell)
        self.assertEqual(issue['issue'], 'unverified_proficiency')
        self.assertEqual(issue['ask'], "Your sheet says shield training. Where's that from?")
        self.assertIn('class, species, background or a feat', issue['rule'])
        self.assertIn('cannot cast spells', issue['rule'])
        self.assertIn('War Caster covers somatic components', issue['rule'])
        self.assertIn('grants no proficiency', issue['rule'])

    def test_war_caster_magic_initiate_and_an_asi_grant_nothing(self):
        pell = sheet('pell_wizard')
        bare = dict(pell, features=['Arcane Recovery'])
        self.assertEqual(kit_gear.sources(pell), kit_gear.sources(bare))
        self.assertNotIn('War Caster covers', kit_gear.audit(bare)[0]['rule'])

    def test_a_real_source_verifies_it(self):
        pell = sheet('pell_wizard')
        for why, changed in (('feat', dict(pell, features=pell['features'] + ['Moderately Armored'])),
                             ('multiclass', dict(pell, **{'class': 'Wizard 4 / Fighter 1'})),
                             ('class', dict(sheet('brannoc_fighter'), armor_proficiencies=['Shields']))):
            with self.subTest(source=why):
                self.assertEqual(kit_gear.audit(changed), [])
                self.assertIn('shield', kit_gear.proficiencies(changed))

    def test_weapons_and_tools_need_a_source_too(self):
        pell = sheet('pell_wizard', armor_proficiencies=[], weapon_proficiencies=['Simple Weapons', 'Martial Weapons'],
                     tool_proficiencies=["Calligrapher's Supplies", "Thieves' Tools"])
        self.assertEqual(sorted(i['id'] for i in kit_gear.audit(pell)),
                         ['proficiency:tools:thieves_tools', 'proficiency:weapons:martial',
                          'shield_proficiency:shield'], 'his shield is sourced by nothing either way')
        dwarf = sheet('brannoc_fighter', weapon_proficiencies=['Battleaxe', 'Warhammer'],
                      tool_proficiencies=["Smith's Tools", 'Dice Set'])
        self.assertEqual(kit_gear.audit(dwarf), [], 'dwarf weapons and tools, soldier gaming set')
        tamsin = sheet('tamsin_bard', magic_items=[], tool_proficiencies=['Lute', 'Disguise Kit'],
                       weapon_proficiencies=['Rapier'])
        self.assertEqual(kit_gear.audit(tamsin), [], 'bard instruments and rapier, entertainer disguise kit')

    def test_an_unknown_build_is_never_guessed_at(self):
        self.assertEqual(kit_gear.audit(sheet('pell_wizard', **{'class': 'Mystery Class'})), [])

    def test_unverified_is_not_trusted(self):
        pell = sheet('pell_wizard')
        self.assertNotIn('shield', kit_gear.proficiencies(pell))
        arena = Arena(self, 'kiln', sheet=pell)
        entry, = kit_gear.gear(arena.state)['clarify']
        self.assertEqual((entry['id'], entry['status']), (SHIELD, 'pending'), 'not trusted: asked about')
        # Ask first, then the rules as written (Brendon): the sheet alone sets no penalty.
        penalties = kit_gear.penalties(arena.state, fight=True)
        self.assertFalse(penalties['no_casting'])
        self.assertFalse(penalties['str_dex_disadvantage'])


class Negotiation(unittest.TestCase):
    """Kit asks once, in the fiction; the player pitches; her call is on record."""

    def raised(self, name='pell_wizard'):
        arena = Arena(self, 'kiln', sheet=sheet(name, hp=60))
        _, body, planning = prepare_turn(arena.runtime, arena.adjudicator, 'I look around the kiln room.')
        ask = planning['gear_clarify']
        self.assertEqual(ask['id'], SHIELD)
        self.assertEqual(ask['ask'], "Your sheet says shield training. Where's that from?")
        kit_gear.check_spoken_clarify(ask, [{'speaker': 'Kit', 'text':
                                             "Your sheet says shield training. Where's that from? Wizards don't "
                                             'usually carry one.'}])
        with self.assertRaises(InvalidChange):
            kit_gear.check_spoken_clarify(ask, [{'speaker': 'Kit', 'text': 'The kiln ticks as it cools.'}])
        self.table = Table(self, None, arena=arena)
        self.table.raise_question()  # Kit asks it at the table (the bridge)
        self.assertEqual([e['status'] for e in kit_gear.gear(arena.state)['clarify']], ['raised'])
        return arena

    def answer(self, arena, line, ruling):
        _, body, planning = prepare_turn(arena.runtime, arena.adjudicator, line)
        self.assertNotIn('gear_clarify', planning, 'asked once')
        self.assertEqual(body['acts']['ruling']['ids'], [SHIELD])
        self.assertIn('ruling', planning['acts'])
        kit_acts.check({'ruling': ruling}, body)
        kit = ('Nice story, but that is not training. Rules as written, then.' if ruling['verdict'] == 'declined'
               else 'Good enough for me, that counts.')
        self.table.turn(line, kit, {'ruling': ruling})
        return arena.state

    def test_granted(self):
        arena = self.raised()
        state = self.answer(arena, '"A shield-maiden in my home warren drilled me for a summer before I left for '
                                   'the academy."', {'id': SHIELD, 'verdict': 'granted',
                                                'source': 'a summer of drill with a warren shield-maiden'})
        ruling, = state['homebrew_rulings']
        self.assertEqual((ruling['claim_id'], ruling['verdict'], ruling['kind'], ruling['subject']),
                         (SHIELD, 'granted', 'proficiency', 'armor'))
        self.assertIn('shield-maiden', ruling['source'])
        self.assertIsNone(ruling['cost'])
        self.assertIn('shield', kit_gear.proficiencies(state['player_sheet'], state['homebrew_rulings']))
        self.assertEqual(kit_gear.penalties(state, fight=True)['gear'], [])
        self.assertIsNone(kit_gear.pending(state))
        self.assertEqual(kit_gear.roll_mode(state, 'dex'), ('normal', ''))

    def test_granted_with_a_cost(self):
        arena = self.raised()
        state = self.answer(arena, '"I\'d trade for it: I gave up a cantrip to train with the city watch."',
                            {'id': SHIELD, 'verdict': 'granted_with_cost', 'source': 'city watch training',
                             'cost': 'Mage Hand is no longer known'})
        ruling, = state['homebrew_rulings']
        self.assertEqual(ruling['verdict'], 'granted_with_cost')
        self.assertEqual(ruling['cost'], 'Mage Hand is no longer known')
        self.assertEqual(kit_gear.penalties(state, fight=True)['gear'], [])

    def test_a_grant_needs_its_source_and_a_cost_needs_the_cost(self):
        arena = self.raised()
        _, body, _ = prepare_turn(arena.runtime, arena.adjudicator, '"Uh, I just have it."')
        for bad in ({'id': SHIELD, 'verdict': 'granted'},
                    {'id': SHIELD, 'verdict': 'granted_with_cost', 'source': 'city watch training'},
                    {'id': 'proficiency:armor:heavy', 'verdict': 'declined'}):
            with self.subTest(ruling=bad), self.assertRaises(InvalidChange):
                kit_acts.check({'ruling': bad}, body)
        self.assertEqual(kit_acts.check({'ruling': {'id': 'none', 'verdict': 'none'}}, body), {},
                         'not answered this turn')

    def test_declined_rules_as_written(self):
        arena = self.raised()
        state = self.answer(arena, '"Uh, I just have it."', {'id': SHIELD, 'verdict': 'declined', 'source': None})
        ruling, = state['homebrew_rulings']
        self.assertEqual(ruling['verdict'], 'declined')
        self.assertIn('cannot cast spells', ruling['rule'])
        # Then (once) whether it is on his arm: stowing it is how he casts again. Until he
        # answers that, nothing is enforced (ask first).
        due = kit_gear.pending(state)
        self.assertEqual((due['issue'], due['item']), ('shield_proficiency', 'shield'))
        self.assertEqual(kit_gear.penalties(state, fight=True)['gear'], [])
        state = answered(self, arena, 'shield', 'held').state
        penalties = kit_gear.penalties(state, fight=True)
        self.assertEqual(penalties['gear'], ['shield'])
        self.assertTrue(penalties['no_casting'])
        self.assertEqual(kit_gear.roll_mode(state, 'dex')[0], 'disadvantage')
        self.assertEqual(kit_gear.roll_mode(state, 'str')[0], 'disadvantage')
        self.assertEqual(kit_gear.roll_mode(state, 'int')[0], 'normal')

    def test_declined_then_drop_and_cast_is_the_swap_only(self):
        arena = self.raised()
        self.answer(arena, '"Uh, I just have it."', {'id': SHIELD, 'verdict': 'declined', 'source': None})
        self.assertIsNotNone(kit_gear.read_swap('I drop my shield and cast Magic Missile at the imp.', arena.state))
        self.assertIsNone(kit_gear.read_swap('I cast Shield.', arena.state))

    def test_the_ruling_persists_into_the_next_session(self):
        arena = self.raised()
        self.answer(arena, '"A shield-maiden drilled me."', {'id': SHIELD, 'verdict': 'granted',
                                                           'source': 'drill with a shield-maiden'})
        arena.runtime.close()
        later = Runtime(arena.path)  # the next session, the same save
        self.addCleanup(later.close)
        # He hand-edits the sheet between sessions: gold, HP, XP, ammo. Accepted, only noted.
        later.set_player_sheet(sheet('pell_wizard', gold_gp=260, hp=28, xp=7200, ammo=20))
        later.rest('long')
        state = later.load()[1]
        self.assertEqual([r['verdict'] for r in state['homebrew_rulings']], ['granted'])
        self.assertEqual([e['status'] for e in kit_gear.gear(state)['clarify']], ['answered'], 'never re-asked')
        self.assertIsNone(kit_gear.pending(state))
        self.assertEqual(kit_gear.penalties(state, fight=True)['gear'], [])
        self.assertEqual({n['field'] for n in state['sheet_notes']}, {'gold_gp', 'hp', 'xp', 'ammo'})
        # It travels with the character from room to room (session state, not the room's).
        for key in ('homebrew_rulings', 'gear', 'sheet_notes'):
            self.assertIn(key, kit_rooms.SESSION_KEYS)

    def test_a_ruling_is_made_once(self):
        arena = self.raised()
        self.answer(arena, '"Uh, I just have it."', {'id': SHIELD, 'verdict': 'declined', 'source': None})
        revision, state = arena.runtime.load()
        with self.assertRaises(InvalidChange):
            arena.runtime.commit('again', revision, [kit_gear.ruling_event(
                state, {'id': SHIELD, 'verdict': 'granted', 'source': 'a second try'})])


class HandEdits(unittest.TestCase):
    """The hand-edit rule is unchanged: numbers are noted; only rules-legality claims are asked."""

    def test_numbers_are_noted_not_asked(self):
        for name in ('brannoc_fighter', 'ilsa_cleric', 'example_pc'):
            with self.subTest(sheet=name):
                arena = Arena(self, 'kiln', sheet=sheet(name))
                arena.runtime.set_player_sheet(sheet(name, gold_gp=9999, hp=99, xp=123))
                state = arena.state
                self.assertEqual(kit_gear.gear(state)['clarify'], [])
                self.assertEqual({n['field'] for n in state['sheet_notes']}, {'gold_gp', 'hp', 'xp'})

    def test_a_proficiency_written_in_by_hand_is_asked_about(self):
        heavy = ['Light', 'Medium', 'Shields', 'Heavy']
        # A Knowledge cleric has no heavy armor training: written in by hand, it is asked about.
        knowledge = {'class': 'Cleric (Knowledge)', 'features': ['Channel Divinity', 'Blessings of Knowledge']}
        arena = Arena(self, 'kiln', sheet=sheet('ilsa_cleric', **knowledge))
        arena.runtime.set_player_sheet(sheet('ilsa_cleric', armor_proficiencies=heavy, **knowledge))
        clarify = kit_gear.gear(arena.state)['clarify']
        self.assertEqual([c['id'] for c in clarify], ['proficiency:armor:heavy'], 'unsourced for this build')
        # Ilsa is a Life cleric: the domain grants heavy armor (SRD 5.1), so the same edit is sourced.
        arena = Arena(self, 'kiln', sheet=sheet('ilsa_cleric'))
        arena.runtime.set_player_sheet(sheet('ilsa_cleric', armor_proficiencies=heavy))
        self.assertEqual(kit_gear.gear(arena.state)['clarify'], [], 'Life Domain: heavy armor')


if __name__ == '__main__':
    unittest.main()

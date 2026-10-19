"""Nagatha's review of kit-slot-ask-gear-audit at 59ce12a (no-go), item by item. Every test plays
the sheet as it is (tests/fixtures/characters, synthetic or Nik's stats-only sheet, never
edited), with every die pinned, through the real paths: KitChatBridge prepare/complete for the
questions Kit raises and the answers she reads, and the adjudicator's resolve-then-commit for
acts in a fight. Nothing here saves an event directly.

1  The equipment question, the ruling on the pitch and the gear answer commit through the
   bridge (they were missing from the commit allowlists: 'Pending Kit event changed').
2  While Kit's question is open, the reply is the answer, quoted or not; never the physical-act
   refusal.
3  Ask first, then the rules as written (Brendon): no untrained-gear penalty from the sheet
   alone, before the player has answered; the question is due at session start.
4  A yes to the slot ask reads the dice in the answer; lower-level damage from the first message
   is never applied at the upcast level.
6  The must-ask check is style: one retry, then the engine carries the question.
7  Subclass and 2024 class-option grants count as sources.
8  Spells the engine does not model still go through the slot ask; a Shield reaction with no
   1st-level slot asks for the upcast.
9/10  A new act given as the slot-ask answer; spell-name capitals; drop-and-cast out of a fight.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

from runtime import kit_combat, kit_gear
from runtime.kit_agent import KitChatBridge, PendingRuling, PerformanceRejected, prepare_turn, window_view
from test_kit_review101c import Arena

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import watchroom_replay as wr  # noqa: E402

SHEETS = ROOT / 'tests' / 'fixtures' / 'characters'
SHIELD = 'proficiency:armor:shield'
TABLES = itertools.count(1)
NARRATION = ('The kiln ticks as it cools. Soot coats the vaulted brick above. A cracked bellows leans on the wall. '
             'Shards of fired clay crunch underfoot. Heat still breathes from the mouth of the oven. A shelf of pots '
             'sits half finished. Ash lies thick along the floor. A draft stirs it into small grey spirals.')
NARRATIONS = (NARRATION,
              'Embers wink in the grate and go dark one by one. The floor gives back the day\'s heat through your '
              'boots. A crack runs up the far wall like a frozen bolt of lightning. Something small skitters '
              'behind the stacked pots. The smell of scorched clay hangs on everything. Light comes in thin and '
              'orange from the vent above. A potter\'s wheel stands still, its treadle worn bright. Dust hangs in '
              'the slant of light.',
              'The oven mouth glows a dull red, patient as a held breath. Old soot streaks the brick in long black '
              'tongues. A bucket of grey slip has dried to a crust. Two clay jars lean together like gossips. The '
              'air tastes of iron and smoke. Somewhere water drips onto hot stone and hisses. Footprints in the ash '
              'lead nowhere useful. The quiet presses in.',
              'A chimney draws the last warm air upward with a low moan. Broken tiles lie fanned across the floor. '
              'Tongs hang from a nail, black with use. A row of unfired bowls waits on a plank. The walls sweat a '
              'little in the heat. A shutter knocks once against its frame and stops. The light flickers on the '
              'glaze of a lone cup. Everything here is half made.')
MM = 'Initiative 25. I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force'


def sheet(name, **extra):
    out = json.loads((SHEETS / f'{name}.json').read_text())
    out.update(extra)
    return out


def used(arena):
    return {level: slot['used'] for level, slot in arena.state['pc_resources']['slots'].items()}


class Table:
    """A kiln session driven through KitChatBridge, Kit's lines scripted, every die pinned."""

    def __init__(self, test, name, roll=lambda: 2, hp=60, arena=None, **extra):
        self.arena = arena or Arena(test, 'kiln', sheet=sheet(name, hp=hp, **extra), roll=roll)
        self.bridge = KitChatBridge(self.arena.runtime, self.arena.adjudicator)
        self.count = 0
        self.prefix = f't{next(TABLES)}-'
        self.arena.table = self  # one table per session: its lines never repeat

    def prepare(self, line):
        self.count += 1
        turn = f'{self.prefix}{self.count}'
        return turn, self.bridge.prepare(line, turn, one_pass=True)

    def output(self, packet, line, kit, acts=None):
        narration = NARRATIONS[(self.count - 1) % len(NARRATIONS)]
        decision = wr.kit_decision(packet, {'speech': [('Narrator', narration), ('Kit', kit)]})
        decision.update(acts or {})
        return {'decision': decision, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': narration},
            {'speaker': 'Kit', 'text': kit, 'reacts_to': ' '.join(line.split()[:4])}]}}

    def turn(self, line, kit, acts=None):
        turn, packet = self.prepare(line)
        return packet, self.bridge.complete(turn, self.output(packet, line, kit, acts))

    def raise_question(self, line='I look around the kiln room.'):
        """Kit raises the due question in her own words (its ask, said her way)."""
        turn, packet = self.prepare(line)
        due = packet['input']['private']['gear_clarify']
        kit = f"{due['ask']} The rules say so: {due['rule'].split(':', 1)[-1].strip()[:200]}"
        self.bridge.complete(turn, self.output(packet, line, kit))
        return due

    @property
    def state(self):
        return self.arena.state


def answered(test, arena, item, state):
    """The player answers Kit's equipment question at the table (bridge, scripted Kit): the item is
    held or stowed. Kit raises the due question, he answers, she records it."""
    table = getattr(arena, 'table', None) or Table(test, None, arena=arena)
    table.raise_question()
    test.assertIn(item, [e['item'] for e in kit_gear.raised(arena.state)], 'his item is the one asked about')
    table.turn('I keep it on.' if state == 'held' else 'I put it away.', 'Noted, then.',
               {'gear': {'item': item, 'state': state}})
    test.assertIs(kit_gear.gear(arena.state)['in_use'][item], state == 'held')
    test.assertFalse(kit_gear.open_question(arena.state, item))
    return arena


class BridgeCommits(unittest.TestCase):
    """1 (blocker): through the bridge, raising, ruling on and answering the question commit."""

    def test_raising_the_source_question_commits_once(self):
        table = Table(self, 'pell_wizard')
        due = table.raise_question()
        self.assertEqual(due['id'], SHIELD)
        self.assertEqual([(e['id'], e['status']) for e in kit_gear.gear(table.state)['clarify']], [(SHIELD, 'raised')])
        _, packet = table.prepare('I look at the bellows.')
        self.assertNotIn('gear_clarify', packet['input']['private'], 'asked once, never again')

    def test_each_verdict_commits_through_the_bridge(self):
        for verdict, extra in (('granted', {'source': 'a summer of drill with a warren shield-maiden'}),
                               ('granted_with_cost', {'source': 'city watch drill', 'cost': 'only this one shield'}),
                               ('declined', {'source': None})):
            with self.subTest(verdict=verdict):
                table = Table(self, 'pell_wizard')
                table.raise_question()
                table.turn('"A shield-maiden drilled me."', 'Good enough for me, that counts.' if verdict != 'declined'
                           else 'Nice story, but drill is not training. Rules as written, then.',
                           {'ruling': {'id': SHIELD, 'verdict': verdict, **extra}})
                ruling, = table.state['homebrew_rulings']
                self.assertEqual(ruling['verdict'], verdict)
                entry = next(e for e in kit_gear.gear(table.state)['clarify'] if e['id'] == SHIELD)
                self.assertEqual(entry['status'], 'answered')

    def test_the_gear_answer_commits_held_or_stowed(self):
        for state, in_use in (('held', True), ('stowed', False)):
            with self.subTest(state=state):
                table = Table(self, 'nik')
                due = table.raise_question()
                self.assertEqual(due['item'], 'Sentinel Shield')
                table.turn('I keep it on my arm.' if in_use else 'I put it away.', 'Noted.',
                           {'gear': {'item': 'sentinel_shield', 'state': state}})
                self.assertIs(kit_gear.gear(table.state)['in_use']['sentinel_shield'], in_use)
                self.assertEqual([e['status'] for e in kit_gear.gear(table.state)['clarify']], ['answered'])
                _, packet = table.prepare('I look at the bellows.')
                self.assertNotIn('gear_clarify', packet['input']['private'])


class AnswerRouting(unittest.TestCase):
    """2: the reply to Kit's open question is the answer, quoted or not."""

    LINES = ('A shield-maiden drilled me.', '"A shield-maiden drilled me."', 'My uncle taught me to block with it.',
             'I trained with the city watch for a year.', 'I just have it.')

    def test_unquoted_answers_reach_kit_with_the_ruling_offered(self):
        for line in self.LINES:
            with self.subTest(line=line):
                table = Table(self, 'pell_wizard')
                table.raise_question()
                try:
                    _, body, planning = prepare_turn(table.arena.runtime, table.arena.adjudicator, line)
                except PendingRuling as exc:
                    self.fail(f'{line!r} was refused: {exc}')
                self.assertEqual(body['acts']['ruling']['ids'], [SHIELD])
                self.assertNotIn('physical action', body['public_event'])

    def test_an_unquoted_answer_is_ruled_on_through_the_bridge(self):
        table = Table(self, 'pell_wizard')
        table.raise_question()
        table.turn('My uncle taught me to block with it.', 'Your uncle, then. I will allow it.',
                   {'ruling': {'id': SHIELD, 'verdict': 'granted', 'source': 'his uncle taught him'}})
        self.assertEqual(table.state['homebrew_rulings'][0]['source'], 'his uncle taught him')

    def test_the_gear_question_answer_is_not_refused_either(self):
        table = Table(self, 'nik')
        table.raise_question()
        for line in ('On my arm, where it always is.', 'Stowed.'):
            with self.subTest(line=line):
                _, body, _ = prepare_turn(table.arena.runtime, table.arena.adjudicator, line)
                self.assertEqual(body['acts']['gear']['items'], ['sentinel_shield'])


class AskFirst(unittest.TestCase):
    """3: Brendon's ruling: ask first, then the rules as written."""

    def test_the_question_is_due_at_session_start(self):
        table = Table(self, 'nik')
        packet = table.bridge.prepare(opening=True, one_pass=True)
        self.assertEqual(packet['input']['private']['gear_clarify']['id'], 'shield_proficiency:sentinel_shield')

    def test_no_penalty_before_he_is_asked_even_if_the_fight_starts_first(self):
        table = Table(self, 'nik')
        self.assertEqual(kit_gear.penalties(table.state, fight=True)['gear'], [])
        result = table.arena.act(MM)
        self.assertNotIn('cannot cast', result.public_event)
        self.assertEqual(table.arena.fight['hp']['imp'], 18 - 12)
        self.assertEqual(used(table.arena)['1'], 1)

    def test_a_shield_reaction_is_offered_before_he_is_asked(self):
        table = Table(self, 'nik', roll=lambda: 10)  # the imp's spit is a 15 against AC 14: a hit
        table.arena.act('Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertEqual(table.arena.fight['awaiting']['options'], ['shield'])

    def test_the_question_comes_due_on_the_turn_the_fight_starts(self):
        table = Table(self, 'nik')
        _, packet = table.prepare(MM)
        self.assertEqual(packet['input']['private']['gear_clarify']['id'], 'shield_proficiency:sentinel_shield')

    def test_once_he_says_it_is_on_his_arm_the_rules_apply(self):
        table = Table(self, 'nik')
        table.raise_question()
        table.turn('It stays on my arm.', 'Then it stays.', {'gear': {'item': 'sentinel_shield', 'state': 'held'}})
        result = table.arena.act(MM)
        self.assertIn('cannot cast', result.public_event)
        self.assertEqual(used(table.arena)['1'], 0)

    def test_an_unruled_claim_does_not_bite_either(self):
        table = Table(self, 'pell_wizard')
        table.raise_question()
        self.assertEqual(kit_gear.penalties(table.state, fight=True)['gear'], [], 'raised, not yet ruled on')
        table.turn('"Uh, I just have it."', 'Rules as written, then: no training.',
                   {'ruling': {'id': SHIELD, 'verdict': 'declined', 'source': None}})
        self.assertEqual(kit_gear.penalties(table.state, fight=True)['gear'], [],
                         'declined: the shield question is asked before the rules bite')
        due = table.raise_question('I look at the shelf of pots.')
        self.assertEqual(due['item'], 'shield')
        table.turn('I keep it up.', 'Your call.', {'gear': {'item': 'shield', 'state': 'held'}})
        self.assertEqual(kit_gear.penalties(table.state, fight=True)['gear'], ['shield'])


class YesReadsTheAnswer(unittest.TestCase):
    """4: a yes to the slot ask with the upcast roll in it applies that roll."""

    def setUp(self):
        self.table = Table(self, 'nik', roll=lambda: 2)
        arena = self.table.arena
        arena.act('I put my shield away.')
        # Four 1st-level casts in play spend every 1st-level slot (the imp has 18 hit points and
        # every foe misses on a 2): 1 damage each, so it stands.
        arena.act('Initiative 25. I cast Magic Missile at the kobold slinger (!cast magic missile) '
                  '3d4 (1, 1, 1) + 3 = 1 force')
        self.assertEqual(used(arena)['1'], 1)
        for _ in range(3):
            arena.act('I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (1, 1, 1) + 3 = 1 force')
        self.assertEqual(used(arena)['1'], 4)
        self.hp = arena.fight['hp']['imp']

    def test_the_answers_dice_are_applied(self):
        arena = self.table.arena
        arena.act('I cast Magic Missile at the ember imp (!cast magic missile)')
        self.assertEqual(arena.fight['awaiting']['kind'], 'slot_ask')
        arena.act('Yes. !cast magic missile -l 2: 4d4 (3, 2, 4, 1) + 4 = 14 force', upcast='yes')
        self.assertEqual(arena.fight['hp']['imp'], self.hp - 14)
        self.assertEqual(used(arena)['2'], 1)
        self.assertFalse(arena.fight.get('pending'))

    def test_lower_level_damage_is_not_applied_at_the_upcast_level(self):
        arena = self.table.arena
        arena.act('I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force')
        result = arena.act('Yes, second level.', upcast='yes')
        self.assertEqual(arena.fight['hp']['imp'], self.hp, 'the 1st-level roll is not the 2nd-level spell')
        self.assertIn('2nd level', result.public_event)
        self.assertIn('!cast magic missile -l 2', result.public_event)
        self.assertEqual(arena.fight['pending']['needs'], 'damage')
        arena.act('Magic Missile: 4d4 (3, 2, 4, 1) + 4 = 14 force')
        self.assertEqual(arena.fight['hp']['imp'], self.hp - 14)
        self.assertEqual(used(arena)['2'], 1, 'one slot, spent once')


class StyleOnly(unittest.TestCase):
    """6: a turn that forgets the question gets one retry, then commits with the question carried."""

    def test_one_retry_then_the_engine_carries_it(self):
        table = Table(self, 'nik')
        line = 'I look around the kiln room.'
        turn, packet = table.prepare(line)
        output = table.output(packet, line, 'Quiet in here. I like it.')
        with self.assertRaises(PerformanceRejected) as caught:
            table.bridge.complete(turn, output)
        self.assertIn('gear_clarify', str(caught.exception))
        result = table.bridge.complete(turn, output)
        self.assertIn('Sentinel Shield', result['spoken'])
        self.assertEqual(kit_gear.gear(table.state)['clarify'][0]['status'], 'raised')


class SubclassGrants(unittest.TestCase):
    """7: subclass (SRD 5.1 and the 2014 books) and 2024 class options are sources."""

    def claims(self, klass, armor=(), weapons=(), features=()):
        base = sheet('brannoc_fighter', **{'class': klass, 'armor_proficiencies': list(armor),
                                           'weapon_proficiencies': list(weapons)})
        base['features'] = list(base.get('features') or []) + list(features)
        return {(c['kind'], c['claim']): bool(c['sources']) for c in kit_gear.verify(base)}

    def test_sourced(self):
        for klass, armor, weapons, features in (
                ('Cleric (Life)', ['Heavy'], [], []), ('Cleric (Life Domain)', ['Heavy Armor'], [], []),
                ('Cleric (War)', ['Heavy'], ['Martial Weapons'], []), ('Cleric (Tempest)', ['Heavy'], ['Martial'], []),
                ('Cleric', ['Heavy'], ['Martial'], ['Divine Order: Protector']),
                ('Bard (Valor)', ['Medium', 'Shields'], ['Martial'], []),
                ('Bard (College of Swords)', ['Medium'], ['Scimitar'], []),
                ('Warlock (Hexblade)', ['Medium', 'Shields'], ['Martial'], []),
                ('Wizard (Bladesinging)', ['Light'], ['Rapier'], []),
                ('Druid', ['Medium'], ['Martial'], ['Primal Order: Warden']),
                ('Wizard 1 / Cleric (Life) 3', ['Heavy'], [], [])):
            with self.subTest(klass=klass, features=features):
                found = self.claims(klass, armor, weapons, features)
                self.assertTrue(found and all(found.values()), found)

    def test_still_unsourced(self):
        for klass, armor, weapons in (('Cleric (Knowledge)', ['Heavy'], []), ('Bard (Lore)', ['Shields'], []),
                                      ('Warlock (Fiend)', ['Shields'], []), ('Wizard (Bladesinging)', ['Medium'], []),
                                      ('Bard (Swords)', ['Shields'], ['Greatsword'])):
            with self.subTest(klass=klass):
                found = self.claims(klass, armor, weapons)
                self.assertFalse(all(found.values()), found)


class UnmodelledSpells(unittest.TestCase):
    """8: a leveled spell the fight does not model still pays its slot, and asks before an upcast."""

    def test_color_spray_and_slow_take_their_slot_or_ask(self):
        for spell, level in (('Color Spray', 1), ('Slow', 3)):
            with self.subTest(spell=spell):
                table = Table(self, 'nik')
                arena = table.arena
                result = arena.act(f'Initiative 25. I cast {spell} at the ember imp (!cast {spell.casefold()})')
                self.assertEqual(used(arena)[str(level)], 1, result.public_event)
                self.assertIn(spell, result.public_event)

    def test_color_spray_with_no_first_level_slot_asks(self):
        table = Table(self, 'nik')
        arena = table.arena
        arena.act('Initiative 25. I cast Color Spray at the ember imp (!cast color spray)')
        for _ in range(3):
            arena.act('I cast Color Spray at the ember imp (!cast color spray)')
        self.assertEqual(used(arena)['1'], 4)
        result = arena.act('I cast Color Spray at the ember imp (!cast color spray)')
        self.assertEqual(arena.fight['awaiting']['kind'], 'slot_ask', result.public_event)
        self.assertIn('2nd level', result.public_event)
        self.assertEqual(used(arena)['2'], 0)

    def test_a_shield_reaction_with_no_first_level_slot_asks_for_the_upcast(self):
        table = Table(self, 'nik', roll=lambda: 10, hp=200)
        arena = table.arena
        arena.act('Initiative 25. I cast Color Spray at the ember imp (!cast color spray)')
        arena.act('Not now.', react='decline')
        for _ in range(3):
            arena.act('I cast Color Spray at the ember imp (!cast color spray)')
            if arena.fight.get('awaiting'):
                arena.act('Not now.', react='decline')
        self.assertEqual(used(arena)['1'], 4)
        arena.act('I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        waiting = arena.fight['awaiting']
        self.assertEqual(waiting['options'], ['shield'])
        view = window_view(arena.runtime.source(), arena.state, waiting)
        self.assertEqual(view['options'][0]['avrae'], '!cast shield -l 2')
        self.assertIn('2nd', view['options'][0]['note'])
        held = arena.held('Shield! !cast shield', react='shield', cast_in_avrae=True)
        self.assertIn('2nd level', str(held))
        self.assertEqual(used(arena)['2'], 0, 'nothing taken silently')
        arena.act('Shield at 2nd. !cast shield -l 2', react='shield', cast_in_avrae=True, slot_level=2)
        self.assertEqual(used(arena)['2'], 1)


class RoughEdges(unittest.TestCase):
    """9 and 10."""

    def slot_asked(self, spell='Magic Missile'):
        table = Table(self, 'nik')
        arena = table.arena
        arena.act('Initiative 25. I cast Color Spray at the ember imp (!cast color spray)')
        for _ in range(3):
            arena.act('I cast Color Spray at the ember imp (!cast color spray)')
        arena.act(f'I cast {spell} at the ember imp (!cast {spell.casefold()})')
        self.assertEqual(arena.fight['awaiting']['kind'], 'slot_ask')
        return arena

    def test_a_new_act_as_the_answer_is_that_act(self):
        arena = self.slot_asked()
        hp = arena.fight['hp']['imp']
        result = arena.act('Nah, I Fire Bolt it instead. To Hit: 1d20 (18) + 7 = 25 Damage: 2d10 (5, 5) = 10 fire',
                           upcast='new_action')
        self.assertEqual(arena.fight['hp']['imp'], hp - 10, result.public_event)
        self.assertIsNone(arena.fight.get('awaiting'))
        self.assertEqual(used(arena)['2'], 0)

    def test_a_no_that_carries_the_roll_for_another_act_is_that_act(self):
        for read in ('no', 'new_action'):
            with self.subTest(upcast=read):
                arena = self.slot_asked()
                hp = arena.fight['hp']['imp']
                arena.act('Nah, I Fire Bolt it instead. To Hit: 1d20 (18) + 7 = 25 Damage: 2d10 (5, 5) = 10 fire',
                          upcast=read)
                self.assertEqual(arena.fight['hp']['imp'], hp - 10)
                self.assertEqual(used(arena)['2'], 0)
        arena = self.slot_asked()
        result = arena.act('No, never mind.', upcast='no')
        self.assertIn('Nothing is cast', result.public_event, 'a plain no is still a no')

    def test_spell_names_keep_their_apostrophes_lower(self):
        table = Table(self, 'nik')
        arena = table.arena
        arena.act('Initiative 25. I cast Magic Missile at the kobold slinger (!cast magic missile -l 2) '
                  '4d4 (1, 1, 1, 1) + 4 = 1 force')
        for _ in range(2):
            arena.act('I cast Magic Missile at the ember imp (!cast magic missile -l 2) 4d4 (1, 1, 1, 1) + 4 = 1 force')
        self.assertEqual(used(arena)['2'], 3)
        result = arena.act("I cast Dragon's Breath on myself (!cast dragon's breath)")
        self.assertEqual(arena.fight['awaiting']['kind'], 'slot_ask')
        self.assertIn("Dragon's Breath", result.public_event)
        self.assertNotIn("Dragon'S", result.public_event)
        view = window_view(arena.runtime.source(), arena.state, arena.fight['awaiting'])
        self.assertEqual(view['spell'], "Dragon's Breath")

    def test_drop_and_cast_out_of_a_fight_does_not_lose_the_cast(self):
        table = Table(self, 'nik')
        result = table.arena.act('I drop my shield and cast Magic Missile at the ember imp '
                                 '(!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force')
        self.assertFalse(kit_gear.gear(table.state)['in_use']['sentinel_shield'])
        self.assertIn('Magic Missile', result.public_event)
        self.assertEqual(table.arena.fight['hp']['imp'], 18 - 12)


if __name__ == '__main__':
    unittest.main()

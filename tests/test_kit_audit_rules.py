"""Teaching-audit fixes as general rules (research audit 07): any room, any PC.

Each test names the rule it pins. Synthetic actors and sheets show nothing is keyed to
area 6c's dealer or to Nik."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_cards, kit_claims, pc_sheet
from runtime.kit_agent import PendingRuling, Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel

SOURCE = json.loads(FIXTURE.read_text())
NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())


def sheet(name='Testa', wis=10, skills=None, **extra):
    """A generic sheet: no class or character is special."""
    return {'schema': 'character_sheet_v1', 'name': name, 'ancestry': 'Human', 'class': 'Rogue',
            'level': 2, 'proficiency_bonus': 2,
            'abilities': {'str': 10, 'dex': 14, 'con': 12, 'int': 10, 'wis': wis, 'cha': 10},
            'skills': skills or {}, **extra}


def no_roll():
    raise AssertionError('rolled although the passive already met the number')


class Case(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(lambda: self.runtime.close())
        self.source = copy.deepcopy(SOURCE)

    def start(self, pc=None, source=None):
        if source is not None:
            self.source = source
        self.runtime.initialize(copy.deepcopy(self.source), 'area_06c')
        if pc:
            self.runtime.set_player_sheet(pc)
        return self.runtime.load()


class InsightRoutesByTargetTests(Case):
    """Rule 1: a lie read uses the lie rule and never prints an unrelated secret."""

    ACTION = 'I use Insight to tell if the dealer is lying about the toll.'

    def test_lie_read_never_reveals_the_disguise(self):
        for pc in (NIK, sheet(wis=8)):
            with self.subTest(pc=pc['name']):
                self.runtime = Runtime(Path(tempfile.mkdtemp()) / 'kit.sqlite')
                revision, state = self.start(pc)
                result = Room6CAdjudicator(source=self.source, roll=lambda: 20).resolve(self.ACTION, revision, state)
                self.assertEqual(result.kind, 'lie_read')
                self.assertNotRegex(result.public_event.lower(), r'vampire|fang|pallor|posing|marked|key')
                self.assertNotIn('reveal_fact', [e['type'] for e in result.events])
                self.assertNotIn('claim_learned', [e['type'] for e in result.events])
                self.runtime.close()

    def test_passive_insight_meeting_flat_deception_reads_without_a_roll(self):
        # Dealer: flat 10 + Deception 4 = 14. Nik's passive Insight 14 meets it.
        revision, state = self.start(NIK)
        state['claims'] = {'said': [{'claim': 'passage_toll', 'by': 'uktarl', 'stance': 'lie', 'version': 'Twenty.'}]}
        result = Room6CAdjudicator(source=self.source, roll=no_roll).resolve(self.ACTION, revision, state)
        self.assertIn('lying', result.public_event)
        self.assertIn('passive Insight 14 meets DC 14', result.public_event)

    def test_an_active_read_rolls_against_the_same_flat_number(self):
        revision, state = self.start(sheet(wis=10, skills={'insight': 2}))   # passive 12 < 14
        state['claims'] = {'said': [{'claim': 'x', 'by': 'uktarl', 'stance': 'truth', 'version': 'Ten.'}]}
        hit = Room6CAdjudicator(source=self.source, roll=lambda: 12).resolve(self.ACTION, revision, state)
        self.assertIn('means it', hit.public_event)
        self.assertIn('(Insight 14 vs DC 14)', hit.public_event)   # 12 + 2 meets 14: a tie succeeds
        miss = Room6CAdjudicator(source=self.source, roll=lambda: 3).resolve(self.ACTION, revision, state)
        self.assertIn('nothing to read', miss.public_event)
        self.assertNotIn('DC', miss.public_event)

    def test_any_actor_in_any_room_shape_can_be_read(self):
        source = copy.deepcopy(SOURCE)
        source['actors']['innkeeper'] = {'name': 'Innkeeper', 'speaker': 'Innkeeper', 'location': 'area_06c',
                                         'status': 'alive', 'visible': True, 'motive': 'Sell rooms.',
                                         'stats': {'abilities': {'str': 10, 'dex': 10, 'con': 10, 'int': 10,
                                                                 'wis': 10, 'cha': 12},
                                                   'skills': {'deception': 1}}}
        revision, state = self.start(sheet(wis=10), source)   # passive Insight 10 < 11
        result = Room6CAdjudicator(source=source, roll=lambda: 1).resolve(
            'Is the innkeeper lying? I watch her face.', revision, state)
        self.assertEqual(result.kind, 'lie_read')
        self.assertIn('innkeeper', result.public_event)
        self.assertIn('innkeeper', result.events[0]['evidence'])

    def test_a_disguise_read_targets_only_the_disguise_claim(self):
        revision, state = self.start(sheet(wis=10, skills={'insight': 0}))
        result = Room6CAdjudicator(source=self.source, roll=lambda: 20).resolve(
            'I use Insight on their fangs: are they really vampires?', revision, state)
        self.assertEqual(result.kind, 'check')
        self.assertIn('posing as vampires', result.public_event)
        self.assertEqual({e.get('claim') or e.get('fact') for e in result.events if e['type'] != 'beat'},
                         {'false_vampires'})

    def test_an_insight_read_with_no_target_asks_what_they_read(self):
        # Rare: several people here and nobody has spoken to the PC, so nothing settles it.
        revision, state = self.start(NIK)
        with self.assertRaisesRegex(PendingRuling, 'What are you reading'):
            Room6CAdjudicator(source=self.source).resolve('I make an Insight check.', revision, state)

    def test_a_bare_insight_reads_whoever_just_spoke_without_asking(self):
        # The situation settles it: whoever last spoke to the PC is the one being read.
        revision, state = self.start(NIK)
        speaker = next(key for key, actor in state['actors'].items()
                       if actor.get('location') == state['area'] and actor.get('status') not in ('fled', 'dead'))
        state = {**state, 'claims': {'said': [{'by': speaker, 'stance': 'truth'}], 'learned': []}}
        result = Room6CAdjudicator(source=self.source, roll=lambda: 20).resolve(
            'I make an Insight check.', revision, state)
        self.assertEqual(result.kind, 'lie_read')
        self.assertIn(speaker, result.events[0]['evidence'])


class PassiveAutoSucceedsTests(Case):
    """Rule 2: a passive that meets the DC is automatic; a roll only when it isn't."""

    def test_passive_perception_finds_the_key_without_a_roll(self):
        revision, state = self.start(NIK)   # passive Perception 14 vs DC 13
        result = Room6CAdjudicator(source=self.source, roll=no_roll).resolve('I inspect the fresco.', revision, state)
        self.assertIn('stone key', result.public_event)
        self.assertIn('passive Perception 14 meets DC 13', result.public_event)
        self.assertIn('fresco_key', [e.get('fact') for e in result.events])

    def test_a_lower_passive_rolls_and_a_tie_succeeds(self):
        pc = sheet(wis=10, skills={'perception': 1})   # passive 11 < 13
        revision, state = self.start(pc)
        tie = Room6CAdjudicator(source=self.source, roll=lambda: 12).resolve('I inspect the fresco.', revision, state)
        self.assertIn('(Perception 13 vs DC 13)', tie.public_event)
        miss = Room6CAdjudicator(source=self.source, roll=lambda: 11).resolve('I inspect the fresco.', revision, state)
        self.assertEqual(miss.public_event, 'You find nothing you can be sure of. (Perception 12)')

    def test_pc_check_helper_is_the_one_rule(self):
        self.assertTrue(kit_claims.pc_check(13, 0, 13, no_roll)['auto'])
        self.assertTrue(kit_claims.pc_check(13, 3, None, lambda: 10)['success'])
        self.assertFalse(kit_claims.pc_check(13, 3, 12, lambda: 9)['success'])


class CardEngineFlatNumbersTests(unittest.TestCase):
    """Rule 3: NPCs bring flat 10 + skill at the card table; ties go to the PC; one
    number per secret."""

    config = SOURCE['procedures']['three_dragon_ante']

    def seated_cheat(self, passives=None, mods=None, dcs=None):
        mods = mods or {'perception': 0, 'insight': 0, 'sleight_of_hand': 0}
        for number in range(300):
            table = kit_cards.CardTable('three_dragon_ante', self.config, dict(mods), f's{number}',
                                        passives=passives, dcs=dcs)
            state = table.resolve('card_join', 'I buy in with 30 gold.', 1, kit_cards.initial_state(self.config))[1]
            probe = table.resolve('card_join', 'Deal me in.', 2, state)[1]
            if probe['private']['cheated']:
                return table, state
        self.fail('no cheating seed')

    def test_watching_meets_a_fixed_dc_and_never_an_npc_roll(self):
        table, state = self.seated_cheat()
        self.assertEqual(table.dcs['watch'], 13)
        text, _, reveals = table.resolve('card_watch', 'I watch the deal. I rolled 13 + 0 = 13.', 2, state)
        self.assertEqual(reveals, ['marked_deck'])           # 13 meets 13
        self.assertIn('(Perception 13 vs DC 13)', text)

    def test_a_passive_that_meets_the_watch_dc_catches_it_without_a_roll(self):
        table, state = self.seated_cheat(passives={'perception': 13})
        text, _, reveals = table.resolve('card_watch', 'I watch the deal.', 2, state)
        self.assertEqual(reveals, ['marked_deck'])
        self.assertIn('passive Perception 13', text)

    def test_reading_him_is_flat_ten_plus_deception_and_a_miss_is_neutral(self):
        table, state = self.seated_cheat()
        state = table.resolve('card_watch', 'I watch the deal. I rolled 1 + 0 = 1.', 2, state)[1]
        state = table.resolve('card_ante', 'I ante my strongest card.', 3, state)[1]
        self.assertEqual(table.dcs['read'], 14)
        text = table.resolve('card_read', 'I read him for a bluff. I rolled 5 + 0 = 5.', 4, state)[0]
        self.assertTrue(text.startswith('He gives you nothing to read.'))
        self.assertNotIn('performance', text)
        self.assertNotIn('DC', text)

    def test_the_watch_dc_is_the_marked_deck_claims_dc(self):
        runtime = Runtime(Path(tempfile.mkdtemp()) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')
        state = runtime.load()[1]
        adjudicator = Room6CAdjudicator(source=SOURCE)
        claim_dc = kit_claims.claims_here(SOURCE, state, None)['claims']['marked_deck']['dc']
        self.assertEqual(adjudicator._card_dcs(self.config, state), {'watch': claim_dc})
        self.assertEqual(claim_dc, 10 + SOURCE['actors']['uktarl']['stats']['skills']['sleight_of_hand'])


class NoLeakyRefusalsTests(Case):
    """Rule 4: defaults instead of refusals; Stealth vs passive Perception; spells aren't combat."""

    def test_inspecting_the_deck_is_a_check_not_a_refusal(self):
        revision, state = self.start(sheet(wis=10))
        result = Room6CAdjudicator(source=self.source, roll=lambda: 2).resolve('I inspect the deck.', revision, state)
        self.assertEqual(result.kind, 'check')
        self.assertNotRegex(result.public_event, r'(?i)no (discovery )?dc|source gives')

    def test_no_player_facing_string_says_the_source_gives_no_dc(self):
        for path in ('runtime/kit_agent.py', 'runtime/kit_cards.py'):
            text = (Path(__file__).parent.parent / path).read_text()
            for raised in re.findall(r"(?:PendingRuling|NeedsRuling)\((.{0,300})", text):
                self.assertNotRegex(raised, r'(?i)gives\s+no\b.{0,20}DC|no discovery DC', path)

    def test_stealth_rolls_against_the_best_passive_perception(self):
        revision, state = self.start(sheet(wis=10, skills={'stealth': 4}))
        best = max(kit_claims.npc_passive(a, 'perception') for a in state['actors'].values())
        adjudicator = Room6CAdjudicator(source=self.source, roll=lambda: best - 4)
        result = adjudicator.resolve('I sneak out the south door.', revision, state)
        self.assertEqual(result.kind, 'stealth')
        self.assertIn(f'passive Perception {best}', result.public_event)
        self.assertEqual(result.events[0]['type'], 'move')
        caught = Room6CAdjudicator(source=self.source, roll=lambda: 1).resolve('I sneak out the south door.',
                                                                              revision, state)
        self.assertNotIn('move', [e['type'] for e in caught.events])

    def test_detect_magic_is_not_combat(self):
        self.assertEqual(kit_agent.room_intent('I cast Detect Magic.'), 'spell')
        self.assertEqual(kit_agent.room_intent('I cast Fire Bolt at the dealer.'), 'combat')
        revision, state = self.start(NIK)
        with self.assertRaises(PendingRuling) as caught:
            Room6CAdjudicator(source=self.source).resolve('I cast Detect Magic.', revision, state)
        self.assertNotIn('Combat', str(caught.exception))
        self.assertNotIn('Fights', str(caught.exception))

    def test_the_ring_uses_the_default_dc_without_a_source_dc(self):
        ring = SOURCE['claims']['ring_value']
        self.assertNotIn('dc', ring)
        self.assertEqual(kit_claims.claim_dc(ring, SOURCE['actors'], 1), 10)


class GeneralNotSixCTests(Case):
    """Rule 6: no dealer, ring, or Nik baked into general code or teaching."""

    def test_focus_actor_accepts_any_present_actor_id(self):
        self.assertNotIn('enum', kit_agent.PLAN_SCHEMA['properties']['focus_actor'])
        self.assertNotIn('enum', kit_agent.SPEECH_SCHEMA['properties']['segments']['items']['properties']['speaker'])
        speakers = kit_agent.actor_speakers(SOURCE)
        for actor in SOURCE['actors']:
            plan = {'focus_actor': actor, 'improv_read': {'actor_ref': actor}}
            self.assertEqual(kit_agent.focus_speaker(plan, speakers), speakers[actor])

    def test_an_absent_focus_actor_is_rejected(self):
        self.start(NIK)
        bridge = kit_agent.KitChatBridge(self.runtime, Room6CAdjudicator(source=self.source))
        prepared = bridge.prepare('I ask the player by the door what they think.', 'door')
        plan = RecordingModel().plan(prepared['input'])
        plan.update(focus_actor='nobody_here')
        with self.assertRaisesRegex(InvalidChange, 'not an actor present here'):
            bridge.decide('door', plan)

    def test_the_speaking_floor_follows_the_actor_card_not_a_dealer_label(self):
        source = copy.deepcopy(SOURCE)
        cards = source['public_performance']['actor_cards']
        cards['Dealer']['speech_floor'] = False
        guards = kit_agent.guard_context(source, {})
        self.assertIn('Dealer', guards['brief_speakers'])
        speech = [{'speaker': 'Narrator', 'text': ' '.join(['word'] * 40)},
                  {'speaker': 'Dealer', 'text': 'Sit.'}]
        kit_agent.check_scope(speech, {'public_brief': {'scope': 'exchange'}, 'focus_actor': 'uktarl',
                                       'improv_read': {'actor_ref': 'uktarl'}}, guards)
        self.assertNotIn('Dealer', [name for name in kit_agent.guard_context(SOURCE, {})['brief_speakers']])

    def test_general_instructions_carry_no_room_nouns(self):
        for name in ('PRIVATE_INSTRUCTIONS', 'PUBLIC_INSTRUCTIONS', 'KIT_EXPRESSION_V1'):
            text = getattr(kit_agent, name)
            for noun in ('dealer', 'ring', 'toll', 'card player', 'Nik', 'shield', 'uktarl', 'napkin'):
                self.assertIsNone(re.search(rf'\b{noun}\b', text, re.I), f'{name}: {noun}')
        self.assertIn('any check the source gives no DC', kit_agent.PRIVATE_INSTRUCTIONS.replace('Any', 'any'))
        self.assertIn('carried item', kit_agent.PRIVATE_INSTRUCTIONS)

    def test_winks_scale_with_passive_insight_not_the_claims_skill(self):
        deck = SOURCE['claims']['marked_deck']           # found with Perception, DC 13
        sharp_eyed = sheet(wis=8, skills={'perception': 9, 'insight': -1})   # Perception 19, Insight 9
        state = {'area': 'area_06c', 'actors': SOURCE['actors'], 'known_facts': []}
        band = kit_claims.pc_band('marked_deck', deck, sharp_eyed, state)
        self.assertEqual(band, 'fingerprint')
        self.assertEqual(kit_claims.wink_tier(deck, sharp_eyed, SOURCE['actors'], band), 'none')
        wise = sheet(wis=18, skills={'perception': 9, 'insight': 9})        # Insight 19: 6 over 13
        self.assertEqual(kit_claims.wink_tier(deck, wise, SOURCE['actors'], 'fingerprint'), 'name_kind')
        doc = (Path(__file__).parent.parent / 'docs/architecture/kit-claims-knowers.md').read_text()
        self.assertIn('Winks scale with the PC\'s **passive Insight**', doc)


if __name__ == '__main__':
    unittest.main()

"""Table call 8 (2026-10-03): players may substitute skills, but each skill gates what it
reveals. Perception notices what is there, Investigation deduces from physical clues, and
Insight (Wisdom) reads motive and the why. In area 6c the why of the vampire act
(false_vampires) is Insight's; the powder line and fake fangs (vampire_tells) are
Perception's and Investigation's. Every die is pinned (Kit's d20 overridden; the player's
rolls stated the way Avrae reports them)."""
import copy
import json
import unittest
from pathlib import Path

from runtime import kit_agent, kit_claims, kit_guards
from runtime.state_context import InvalidChange
from test_kit_6c_intents import Room

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json').read_text())
MOTIVE_WORDS = ('frighten', 'safe passage', '10 gp', 'losing coin')
TELL_WORDS = ('powder', 'fitted', 'costume')
CONCLUSIONS = ('costume', 'fitted', 'not undead', 'marks', 'marked', 'reads them', 'frighten', 'safe passage')


def roll(skill, die=18, bonus=3):
    name = skill.replace('_', ' ').title()
    article = 'an' if name[0] in 'AEIOU' else 'a'
    return f'\nWren makes {article} {name} check! 1d20 ({die}) + {bonus} = `{die + bonus}`'


class SkillGatesTheRevealTests(unittest.TestCase):
    def room(self, roll_value=20):
        return Room(self, toll=False, roll=lambda: roll_value)

    def learned(self, room):
        return set(room.state.get('known_facts') or []) | set((room.state.get('claims') or {}).get('learned') or [])

    def assertMotive(self, text):
        self.assertTrue(any(word in text for word in MOTIVE_WORDS), text)
        for word in TELL_WORDS:
            self.assertNotIn(word, text)

    def assertTells(self, text):
        self.assertTrue(any(word in text for word in TELL_WORDS), text)
        for word in MOTIVE_WORDS:
            self.assertNotIn(word, text)

    def test_insight_on_the_fangs_returns_the_motive_not_the_tells(self):
        room = self.room()
        result = room.act('I study the dealer\'s fangs closely.' + roll('insight'))
        self.assertEqual(result.kind, 'check')
        self.assertMotive(result.public_event)
        self.assertIn('false_vampires', self.learned(room))
        self.assertNotIn('vampire_tells', self.learned(room))
        self.assertIn('insight', json.dumps(result.events).casefold())

    def test_investigation_on_the_fangs_returns_the_tells_not_the_motive(self):
        room = self.room()
        result = room.act('I study the dealer\'s fangs closely.' + roll('investigation'))
        self.assertEqual(result.kind, 'check')
        self.assertTells(result.public_event)
        self.assertIn('vampire_tells', self.learned(room))
        self.assertNotIn('false_vampires', self.learned(room))
        self.assertIn('Investigation', json.dumps(result.events), 'the check records the skill used')

    def assertSnapshot(self, result, room, details):
        """Perception: observed details only, never a conclusion (Brendon: a snapshot)."""
        self.assertEqual(result.kind, 'check')
        for word in CONCLUSIONS:
            self.assertNotIn(word, result.public_event.casefold())
        learned = self.learned(room)
        self.assertFalse({'vampire_tells', 'false_vampires', 'marked_deck'} & learned, learned)
        for fact in details:
            self.assertIn(fact, learned)
            self.assertIn(SOURCE['facts'][fact]['text'], result.public_event)

    def test_perception_on_the_fangs_sees_details_not_the_conclusion(self):
        room = self.room()
        result = room.act('I look closely at their pale skin and fangs.' + roll('perception', die=12, bonus=3))
        self.assertSnapshot(result, room, ['vampire_tells_glance'])
        self.assertNotIn('vampire_tells_close', self.learned(room), 'a bare success sees one detail')

    def test_a_higher_perception_result_sees_more(self):
        room = self.room()
        result = room.act('I look closely at their pale skin and fangs.' + roll('perception', die=18, bonus=3))
        self.assertSnapshot(result, room, ['vampire_tells_glance', 'vampire_tells_close'])

    def test_perception_on_the_card_backs_sees_holes_never_marks(self):
        room = self.room()
        result = room.act('I look closely at the card backs on the table.' + roll('perception', die=20, bonus=3))
        self.assertSnapshot(result, room, ['deck_backs_glance', 'deck_backs_close'])
        follow = room.act('I study the card backs and work out the pattern.' + roll('investigation'))
        self.assertIn('marked_deck', self.learned(room), follow.public_event)

    def test_details_then_investigation_then_insight(self):
        room = self.room()
        room.act('I look closely at the dealer\'s fangs.' + roll('perception', die=12, bonus=3))
        what = room.act('I study the dealer\'s fangs closely.' + roll('investigation'))
        self.assertTells(what.public_event)
        why = room.act("I study them; something's off." + roll('insight'))
        self.assertMotive(why.public_event)

    def test_a_named_skill_gates_without_a_stated_roll(self):
        room = self.room()
        result = room.act('I use Investigation on the dealer\'s fangs.')
        self.assertTells(result.public_event)
        room = self.room()
        result = room.act('I make an Insight check on their costume.')
        self.assertMotive(result.public_event)

    def test_a_group_read_with_investigation_gets_the_tells(self):
        room = self.room()
        result = room.act("I study them; something's off." + roll('investigation'))
        self.assertTells(result.public_event)
        self.assertNotIn('false_vampires', self.learned(room))

    def test_a_group_read_with_insight_gets_the_motive(self):
        room = self.room()
        result = room.act("I study them; something's off." + roll('insight'))
        self.assertMotive(result.public_event)
        self.assertNotIn('vampire_tells', self.learned(room))

    def test_an_unnamed_close_look_at_the_fangs_is_perception(self):
        room = self.room()
        result = room.act('I look closely at the dealer\'s fangs.')
        self.assertSnapshot(result, room, ['vampire_tells_glance'])
        self.assertIn('Perception', json.dumps(result.events))

    def test_a_skill_that_finds_nothing_about_it_reveals_nothing(self):
        room = self.room()
        result = room.act('I search the fresco carving for anything loose.' + roll('insight'))
        self.assertEqual(result.public_event, 'You find nothing you can be sure of.')
        self.assertNotIn('fresco_key', self.learned(room))
        self.assertIn('insight does not reveal it', json.dumps(result.events))

    def test_a_failed_roll_reveals_neither(self):
        room = self.room()
        result = room.act('I study the dealer\'s fangs closely.' + roll('investigation', die=2, bonus=0))
        self.assertEqual(result.public_event, 'You find nothing you can be sure of.')
        self.assertFalse({'vampire_tells', 'false_vampires'} & self.learned(room))

    def test_cracking_the_act_physically_shows_the_tells_not_the_why(self):
        room = self.room()
        room.act("I lick my thumb and wipe a streak of paint off the dealer's cheek.")
        self.assertIn('vampire_tells', self.learned(room))
        self.assertNotIn('false_vampires', self.learned(room))
        result = room.act("I study them; something's off." + roll('insight'))
        self.assertMotive(result.public_event)


class SkillSwapTests(unittest.TestCase):
    def test_a_swap_is_accepted_and_gated_to_the_rolled_skill(self):
        room = Room(self, toll=False, roll=lambda: 20)
        result = room.act('I use Investigation instead of Perception on the card backs on the table.'
                          + roll('investigation'))
        learned = set(room.state['known_facts'])
        self.assertIn('marked_deck', learned, 'Investigation gets the deduced what')
        self.assertFalse({'deck_backs_glance', 'deck_backs_close'} & learned, "not Perception's snapshot")
        self.assertIn('Investigation', json.dumps(result.events), 'the check records the skill used')

    def test_an_implausible_swap_reveals_nothing(self):
        room = Room(self, toll=False, roll=lambda: 20)
        result = room.act('I use Insight on the fresco carving to find anything loose.' + roll('insight'))
        self.assertEqual(result.public_event, 'You find nothing you can be sure of.')


class SkillMetaQuestionTests(unittest.TestCase):
    QUESTIONS = ("Kit, why didn't Perception tell me the deck is marked?",
                 "What's the difference between Insight and Investigation?",
                 "Why can't I use Investigation instead of Perception for this?")

    def test_a_meta_skill_question_is_table_talk_and_carries_the_model(self):
        for question in self.QUESTIONS:
            with self.subTest(question=question):
                self.assertTrue(kit_agent.is_ooc(question))
                room = Room(self, toll=False)
                bridge = kit_agent.KitChatBridge(room.runtime)
                packet = bridge.prepare(question, 'meta', one_pass=True)
                body = room.runtime.pending_kit_turn(packet['turn_id'])['body']
                self.assertNotIn(body['kind'], ('check', 'knowledge'), 'a question is not a roll')
                core = packet['input']['private']['personality_core']
                for words in ('tomato', 'fruit salad', 'Perception is a snapshot',
                              'Investigation understands what happened', 'Insight understands why',
                              'Athletics instead of Acrobatics'):
                    self.assertIn(words, core)
                room.runtime.discard_pending_kit_turn(packet['turn_id'])

    def test_the_model_fits_the_voice_slot(self):
        from runtime import state_context
        text, warning = state_context.load_voice()
        self.assertIsNone(warning)
        self.assertIn('Working model of skills', text)


class RoomFileTests(unittest.TestCase):
    def test_the_claim_gives_the_why(self):
        claim = SOURCE['claims']['false_vampires']
        for text in (claim['truth'], SOURCE['facts']['false_vampires']['text']):
            for word in ('Undertakers', 'thugs', 'Not undead', '10 gp', 'safe passage', 'losing coin'):
                self.assertIn(word, text)
        self.assertEqual(claim['pc_check'], 'insight')
        self.assertNotIn('pc_checks', claim, 'only Insight reads the why')

    def test_the_tells_are_their_own_fact_for_perception_and_investigation(self):
        claim = SOURCE['claims']['vampire_tells']
        self.assertEqual(claim['fact'], 'vampire_tells')
        self.assertEqual(set(kit_claims.claim_skills(claim)), {'perception', 'investigation'})
        for word in ('powder', 'collar', 'fangs'):
            self.assertIn(word, SOURCE['facts']['vampire_tells']['text'])

    def test_the_fresco_is_called_a_fresco(self):
        self.assertIn('fresco', SOURCE['facts']['fresco']['text'].casefold())
        self.assertIn('carved mountain', SOURCE['facts']['fresco']['text'])

    def test_kits_npc_context_carries_the_motive(self):
        room = Room(self, toll=False)
        packet = kit_claims.claims_here(room.runtime.source(), room.state, None)
        entry = packet['claims']['false_vampires']
        self.assertIn('safe passage', entry['truth'])
        self.assertEqual(set(entry['npc_bands'].values()), {'knows'})
        for key in ('uktarl', 'bandit_a', 'bandit_b', 'doppelganger'):
            self.assertIn('toll', SOURCE['actors'][key]['motive'])

    def test_pc_checks_must_include_pc_check(self):
        source = copy.deepcopy(SOURCE)
        source['claims']['vampire_tells']['pc_checks'] = ['perception']
        with self.assertRaises(InvalidChange):
            kit_claims.compile_claims(source)

    def test_either_fact_makes_the_fake_fangs_set_public(self):
        sets = kit_guards.leak_sets(SOURCE)
        line = 'The fangs are fake.'
        with self.assertRaises(InvalidChange):
            kit_guards.check_paraphrased_leaks(line, {}, '', sets)
        for fact in ('vampire_tells', 'false_vampires'):
            with self.subTest(fact=fact):
                kit_guards.check_paraphrased_leaks(
                    line, {'known_facts_here': [SOURCE['facts'][fact]['text']]}, '', sets)


if __name__ == '__main__':
    unittest.main()

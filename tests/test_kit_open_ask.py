"""Brendon's plan (2026-10-14), step 2: answer the open ask before reading a new deed, and commit
the engine's sentence after one failed narration.

(a) The open-ask gate at the top of RoomAdjudicator.resolve. A hit on his turn with no damage
    holds the turn: the monsters wait for the damage, and the next message (a bare Avrae damage
    field, "4 piercing damage", a bare "4") is its answer. No damage in the message, or an explicit
    cancel, yields the ask: the hit stands with no damage, it was his action, and the round runs on.
    A called check takes a bare roll first; a cancel calls it off.
(b) A rejected narration commits the engine's public_event sentence (no retry).
(c) A leveled spell with no slot left fizzles before any roll is asked for (Witch Bolt).

Synthetic roadcamp room (tests/fixtures/rooms), never 6c, for every fight; every die pinned
(NPC d20s 2: every monster swing misses)."""
import copy
import unittest

from runtime import kit_agent
from runtime.kit_agent import KitAgent
from test_kit_combat_checkpoints import NIK, Camp, without_shield
from test_kit_hardening import NIK_GREETING, NIK_REPLY, BridgeCase, RecordingModel

HIT = 'Initiative 25. I stab the wagon-side cutthroat with my dagger, 18 to hit.'  # AC 12: a hit, no damage


def camp(test):
    return Camp(test, roll=lambda: 2, sheet=without_shield(NIK))


class HitWithNoDamageHoldsTheTurn(unittest.TestCase):
    """The audit's High bug (main kit_combat.py:1152 and :664): the hit returned True, so the turn
    advanced and every monster acted before the damage existed; the damage paste was then a new turn."""

    def test_the_monsters_wait_for_the_damage(self):
        table = camp(self)
        result = table.act(HIT)
        fight = table.fight
        self.assertIn('Roll damage in Avrae.', result.public_event)
        self.assertNotIn('swings at you', result.public_event, 'nobody acts before the damage')
        self.assertEqual((fight['round'], fight['order'][fight['next']]), (1, 'pc'), 'still his turn')
        self.assertEqual(fight['pending']['needs'], 'damage')
        self.assertEqual(fight['hp']['cutthroat_a'], 11)

    def test_the_next_message_answers_the_damage_ask_bare_avrae_lines_included(self):
        for answer in ('**Damage**: 1d4 (2) + 2 = `4`', 'Damage: 1d4 (2) + 2 [piercing] = 4',
                       '4 piercing damage', '4', 'I attack. 4 piercing damage.'):
            with self.subTest(answer=answer):
                table = camp(self)
                table.act(HIT)
                result = table.act(answer)
                fight = table.fight
                self.assertEqual(fight['hp']['cutthroat_a'], 7, 'the 4 lands once')
                self.assertIsNone(fight.get('pending'))
                self.assertIn('swings at you', result.public_event, 'then the round runs on')
                self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'),
                                 'one round, not two')

    def test_a_message_with_no_damage_yields_the_ask(self):
        for words in ('Forget the damage.', 'I shout at them to drop their weapons.'):
            with self.subTest(words=words):
                table = camp(self)
                table.act(HIT)
                result = table.act(words)
                fight = table.fight
                self.assertIn('No damage was rolled', result.public_event)
                self.assertIsNone(fight.get('pending'))
                self.assertEqual(fight['hp']['cutthroat_a'], 11, 'the hit deals nothing')
                self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'),
                                 'the hit was his action: the round ran on')

    def test_a_new_attack_with_its_own_to_hit_is_no_answer_and_waits_for_his_next_turn(self):
        table = camp(self)
        table.act(HIT)
        result = table.act('I stab the bandit captain with my dagger, 17 to hit, 5 piercing')
        fight = table.fight
        self.assertEqual(fight['hp']['cutthroat_a'], 11, 'the 5 is not the old damage')
        self.assertIn('that waits for your next turn', result.public_event)
        self.assertEqual(fight['hp']['harl'], 25, 'it lands on his next turn')
        self.assertEqual(fight['round'], 3)

    def test_an_explicit_cancel_wins_over_a_number(self):
        table = camp(self)
        table.act(HIT)
        table.act('Never mind the damage, 4 is too low anyway.')
        self.assertEqual(table.fight['hp']['cutthroat_a'], 11)
        self.assertIsNone(table.fight.get('pending'))


class CalledCheckAnswersFirst(unittest.TestCase):
    def called(self):
        table = camp(self)
        revision, _ = table.runtime.load()
        table.runtime.commit('call', revision, [{'type': 'pending_check', 'evidence': 'Kit called Perception (test setup).',
                                                 'check': {'skill': 'perception', 'ability': 'wis', 'target': 'none',
                                                           'called_turn': 'call'}}])
        return table

    def test_a_bare_roll_answers_the_called_check(self):
        table = self.called()
        result = table.act('15')
        self.assertEqual(result.kind, 'called_check')
        self.assertNotIn('pending_check', table.state)

    def test_a_cancel_calls_the_check_off_and_the_words_resolve(self):
        table = self.called()
        result = table.act('Never mind the roll. I look around the camp.')
        self.assertNotEqual(result.kind, 'called_check')
        self.assertTrue(any(e.get('type') == 'pending_check' and e.get('check') is None for e in result.events))
        self.assertNotIn('pending_check', table.state)


class NoSlotFizzlesBeforeTheAsk(unittest.TestCase):
    """Nagatha's #123 review: Witch Bolt with no slot left asked for its attack roll first."""

    def spent(self):
        table = camp(self)
        revision, state = table.runtime.load()
        resources = copy.deepcopy(state['pc_resources'])
        for slot in resources['slots'].values():
            slot['used'] = slot['max']
        table.runtime.commit('spent', revision, [{'type': 'pc_resources', 'resources': resources,
                                                  'evidence': 'every slot spent (test setup)'}])
        return table

    def test_witch_bolt_with_no_slot_fizzles_before_the_attack_roll(self):
        table = self.spent()
        result = table.act('Initiative 25. I cast Witch Bolt at the wagon-side cutthroat.')
        self.assertIn('fizzles', result.public_event)
        self.assertNotIn('Roll the attack', result.public_event)
        self.assertFalse((table.fight.get('pending') or {}).get('needs'), 'no roll asked for')

    def test_a_cantrip_still_asks_for_its_attack(self):
        table = self.spent()
        result = table.act('Initiative 25. I cast Fire Bolt at the wagon-side cutthroat.')
        self.assertIn('Roll the attack', result.public_event)
        self.assertNotIn('fizzles', result.public_event)


class EngineLineAfterOneFailedNarration(BridgeCase):
    """The audit (kit_agent.py:2247 and :4759): rejected narrations walked to degraded mode, then
    abandon and prepare again, each another model call. Nagatha's #127 review: the engine's
    sentence commits after ONE failed narration (ENGINE_LINE_AFTER_REJECTIONS = 1)."""

    def test_the_default_is_one_failed_narration(self):
        self.assertEqual(kit_agent.ENGINE_LINE_AFTER_REJECTIONS, 1)

    def test_one_rejected_narration_commits_the_engine_sentence(self):
        self.staged(NIK_GREETING, 'once', reply_to='Whats going on here?')
        result = self.bridge.finish('once', NIK_REPLY)
        self.assertTrue(result['engine_line'])
        self.assertEqual(result['revision'], 1, 'committed, no retry asked for')
        record = self.runtime.recent_kit_turns()[-1]
        self.assertEqual(record['spoken'], f"Narrator: {record['public_event']}")
        self.assertEqual(record['engine_line']['after_rejections'], 1)
        self.assertIn('Exchange scope', record['engine_line']['last_rejection'], 'the real validator fired')
        self.assertEqual(self.runtime.kit_timing('once')['rejected_attempts'], 1)

    def test_a_hard_check_failure_also_falls_back_to_the_engine_sentence(self):
        self.staged('I take a seat.', 'hard')
        leaky = {'segments': [{'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                              {'speaker': 'Dealer', 'text': 'Sit.'}]}
        result = self.bridge.finish('hard', leaky)
        self.assertTrue(result['engine_line'])
        self.assertNotIn('doppelganger', result['spoken'].casefold())
        self.assertIn('private fact', self.runtime.recent_kit_turns()[-1]['engine_line']['last_rejection'])

    def test_a_resubmission_after_the_engine_line_returns_what_was_committed(self):
        self.staged(NIK_GREETING, 'lost', reply_to='Whats going on here?')
        first = self.bridge.finish('lost', NIK_REPLY)
        again = self.bridge.finish('lost', {'segments': [{'speaker': 'Narrator',
                                                          'text': first['spoken'][len('Narrator: '):]}]})
        self.assertTrue(again.get('already_committed'))
        self.assertEqual(again['revision'], first['revision'])

    def test_the_api_turn_commits_the_engine_sentence_after_one_failed_narration(self):
        class AlwaysLeaky(RecordingModel):
            def plan(inner, payload):
                return {**super().plan(payload), 'move': 'npc_reply', 'table_presence': 'quiet'}

            def perform(inner, payload, performance_variant='current'):
                return {'segments': [{'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                                     {'speaker': 'Dealer', 'text': 'Sit.'}]}

        result = KitAgent(self.runtime, AlwaysLeaky(), self.adjudicator).turn('I take a seat.', 'api-leak')
        self.assertEqual(result['timing']['model_calls'], 1 + 1, 'one plan and one narration, no retry')
        self.assertTrue(result['timing']['engine_line'])
        self.assertEqual(result['spoken'], f"Narrator: {result['public_event']}")


if __name__ == '__main__':
    unittest.main()

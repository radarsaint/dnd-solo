"""Nagatha's clean-host review of #129: a fresh host's opening still took seven attempts, because
each rejection named one problem and some messages named neither the field nor its shape.

1. Each of these rejections names the field and gives an example: actor basis, an incomplete
   decision (listing the missing keys), player_note length, evidence and replaces (replaces "none"
   when nothing is new), and the mirror's how.
2. Every problem in a decision comes back in one rejection, so a decision with several problems is
   fixed in one correction.

Watchroom fixture only (synthetic). Dice pinned; no model."""
import copy

from runtime import kit_agent
from test_kit_opening_friction import OpeningFriction
from test_kit_watchroom_stalls import landing


class EachMessageNamesTheFieldWithAnExample(OpeningFriction):
    def check(self, mutate, *expected):
        turn, plan = self.opening()
        mutate(plan)
        message = self.reject(turn, plan)
        for text in expected + ('Example:',):
            self.assertIn(text, message)
        return message

    def test_actor_basis(self):
        def mutate(plan):
            plan['improv_read']['actor_basis'] = 'made_up_basis'
        message = self.check(mutate, 'Actor basis is not established', 'improv_read.actor_basis', "'made_up_basis'")
        self.assertIn('"actor_basis": "none"', message)

    def test_incomplete_decision_lists_the_missing_keys(self):
        def mutate(plan):
            del plan['tone'], plan['player_mood']
        message = self.check(mutate, 'Incomplete private decision', 'missing: player_mood, tone')
        self.assertIn('"player_mood": {"read": "neutral", "cue": "none"}', message)

    def test_an_unknown_decision_key_is_named(self):
        def mutate(plan):
            plan['mood_guess'] = 'calm'
        self.check(mutate, 'Incomplete private decision', 'not allowed: mood_guess')

    def test_player_note_length(self):
        def mutate(plan):
            plan['player_note'] = {'note': 'x ' * 200, 'evidence_turns': ['this_turn'], 'replaces': 'none'}
        self.check(mutate, 'A player note must be 1–300 characters', 'player_note.note')

    def test_player_note_evidence(self):
        def mutate(plan):
            plan['player_note'] = {'note': 'Tests NPCs with direct questions.', 'evidence_turns': ['T99'],
                                   'replaces': 'none'}
        self.check(mutate, 'player_note must cite', 'player_note.evidence_turns', "'T99'", '"this_turn"')

    def test_player_note_replaces_an_unknown_note(self):
        def mutate(plan):
            plan['player_note'] = {'note': 'Tests NPCs with direct questions.', 'evidence_turns': ['this_turn'],
                                   'replaces': 'n9'}
        message = self.check(mutate, 'replaces an unknown note', 'player_note.replaces', "'n9'")
        self.assertIn('"replaces": "none"', message)

    def test_mirror_how(self):
        def mutate(plan):
            plan['public_brief']['mirror'] = 'steady energy, standard, dry humor: ok'
        self.check(mutate, 'mirror must say', 'public_brief.mirror', kit_agent.kit_voice.MIRROR_FORMAT)


class EveryProblemAtOnce(OpeningFriction):
    def broken(self, plan):
        bad = copy.deepcopy(plan)
        bad['improv_read']['actor_basis'] = 'made_up_basis'
        bad['player_note'] = {'note': 'Tests NPCs with direct questions.', 'evidence_turns': ['this_turn'],
                              'replaces': 'n9'}
        bad['public_brief']['mirror'] = 'steady energy, standard, dry humor: ok'
        bad['public_brief']['kit_focus'] = 'Make the scene feel tense and interesting.'
        del bad['tone']
        return bad

    def test_one_rejection_names_every_problem(self):
        turn, plan = self.opening()
        message = self.reject(turn, self.broken(plan))
        for text in ('missing: tone', 'improv_read.actor_basis', 'player_note.replaces',
                     'public_brief.mirror', 'kit_focus is too generic'):
            self.assertIn(text, message)
        self.assertIn('5 problems', message)

    def test_a_multi_error_opening_is_fixed_in_one_correction(self):
        # A host that fixes exactly what the rejection names (one per attempt before: 7 attempts).
        turn, plan = self.opening()
        bad = self.broken(plan)
        message = self.reject(turn, bad)
        fixes = {
            'tone': lambda d: d.__setitem__('tone', plan['tone']),
            'improv_read.actor_basis': lambda d: d['improv_read'].__setitem__('actor_basis', 'none'),
            'player_note.replaces': lambda d: d['player_note'].__setitem__('replaces', 'none'),
            'public_brief.mirror': lambda d: d['public_brief'].__setitem__('mirror', plan['public_brief']['mirror']),
            'kit_focus': lambda d: d['public_brief'].__setitem__('kit_focus', plan['public_brief']['kit_focus']),
        }
        corrected = copy.deepcopy(bad)
        for field, fix in fixes.items():
            if field in message:
                fix(corrected)
        result = self.bridge.complete(turn, {'decision': corrected, 'performance': landing()})
        self.assertIn('spoken', result)
        self.assertEqual(self.bridge.guidance(turn)['rejected_attempts'], 1)

    def test_one_problem_reads_as_before(self):
        turn, plan = self.opening()
        plan['public_brief']['kit_focus'] = 'Make the scene feel tense and interesting.'
        message = self.reject(turn, plan)
        self.assertNotIn('problems', message)
        self.assertIn('kit_focus is too generic', message)


if __name__ == '__main__':
    import unittest
    unittest.main()

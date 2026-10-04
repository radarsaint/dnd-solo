"""Brendon's voice spec as carriers (runtime/kit_voice.py): the private mood read and
its public mirror, turn modes, showtime presence, and NPC noticing. For each carrier:
it reaches the performer, its private source does not, and the validator rejects a
turn that ignores it."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_voice
from runtime.kit_agent import KitAgent, KitChatBridge, RoomAdjudicator, check_speech
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import (EXCHANGE_SPEECH, FIXTURE, MIRROR, NIK_GREETING, QUIET_EXCHANGE_SPEECH,
                            RecordingModel, exchange_speech)

OOC = "(OOC) Kit, quick rules question: what do I roll to tell if they're really vampires?"
PACING_CUE = 'pacing: replies shrank from forty words to three'
TIGHT = 'high energy, tight, no humor: skip the scenery and get the dealer to the point'
BORED = 'This is taking forever. Just deal.'
THREAT = 'I draw my blade and snarl, "Last chance to deal me in."'
LONG_SPEECH = {'segments': [
    {'speaker': 'Narrator', 'text': ('The dealer takes his time. He squares the deck, taps it twice, fans '
                                     'it, closes it, and sets it down with the care of a jeweler laying out '
                                     'a necklace. The lamplight wobbles. Somebody coughs. The silver ring in '
                                     'the pot catches the light and throws it across the ceiling while the '
                                     'other players shuffle their coins and glance at the doorway.')},
    {'speaker': 'Dealer', 'text': ('Patience, friend, patience. A good game is like a good meal: it must be '
                                   'savored, not wolfed. I have dealt at this table longer than you have '
                                   'been walking these halls, and I have learned that the ones who hurry '
                                   'are the ones who lose. So sit, breathe, and tell me what you came to '
                                   'wager tonight, and we shall begin when I say we begin.')}]}
COMBAT_SPEECH = {'segments': [
    {'speaker': 'Narrator', 'text': ('Steel hisses free. Coins jump. A stool scrapes back and topples. '
                                     'Every pale face turns to the blade in your hand.')},
    {'speaker': 'Dealer', 'text': ('Put that away before you cut yourself, friend. You want in? Then pay in '
                                   'like everyone else. Draw on me again and the whole table stops being '
                                   'friendly. Your move, friend: coin or steel?')}]}
DRAGGING_COMBAT = {'segments': [
    {'speaker': 'Narrator', 'text': ('As the steel slides free of its scabbard with a long and lingering hiss '
                                     'that seems to echo off every carved dwarf in the mountain behind the '
                                     'table, the pale players slowly and deliberately turn their heads '
                                     'toward you in a single unhurried motion.')},
    COMBAT_SPEECH['segments'][1]]}
# Kit's theatrical narration carries the scene; the dealer answers.
SHOWTIME_SPEECH = {'segments': [
    {'speaker': 'Kit', 'text': ('Oh, you want the room? You get the room. Picture it: lamplight the colour of '
                                'weak tea, a carved mountain crowded with tiny dwarves glaring down, and four '
                                'gamblers holding perfectly, magnificently still.'),
     'reacts_to': 'take in the whole room'},
    {'speaker': 'Narrator', 'text': 'A card pauses.'},
    {'speaker': 'Dealer', 'text': ('A visitor who stops to admire the decor. Most people look at the coins '
                                   'first, friend. The table is where the real art is. Care to sit, or shall '
                                   'I keep you as an audience?')}]}
ROLL_PROMPT = {'segments': [
    {'speaker': 'Kit', 'text': 'Wisdom (Insight): you are reading people. Tell me you study them and I will call it.',
     'reacts_to': 'what do I roll'}]}


class VoiceTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.adjudicator = RoomAdjudicator(perception=0, insight=0, roll=lambda: 20)
        self.bridge = KitChatBridge(self.runtime, self.adjudicator)
        self.model = RecordingModel()

    def plan(self, prepared_input, brief=None, **updates):
        plan = self.model.plan(prepared_input)
        plan.update(updates)
        plan['public_brief'].update(brief or {})
        return plan

    def accepts(self, turn_id, plan):
        """Run the decision checks without fixing the plan (decide fixes it once)."""
        body = self.runtime.pending_kit_turn(turn_id)['body']
        state = self.runtime.load()[1]
        kit_agent.check_decision(self.runtime, plan,
                                 kit_agent.kit_memory(self.runtime, state, body['action'], True), body)

    def first_turn(self):
        KitAgent(self.runtime, RecordingModel(), self.adjudicator).turn('I take a seat.', 'seat')


class MoodMirrorTests(VoiceTestCase):
    def test_host_is_told_to_read_mood_and_mirror_it(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'fast', one_pass=True)
        decision = prepared['schema']['properties']['decision']
        self.assertIn('player_mood', decision['required'])
        self.assertEqual(decision['properties']['player_mood']['properties']['read']['enum'],
                         list(kit_voice.MOOD_READS))
        self.assertIn('mirror', decision['properties']['public_brief']['required'])
        for phrase in ('player_mood', kit_voice.MIRROR_FORMAT, 'momentum', 'Never pad to reach a length',
                       'player_mood is private', 'honor its energy, length, and humor'):
            self.assertIn(phrase, prepared['instructions'])
        self.assertIn('tight', prepared['performance_limits']['mirror'])
        read = prepared['input']['private']['table_read']
        self.assertEqual((read['mode_hint'], read['out_of_character'], read['player_words']), (None, False, 14))
        self.assertNotIn('table_read', json.dumps(prepared['input']['public']))

    def test_mirror_reaches_the_performer_and_the_mood_read_does_not(self):
        self.first_turn()
        prepared = self.bridge.prepare(BORED, 'bored')
        self.assertEqual(prepared['input']['table_read']['recent_player_words'], [4])
        plan = self.plan(prepared['input'], brief={'mirror': TIGHT},
                         player_mood={'read': 'bored', 'cue': PACING_CUE}, turn_mode='banter',
                         move='npc_reply', table_presence='quiet')
        payload = self.bridge.decide('bored', plan)
        selected = payload['input']['selected_move']
        self.assertEqual((selected['brief']['mirror'], selected['turn_mode']), (TIGHT, 'banter'))
        # The personality core is public documentation of Kit; check everything else.
        text = json.dumps({k: v for k, v in payload['input'].items() if k != 'personality_core'},
                          ensure_ascii=False)
        for private in ('player_mood', PACING_CUE, 'bored', 'table_read'):
            self.assertNotIn(private, text.replace(BORED, ''))
        self.assertIn('mirror', payload['instructions'])
        # Momentum, not padding: a bored player's tight turn cannot ramble.
        with self.assertRaisesRegex(InvalidChange, 'Mirror says tight: 1[0-9][0-9] words'):
            self.bridge.finish('bored', LONG_SPEECH)
        # A fresh line: the first turn already used exchange_speech(0), and recycling it is padding.
        result = self.bridge.finish('bored', exchange_speech(1, kit=False))
        trace = self.runtime.recent_kit_turns()[-1]['trace']
        self.assertEqual(trace['player_mood'], {'read': 'bored', 'cue': PACING_CUE})
        self.assertNotIn('bored', result['spoken'])

    def test_mood_cue_must_point_at_something_observable(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'cue')
        good = self.plan(prepared['input'], player_mood={'read': 'curious', 'cue': 'Whats going on here?'},
                         brief={'mirror': 'steady energy, standard, dry humor: answer the curiosity with a hook'})
        self.accepts('cue', good)
        for cue, reason in [('The player seems curious and eager.', 'quote the player'),
                            ('feedback n9', 'unknown player note'),
                            (PACING_CUE, 'needs earlier turns'),
                            ('pacing:', 'say what changed')]:
            with self.subTest(cue=cue), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('cue', {**good, 'player_mood': {'read': 'curious', 'cue': cue}})
        with self.assertRaisesRegex(InvalidChange, 'Invalid player_mood read'):
            self.bridge.decide('cue', {**good, 'player_mood': {'read': 'angry', 'cue': 'Whats going on here?'}})
        opening = self.bridge.prepare(turn_id='open', opening=True)
        plan = self.plan(opening['input'], player_mood={'read': 'playful', 'cue': 'none'},
                         move='world_description')
        with self.assertRaisesRegex(InvalidChange, 'no player to read yet'):
            self.bridge.decide('open', plan)

    def test_mirror_is_checkable_and_fits_the_mood(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'fit')
        base = self.plan(prepared['input'])
        cue = 'Whats going on here?'
        cases = [
            ('neutral', 'Be fun.', 'mirror must read'),
            ('neutral', 'high energy, tight, dry humor: go', 'how Kit answers'),
            ('neutral', 'high energy, tight, dry humor: say "hello there" warmly', 'not quoted dialogue'),
            ('bored', 'high energy, standard, dry humor: give them a jolt', 'momentum, not more words'),
            ('frustrated', 'steady energy, tight, playful humor: lighten things up', 'no or dry'),
            ('tense', 'low energy, standard, playful humor: tease them a bit', 'no or dry'),
            ('gleeful', 'high energy, roomy, no humor: play it straight', 'gets play back'),
        ]
        for mood, mirror, reason in cases:
            with self.subTest(mirror=mirror), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('fit', {**base, 'player_mood': {'read': mood, 'cue': cue},
                                           'public_brief': {**base['public_brief'], 'mirror': mirror}})
        playful = 'high energy, roomy, playful humor: match the grin and raise it'
        self.accepts('fit', {**base, 'player_mood': {'read': 'gleeful', 'cue': cue},
                                   'public_brief': {**base['public_brief'], 'mirror': playful}})

    def test_feedback_can_drive_the_mood_read(self):
        self.first_turn()
        note = self.bridge.feedback('This is dragging; I want things to happen faster.')['note']
        prepared = self.bridge.prepare('What are the stakes?', 'stakes')
        self.assertEqual(prepared['input']['table_read']['feedback_note_ids'], [note['id']])
        mood = {'read': 'frustrated', 'cue': f"feedback {note['id']}"}
        plan = self.plan(prepared['input'], player_mood=mood, move='npc_reply', table_presence='quiet')
        with self.assertRaisesRegex(InvalidChange, 'momentum'):
            self.bridge.decide('stakes', plan)
        plan['public_brief']['mirror'] = TIGHT
        payload = self.bridge.decide('stakes', plan)['input']
        self.assertNotIn(note['note'], json.dumps(payload, ensure_ascii=False))


class TurnModeTests(VoiceTestCase):
    def test_mode_is_detected_where_code_can_and_declared_otherwise(self):
        for action, hint in ((OOC, 'meta'), ('I look inside the tub.', 'description'), (NIK_GREETING, None)):
            with self.subTest(action=action):
                read = self.bridge.prepare(action, f't-{hint}')['input']['table_read']
                self.assertEqual(read['mode_hint'], hint)
        opening = self.bridge.prepare(turn_id='open', opening=True)
        self.assertEqual(opening['input']['table_read']['mode_hint'], 'description')

    def test_mode_must_agree_with_what_code_detects(self):
        prepared = self.bridge.prepare(OOC, 'ooc')
        plan = self.plan(prepared['input'], move='ruling', focus_actor='none', table_presence='present',
                         brief={'scope': 'call'})
        plan['improv_read']['actor_ref'] = 'none'
        plan['improv_read']['actor_basis'] = 'none'
        self.assertEqual(plan['turn_mode'], 'meta')
        with self.assertRaisesRegex(InvalidChange, 'turn_mode must be meta'):
            self.bridge.decide('ooc', {**plan, 'turn_mode': 'banter'})
        with self.assertRaisesRegex(InvalidChange, 'cannot be quiet'):
            self.bridge.decide('ooc', {**plan, 'table_presence': 'quiet'})
        payload = self.bridge.decide('ooc', plan)
        self.assertEqual(payload['input']['selected_move']['turn_mode'], 'meta')
        narrated = {'segments': [{'speaker': 'Narrator', 'text': 'Roll Wisdom (Insight).'}]}
        with self.assertRaises(InvalidChange):
            self.bridge.finish('ooc', narrated)
        self.assertEqual(self.bridge.finish('ooc', ROLL_PROMPT)['revision'], 1)
        tub = self.bridge.prepare('I look inside the tub.', 'tub')
        tub_plan = self.plan(tub['input'], move='world_description', table_presence='quiet')
        with self.assertRaisesRegex(InvalidChange, 'room action is a description'):
            self.bridge.decide('tub', {**tub_plan, 'turn_mode': 'banter'})

    def test_combat_mode_is_tense_and_punchy(self):
        prepared = self.bridge.prepare(THREAT, 'threat')
        plan = self.plan(prepared['input'], turn_mode='combat', move='npc_reply', table_presence='quiet',
                         player_mood={'read': 'tense', 'cue': 'Last chance'},
                         brief={'mirror': 'high energy, standard, no humor: meet the steel with steel'})
        playful = {**plan, 'public_brief': {**plan['public_brief'],
                                            'mirror': 'high energy, standard, dry humor: wink at the danger'}}
        self.accepts('threat', {**playful, 'player_mood': {'read': 'neutral', 'cue': 'none'}})
        with self.assertRaisesRegex(InvalidChange, 'showtime'):
            self.bridge.decide('threat', {**plan, 'table_presence': 'showtime'})
        payload = self.bridge.decide('threat', plan)
        self.assertEqual(payload['input']['selected_move']['turn_mode'], 'combat')
        with self.assertRaisesRegex(InvalidChange, 'Combat narration dragged'):
            self.bridge.finish('threat', DRAGGING_COMBAT)
        self.assertEqual(self.bridge.finish('threat', COMBAT_SPEECH)['revision'], 1)


class ShowtimeTests(VoiceTestCase):
    def test_showtime_gives_kit_the_stage_and_counts_her_narration(self):
        prepared = self.bridge.prepare('I stop and take in the whole room before anyone speaks.', 'show')
        self.assertIn('showtime', prepared['schema']['properties']['table_presence']['enum'])
        plan = self.plan(prepared['input'], table_presence='showtime', turn_mode='description',
                         move='kit_comment_then_npc',
                         brief={'mirror': 'high energy, roomy, playful humor: ham up the reveal'})
        payload = self.bridge.decide('show', plan)
        self.assertIn('showtime', payload['instructions'])
        self.assertIn('overacting is welcome', payload['instructions'])
        # No word floor counts Kit's segment in or out any more (#102): the turn hands off on the
        # Dealer's question under `present` as under showtime.
        present = {**plan, 'table_presence': 'present'}
        check_speech(SHOWTIME_SPEECH, present, {}, 'I stop and take in the whole room', 'social')
        check_speech(SHOWTIME_SPEECH, plan, {}, 'I stop and take in the whole room', 'social')
        too_much = {'segments': [{'speaker': 'Kit', 'text': 'Look at it.', 'reacts_to': 'take in the whole room'}] * 4 + SHOWTIME_SPEECH['segments'][1:]}
        with self.assertRaisesRegex(InvalidChange, 'Showtime: Kit takes the stage in 1-'):
            self.bridge.finish('show', too_much)
        self.assertEqual(self.bridge.finish('show', SHOWTIME_SPEECH)['revision'], 1)

    def test_showtime_never_breaks_a_call_or_a_frustrated_player(self):
        prepared = self.bridge.prepare('Can I roll Insight on them?', 'roll')
        plan = self.plan(prepared['input'], move='ruling', focus_actor='none', table_presence='showtime',
                         brief={'scope': 'call'})
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        with self.assertRaisesRegex(InvalidChange, 'Showtime is never a call'):
            self.bridge.decide('roll', plan)
        frustrated = {**plan, 'public_brief': {**plan['public_brief'], 'scope': 'exchange', 'mirror': TIGHT},
                      'player_mood': {'read': 'frustrated', 'cue': 'Can I roll'}}
        with self.assertRaisesRegex(InvalidChange, 'frustrated player gets momentum'):
            self.bridge.decide('roll', frustrated)
        # A simple roll prompt stays a short call at brief presence.
        self.bridge.decide('roll', {**plan, 'table_presence': 'brief'})
        prompt = {'segments': [{**ROLL_PROMPT['segments'][0], 'reacts_to': 'roll Insight on them'}]}
        self.assertEqual(self.bridge.finish('roll', prompt)['revision'], 1)


class NpcNoticeTests(VoiceTestCase):
    NOTICE = 'mood: the visitor is openly delighted, which the dealer reads as a mark ready to bet big'

    def test_npc_notice_reaches_the_performer_as_the_actors_own_reaction(self):
        prepared = self.bridge.prepare('Ha! I love this place. Deal me in!', 'glee', one_pass=True)
        for phrase in ('npc_notice', 'for their own reasons', 'no NPC borrows her wit'):
            self.assertIn(phrase, prepared['instructions'])
        plan = self.plan(prepared['input']['private'], player_mood={'read': 'gleeful', 'cue': 'I love this place'},
                         brief={'npc_notice': self.NOTICE,
                                'mirror': 'high energy, standard, playful humor: meet the glee head on'})
        result = self.bridge.complete('glee', {'decision': plan, 'performance': EXCHANGE_SPEECH})
        self.assertEqual(result['revision'], 1)
        saved = self.runtime.recent_kit_turns()[-1]['trace']['public_brief']['npc_notice']
        self.assertEqual(saved, self.NOTICE)

    def test_npc_notice_is_grounded_in_the_fiction_and_the_actor_speaks(self):
        self.first_turn()
        note = self.bridge.feedback('Honestly I am bored of the dealer stalling.')['note']
        prepared = self.bridge.prepare('Fine. What now?', 'notice')
        plan = self.plan(prepared['input'], memory_refs=[], player_mood={'read': 'bored', 'cue': 'Fine. What now?'},
                         brief={'mirror': TIGHT, 'npc_notice': self.NOTICE.replace('delighted', 'bored')})
        self.accepts('notice', plan)
        bad = [
            ('the dealer notices the visitor is bored', 'must read'),
            ('attitude: the visitor sighs and the dealer takes offence', 'must read'),
            ('stunt: the dealer says "sit down" to the visitor', 'not an NPC line'),
            ('mood: the dealer echoes Kit and teases the visitor', 'never Kit'),
            ('past_act: the dealer remembers the visitor taking a seat', 'memory_refs'),
        ]
        for notice, reason in bad:
            with self.subTest(notice=notice), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('notice', {**plan, 'public_brief': {**plan['public_brief'], 'npc_notice': notice}})
        # The past act from memory is fine once the remembered turn is cited.
        self.accepts('notice', {**plan, 'memory_refs': ['seat'], 'public_brief': {
            **plan['public_brief'], 'npc_notice': 'past_act: the dealer remembers the visitor sat without paying'}})
        # NPCs never react to out-of-character feedback or pacing.
        for cue in (f"feedback {note['id']}", PACING_CUE):
            with self.subTest(cue=cue), self.assertRaisesRegex(InvalidChange, 'never out-of-character'):
                self.bridge.decide('notice', {**plan, 'player_mood': {'read': 'bored', 'cue': cue}})
        with self.assertRaisesRegex(InvalidChange, 'needs a focus actor'):
            self.bridge.decide('notice', {**plan, 'focus_actor': 'none', 'move': 'world_description',
                                          'improv_read': {**plan['improv_read'], 'actor_ref': 'none',
                                                          'actor_basis': 'none'}})
        self.bridge.decide('notice', {**plan, 'move': 'world_description', 'table_presence': 'quiet'})
        silent = {'segments': [{'speaker': 'Narrator', 'text': ' '.join(['The coins glint.'] * 14)}]}
        with self.assertRaisesRegex(InvalidChange, 'npc_notice: the Dealer never reacted'):
            self.bridge.finish('notice', silent)

    def test_no_npc_notice_on_table_talk(self):
        prepared = self.bridge.prepare(OOC, 'ooc')
        plan = self.plan(prepared['input'], table_presence='present',
                         brief={'npc_notice': 'stunt: the dealer sees the visitor squinting at his teeth'})
        with self.assertRaisesRegex(InvalidChange, 'NPCs do not hear table talk'):
            self.bridge.decide('ooc', plan)


class HardeningGuardTests(VoiceTestCase):
    """Brendon's spec asks for theatre, overacting, and tense combat. kit-hardening's
    guards (padding, player agency, paraphrase leaks, NPC register) still apply to all of
    it: theatre is specific images, never repetition, stock atmosphere, the player's
    feelings, or a hint at a hidden truth."""
    ACTION = 'I stop and take in the whole room before anyone speaks.'

    def guarded(self, speech, plan):
        source = self.runtime.source()
        return check_speech(speech, plan, {}, self.ACTION, 'social',
                            guards=kit_agent.guard_context(source, {'public_history': []}))

    def showtime_plan(self):
        prepared = self.bridge.prepare(self.ACTION, 'guards')
        return self.plan(prepared['input'], table_presence='showtime', turn_mode='description',
                         brief={'mirror': 'high energy, roomy, playful humor: ham up the reveal'})

    def test_theatrical_overacting_passes_every_guard(self):
        self.guarded(SHOWTIME_SPEECH, self.showtime_plan())

    def test_overacting_is_not_a_licence_to_pad_or_to_feel_for_the_player(self):
        plan = self.showtime_plan()
        dealer = SHOWTIME_SPEECH['segments'][1:]
        cases = [
            ('Padding: the turn repeats', 'Behold the lamplight on the old coins. Behold the lamplight on the old coins.'),
            ('Padding: stock filler', 'Oh, the drama. The tension is palpable and every coin glitters.'),
            ('Player agency', 'Oh, the drama. Your heart pounds as the gamblers hold perfectly still.'),
            ('paraphrases a private fact', 'Oh, the drama. Four pale gamblers, theatrically still.'),
        ]
        for reason, kit_line in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(InvalidChange, reason):
                self.guarded({'segments': [{'speaker': 'Kit', 'text': kit_line, 'reacts_to': 'take in the whole room'}] + dealer}, plan)

    def test_voice_style_floors_soften_in_degraded_mode_but_presence_does_not(self):
        prepared = self.bridge.prepare(BORED, 'degrade')
        plan = self.plan(prepared['input'], brief={'mirror': TIGHT}, move='npc_reply', table_presence='quiet',
                         player_mood={'read': 'bored', 'cue': 'taking forever'})
        self.bridge.decide('degrade', plan)
        for _ in range(kit_agent.DEGRADED_AFTER_REJECTIONS):
            with self.assertRaisesRegex(InvalidChange, 'Mirror says tight'):
                self.bridge.finish('degrade', LONG_SPEECH)
        result = self.bridge.finish('degrade', LONG_SPEECH, degraded=True)
        self.assertTrue(any('Mirror says tight' in warning for warning in result['soft_warnings']))
        with self.assertRaisesRegex(InvalidChange, 'Showtime: Kit takes the stage'):
            check_speech(QUIET_EXCHANGE_SPEECH, {**plan, 'table_presence': 'showtime'}, {}, BORED,
                         'social', degraded=True)


class CompatibilityTests(VoiceTestCase):
    def test_both_variants_face_the_same_voice_checks(self):
        for variant in ('current', 'kit_expression_v1'):
            with self.subTest(variant=variant):
                self.assertIn('mirror', kit_agent.PERFORMANCE_VARIANTS[variant])
                self.assertIn('npc_notice', kit_agent.PERFORMANCE_VARIANTS[variant])
                turn = f'v-{variant}'
                prepared = self.bridge.prepare(BORED, turn, one_pass=True, performance_variant=variant)
                plan = self.plan(prepared['input']['private'], brief={'mirror': TIGHT},
                                 player_mood={'read': 'bored', 'cue': 'taking forever'},
                                 move='npc_reply', table_presence='quiet')
                with self.assertRaisesRegex(InvalidChange, 'Mirror says tight'):
                    self.bridge.complete(turn, {'decision': plan, 'performance': LONG_SPEECH})
                self.bridge.runtime.db.execute('DELETE FROM kit_pending')
                self.bridge.runtime.db.commit()

    def test_a_decision_fixed_before_the_voice_carriers_still_performs(self):
        old = self.model.plan(self.bridge.prepare(NIK_GREETING, 'old')['input'])
        for key in ('player_mood', 'turn_mode'):
            old.pop(key)
        for key in ('mirror', 'npc_notice'):
            old['public_brief'].pop(key)
        check_speech(EXCHANGE_SPEECH, old, {}, NIK_GREETING, 'social')
        kit_voice.check_voice_presence(LONG_SPEECH['segments'], old)
        kit_voice.check_voice_style(LONG_SPEECH['segments'], old)


if __name__ == '__main__':
    unittest.main()

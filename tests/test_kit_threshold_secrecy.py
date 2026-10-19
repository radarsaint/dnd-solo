"""Nagatha's clean-host review (8c on main de442cf): a threshold look committed what lies inside.
"Inside, Vex the vampire deals cards to two bandits in costume." was accepted: the hidden-actor
check catches only status 'hidden', and nothing checked the next area's people, their secrets and
true identities, its claims, or its unfound contents. A look or listen through a threshold is
tease-only (kit_brief.THRESHOLD_RULE): the narration may use the tease, what is heard, and what
the PC already perceives, never the inside.

Synthetic: the watchroom fixture with a claim about the warden and a secret added (no book text).
Dice pinned (10s)."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent
from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import LANDING, LANDING_MORE, PEEKS, Stalls, landing
from test_kit_room_review import WATCH


def secret_watchroom(test):
    source = json.loads(Path(WATCH).read_text())
    warden = source['actors']['warden']
    warden['secrets'] = ['He sold the back stair key to the smugglers below.']
    warden['stat_block'] = {**(warden.get('stat_block') or {}), 'srd': 'Veteran'}
    source['claims'] = {'warden_true': {
        'about': 'actor:warden/identity', 'truth': 'The warden is a deserter wearing a stolen uniform.',
        'source': 'kit', 'roots': ['actor:warden'], 'exposure': 'hidden', 'dc': 14,
        'pc_check': 'insight', 'pc_access': 'roll', 'holders': {'warden': 'knows'},
        'subject_words': ['deserter', 'uniform']}}
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    path = Path(folder.name) / 'watchroom_secret.json'
    path.write_text(json.dumps(source))
    return path


LEAKS = {
    'the name of who is inside': 'Inside, the watch warden sits over a ledger with his spear at hand.',
    'a true identity (stat block)': 'Inside, a grizzled veteran bends over his ledger with a spear at hand.',
    'a hidden claim': 'Inside, a deserter in a stolen uniform hums the same four notes and waits.',
    'an actor secret': 'Inside sits the man who sold the back stair key to the smugglers below.',
    'unfound contents': 'Inside, a coil of rope and a sealed letter lie in the chest under the slit.',
}


class ThresholdLookIsTeaseOnly(Stalls):
    def setUp(self):
        super().setUp()
        self.runtime = self.start(secret_watchroom(self))
        from runtime.kit_agent import KitChatBridge, RoomAdjudicator
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))

    def peek(self, text, turn='p'):
        packet = self.bridge.prepare(PEEKS[1], turn, one_pass=True)
        self.assertIn('threshold_view', packet['input']['private'])
        plan = self.plan_for(packet)
        plan['public_brief'].update(reply_to='I peek through the gap', scope='exchange')
        return self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': LANDING}, {'speaker': 'Narrator', 'text': text}]}})

    def test_what_lies_inside_is_refused_on_a_threshold_look(self):
        for n, (label, text) in enumerate(LEAKS.items()):
            with self.subTest(label):
                with self.assertRaisesRegex(InvalidChange, 'threshold'):
                    self.peek(text, turn=f'p{n}')
                self.bridge.abandon(f'p{n}')
        self.assertEqual(self.runtime.load()[1]['area'], 'landing')

    def test_the_tease_and_what_is_heard_still_commit(self):
        result = self.peek(LANDING_MORE)
        self.assertIn('hums the same four notes', result['spoken'])

    def test_the_words_come_from_the_next_area_only(self):
        revision, state = self.runtime.load()
        words = kit_agent.threshold_hidden_words(self.runtime.source(), state, 'iron_door',
                                                 {'public_view': {}, 'action': PEEKS[1]})
        flat = ' | '.join(words)
        for word in ('warden', 'veteran', 'deserter', 'stolen uniform', 'sealed letter'):
            self.assertIn(word, flat)
        self.assertNotIn('humming', flat, 'the tease and what is heard are public')

    def test_inside_the_room_the_same_narration_is_fine(self):
        self.go_in()
        packet = self.bridge.prepare('I look at the warden.', 'i', one_pass=True)
        self.assertNotIn('threshold_view', packet['input']['private'])
        self.assertEqual(kit_agent.threshold_hidden_words(self.runtime.source(), self.runtime.load()[1], None, {}), [])


if __name__ == '__main__':
    unittest.main()

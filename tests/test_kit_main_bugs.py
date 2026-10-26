"""Bugs still on main after PR 145 (/workspace/kit2/pr145-bugs.md), fixed in the PR stacked on
#150. Watchroom fixture, dice pinned, no model."""
import json
import unittest

from runtime import kit_agent, kit_rooms
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime, encode
from test_kit_watchroom_stalls import Stalls


def find(node, key):
    """Every value under `key` anywhere in a packet."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from find(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from find(v, key)


class HiddenFactsArriveOnTheEntryTurn(Stalls):
    def test_entry_turn_carries_the_rooms_hidden_facts(self):
        packet = self.bridge.prepare('I go through the iron door.', 'in', one_pass=True)
        hidden = set()
        for facts in find(packet, 'unrevealed_facts'):
            hidden |= set(facts)
        self.assertIn('chest_contents', hidden)
        self.assertNotIn('humming', hidden)

    def test_a_turn_without_a_move_is_unchanged(self):
        packet = self.bridge.prepare('I wait on the landing and listen.', 'l', one_pass=True)
        hidden = set()
        for facts in find(packet, 'unrevealed_facts'):
            hidden |= set(facts)
        self.assertNotIn('chest_contents', hidden)


if __name__ == '__main__':
    unittest.main()

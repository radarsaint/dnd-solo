"""Tests for DM Kit's player-safe visual brief path."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_rooms, kit_visual
from runtime.kit_agent import DEFAULT_ROOM
from runtime.state_context import Runtime


class VisualBriefTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        self.path = Path(handle.name)
        self.runtime = Runtime(self.path)
        source = kit_rooms.load_room(DEFAULT_ROOM)
        self.runtime.initialize(source, source["starting_area"])

    def tearDown(self):
        self.runtime.close()
        self.path.unlink(missing_ok=True)

    def test_visual_brief_contains_only_player_view_facts(self):
        brief = kit_visual.build_visual_brief(
            self.runtime, "Draw what I can see right now.", "scene_vignette")
        kit_visual.validate_visual_brief(brief)

        self.assertEqual(brief["schema"], "kit_visual_brief_v1")
        self.assertEqual(
            brief["player_safe_facts"]["known_facts_here"],
            self.runtime.player_view()["known_facts_here"])
        self.assertEqual(
            brief["player_safe_facts"]["visible_subjects"],
            [{"name": actor["name"], "status": actor["status"]}
             for actor in self.runtime.player_view()["actors"]])

    def test_visual_brief_does_not_leak_room_secrets(self):
        text = json.dumps(
            kit_visual.build_visual_brief(self.runtime, "Show me the room."),
            ensure_ascii=False).casefold()

        for secret in (
            "doppelganger",
            "marked deck",
            "marked cards",
            "stone key",
            "pretending to be vampires",
            "uktarl",
            "harria",
        ):
            self.assertNotIn(secret, text)

    def test_visual_brief_does_not_change_game_state(self):
        before_revision, before_state = self.runtime.load()
        kit_visual.build_visual_brief(self.runtime, "Portrait of whoever is visible.", "character_spotlight")
        after_revision, after_state = self.runtime.load()

        self.assertEqual(before_revision, after_revision)
        self.assertEqual(before_state, after_state)

    def test_visual_mode_aliases_are_for_api_use_but_cli_modes_are_canonical(self):
        self.assertEqual(kit_visual.normalize_mode("portrait"), "character_spotlight")
        self.assertEqual(kit_visual.normalize_mode(None), "scene_vignette")

    def test_reference_rule_requires_variety(self):
        brief = kit_visual.build_visual_brief(self.runtime, "Draw this.")
        rule = brief["style"]["reference_selection_rule"].casefold()
        self.assertIn("varied", rule)
        self.assertIn("do not repeatedly default", rule)


if __name__ == "__main__":
    unittest.main()

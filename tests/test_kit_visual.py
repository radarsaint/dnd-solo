"""Visual bridge tests: player-safe facts, style retrieval, rotation, and canonical art lookup."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_rooms, kit_visual
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parent.parent
WATCHROOM = ROOT / "tests/fixtures/rooms/watchroom.json"


class KitVisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "kit.sqlite"
        self.runtime = Runtime(self.db)
        self.source = kit_rooms.load_room(WATCHROOM)
        self.runtime.initialize(self.source, self.source["starting_area"], room_path=WATCHROOM)

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_visual_brief_is_player_safe_and_does_not_change_world_revision(self):
        before = self.runtime.load()[0]
        brief = kit_visual.prepare_visual(self.runtime, "Draw what I see from here.")
        after = self.runtime.load()[0]
        self.assertEqual(before, after)
        self.assertEqual(brief["stage"], "visual_brief")
        self.assertEqual(brief["mode"], "story_vignette")
        self.assertEqual(brief["player_safe"]["location"], "Landing outside the watchroom")
        blob = json.dumps(brief, ensure_ascii=False).casefold()
        self.assertIn("iron door", blob)
        self.assertIn("four notes", blob)
        self.assertNotIn("sealed letter", blob)
        self.assertNotIn("who is expected tonight", blob)
        self.assertNotIn("keep strangers off the stair", blob)
        self.assertNotIn("guards from the gatehouse below", blob)

    def test_only_explicit_public_visual_descriptors_cross_boundary(self):
        self.runtime.close()
        source = copy.deepcopy(self.source)
        source["actors"]["warden"]["visual"] = {
            "public": ["Weathered human watchman.", "Brass-trimmed leather coat."],
            "dm_only": ["A black sun tattoo under his collar."],
        }
        self.runtime = Runtime(self.db)
        self.runtime.initialize(source, "watchroom")
        brief = kit_visual.prepare_visual(self.runtime, "Draw the watch warden as I see him.")
        blob = json.dumps(brief, ensure_ascii=False)
        self.assertIn("Weathered human watchman.", blob)
        self.assertIn("Brass-trimmed leather coat.", blob)
        self.assertNotIn("black sun tattoo", blob.casefold())

    def test_reference_rotation_penalizes_recent_overuse(self):
        first = kit_visual.prepare_visual(self.runtime, "Draw a magical character portrait.")
        second = kit_visual.prepare_visual(self.runtime, "Draw a magical character portrait.")
        first_ids = [r["id"] for r in first["style"]["references"]]
        second_ids = [r["id"] for r in second["style"]["references"]]
        self.assertTrue(first_ids)
        self.assertTrue(second_ids)
        self.assertNotEqual(first_ids, second_ids)

    def test_subject_bias_does_not_turn_anthro_reference_into_default_human_reference(self):
        brief = kit_visual.prepare_visual(self.runtime, "Draw a portrait of a human guard.")
        ids = [r["id"] for r in brief["style"]["references"]]
        self.assertNotIn("BFDM-CORE-08", ids)

    def test_visible_exact_entity_can_resolve_existing_canonical_art(self):
        self.runtime.close()
        source = copy.deepcopy(self.source)
        source["actors"]["warden"]["name"] = "Halaster Blackcloak"
        self.runtime = Runtime(self.db)
        self.runtime.initialize(source, "watchroom")
        brief = kit_visual.prepare_visual(self.runtime, "Draw Halaster Blackcloak.")
        candidates = brief["canonical_asset_candidates"]
        self.assertEqual([c["id"] for c in candidates], ["halaster-blackcloak"])
        self.assertTrue(all("exact entity" in c["rule"] for c in candidates))

    def test_explicit_mode_and_branch_override_inference(self):
        brief = kit_visual.prepare_visual(
            self.runtime, "Make this useful for the campaign.",
            mode="prop_study", branch="earthfall"
        )
        self.assertEqual(brief["mode"], "prop_study")
        self.assertEqual(brief["branch"], "earthfall")


class KitVisualInferenceTests(unittest.TestCase):
    def test_mode_inference(self):
        cases = {
            "Draw the town waterfront.": "exterior",
            "Make a portrait of the innkeeper.": "character_spotlight",
            "Show me the monster.": "creature_concept",
            "Illustrate this magic item.": "prop_study",
            "Make a subclass rules page.": "rulebook_page",
            "Create a player handout letter.": "handout",
            "Give me a chapter cover.": "splash",
            "Draw what I see.": "story_vignette",
        }
        for request, expected in cases.items():
            with self.subTest(request=request):
                self.assertEqual(kit_visual.infer_mode(request), expected)


if __name__ == "__main__":
    unittest.main()

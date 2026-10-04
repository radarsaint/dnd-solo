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

    def replace_runtime(self, source, area):
        self.runtime.close()
        if self.db.exists():
            self.db.unlink()
        self.runtime = Runtime(self.db)
        self.runtime.initialize(source, area)

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
        source = copy.deepcopy(self.source)
        source["actors"]["warden"]["visual"] = {
            "public": ["Weathered human watchman.", "Brass-trimmed leather coat."],
            "public_counts": {"arms": 2, "eyes": 2, "swords": 1},
            "dm_only": ["A black sun tattoo under his collar."],
        }
        self.replace_runtime(source, "watchroom")
        brief = kit_visual.prepare_visual(self.runtime, "Draw the watch warden as I see him.")
        blob = json.dumps(brief, ensure_ascii=False)
        self.assertIn("Weathered human watchman.", blob)
        self.assertIn("Brass-trimmed leather coat.", blob)
        self.assertNotIn("black sun tattoo", blob.casefold())
        self.assertEqual(brief["generation_contract"]["expected_counts"], {
            "actor:warden.arms": 2,
            "actor:warden.eyes": 2,
            "actor:warden.swords": 1,
        })

    def test_invalid_public_visual_counts_make_room_unmountable(self):
        source = copy.deepcopy(self.source)
        source["actors"]["warden"]["visual"] = {"public_counts": {"arms": "two"}}
        problems = kit_rooms.first_framing_problems(source)
        self.assertTrue(any("visual.public_counts" in problem for problem in problems))

    def test_request_does_not_promote_hidden_detail_to_visual_fact(self):
        brief = kit_visual.prepare_visual(
            self.runtime,
            "Draw the sealed letter and the guards waiting behind the door."
        )
        self.assertIn("sealed letter", brief["request"].casefold())
        safe = json.dumps(brief["player_safe"], ensure_ascii=False).casefold()
        self.assertNotIn("sealed letter", safe)
        self.assertNotIn("guards", safe)
        self.assertIn("player_safe is the factual ceiling",
                      brief["generation_contract"]["fact_rule"])

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
        source = copy.deepcopy(self.source)
        source["actors"]["warden"]["name"] = "Halaster Blackcloak"
        self.replace_runtime(source, "watchroom")
        brief = kit_visual.prepare_visual(self.runtime, "Draw Halaster Blackcloak.")
        candidates = brief["canonical_asset_candidates"]
        self.assertEqual([c["id"] for c in candidates], ["halaster-blackcloak"])
        self.assertTrue(all("exact entity" in c["rule"] for c in candidates))

    def test_visual_record_is_presentation_telemetry_not_world_state(self):
        brief = kit_visual.prepare_visual(self.runtime, "Draw what I see.")
        before = self.runtime.load()[0]
        recorded = kit_visual.record_visual(
            self.runtime, brief["visual_id"], "generated",
            result_id="gen-test-1", reference_mode="text_only",
            qa={"canon": "pass", "style": "needs review"},
            notes="Synthetic visual bridge test."
        )
        after = self.runtime.load()[0]
        self.assertEqual(before, after)
        self.assertEqual(recorded["status"], "generated")
        history = kit_visual.visual_history(self.runtime)
        self.assertEqual(history[0]["result_id"], "gen-test-1")
        self.assertEqual(history[0]["reference_mode"], "text_only")
        self.assertEqual(history[0]["qa"]["canon"], "pass")

    def test_visual_record_refuses_status_rewrite(self):
        brief = kit_visual.prepare_visual(self.runtime, "Draw what I see.")
        kit_visual.record_visual(self.runtime, brief["visual_id"], "generated")
        with self.assertRaisesRegex(Exception, "already recorded"):
            kit_visual.record_visual(self.runtime, brief["visual_id"], "failed")

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

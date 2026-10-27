"""Advisory judgments follow live state, not the player sentence.

Deterministic harness only. A RecordingModel is not a playtest, and a scripted
decision handed to KitChatBridge is not a ChatGPT turn.

The pin file is checked on every run. The live corpus checkout is a separate
test: it executes when BFDM_CORPUS or /tmp/bfdm-judgment holds the pinned JSONL,
and skipTest reports ``live corpus drift skipped`` when that checkout is absent.
Set BFDM_JUDGMENT_REQUIRED=1 to make that absence a failure. The cross-repo
workflow does. No paid API.
"""
import copy
import json
import os
import subprocess
import unittest
from pathlib import Path

from runtime import kit_claims, kit_combat, kit_judgment, kit_reactions, kit_rooms
from runtime.kit_agent import KitAgent, KitChatBridge, RoomAdjudicator, check_public_content, start_session
from runtime.state_context import BOOKKEEPING_EVENTS, COMMIT_APPENDED_EVENTS, InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel
from test_kit_story_brief import Base, Entering

NIK = json.loads((Path(__file__).parent / "fixtures/characters/nik.json").read_text())
NIK_PATH = Path(__file__).parent / "fixtures/characters/nik.json"
YARD = Path(__file__).parent / "fixtures/rooms/judgment_yard.json"
PIN = Path(__file__).parent / "fixtures/judgment/bfdm-bounded-judgment-pin.json"
AREA = "area_06c"
RESEARCH = ("BJ-001", "BJ-002", "BJ-003", "BJ-004", "BJ-005", "discord:",
            "Advisory historical", "746253583552479272", "Play the fight", "Decline")

OPENING_SPEECH = {"segments": [
    {"speaker": "Narrator", "text": (
        "A weathered wooden post stands in the middle of the yard, grey where seasons of rain have "
        "opened the grain, with a frayed rope knotted through an iron nail near the top and a scatter "
        "of pale wood chips at its foot. The chips are dry. Ants move among them.")},
    {"speaker": "Narrator", "text": (
        "The lane that leaves the yard is empty. No cart waits, no voice calls from beyond the corner, "
        "and the late light lies flat across packed dirt. The rope turns once on a thin breath of air "
        "and then hangs still against the post. Dust settles back into the ruts.")},
]}
LOOK_SPEECH = {"segments": [
    {"speaker": "Narrator", "text": (
        "Closer up the nail is rusted dark, and the rope fibres have bleached to straw where the sun "
        "hits them through the long afternoon. A split in the wood shows a paler core underneath.")},
    {"speaker": "Narrator", "text": (
        "Nothing else occupies the yard. The dirt holds a few boot prints that stop at the post and do "
        "not continue toward the lane, and a beetle crosses one of them without hurry.")},
]}


def corpus_root():
    """The bfdm-corpus checkout, if this environment has one. Never fetched."""
    candidates = []
    if os.environ.get("BFDM_CORPUS"):
        candidates.append(Path(os.environ["BFDM_CORPUS"]))
    candidates.append(Path("/tmp/bfdm-judgment"))
    for root in candidates:
        if (root / kit_judgment.CORPUS_PATH).is_file():
            return root
    return None


def sheet(hp, used):
    body = copy.deepcopy(NIK)
    body["hp"] = hp
    body["slots"] = {level: {"max": count, "used": count if used else 0}
                     for level, count in {"1": 4, "2": 3, "3": 2}.items()}
    return body


def room(**judgment):
    source = json.loads(FIXTURE.read_text())
    source["_judgment"] = {"encounters": [], "constraints": [], "damage": [],
                           "unknown_to": [], "settled": []}
    source["_judgment"].update(judgment)
    return source


def plan_for(packet, **update):
    plan = RecordingModel().plan(packet["input"]["private"])
    plan.update({"move": "world_description", "table_presence": "quiet", "focus_actor": "none", **update})
    plan["improv_read"].update(actor_ref="none", actor_basis="none")
    return plan


def judgment_event(open_ids=(), standing=(), unscheduled=()):
    return {"type": "judgment_state",
            "state": {"open": list(open_ids), "standing": list(standing), "unscheduled": list(unscheduled)},
            "evidence": "The host recorded the live judgment conditions."}


ENCOUNTER = {"id": "prepared_boss", "area": AREA, "prepared": True,
             "assumes": {"min_hp": 16, "min_slots_remaining": 1}}


class StateSelects(unittest.TestCase):
    def test_a_sentence_never_selects_on_its_own(self):
        bare = json.loads(FIXTURE.read_text())
        state = {"area": AREA, "player_sheet": copy.deepcopy(NIK)}
        for line in (
            "I search the spare bedroom for clues",
            "the boss is depleted and out of spell slots",
            "I dig survivors out of the wrecked shop",
            'He said "give me a spare bedroom"',
            "I do not want to clear the rubble",
            "We're topped up. Run the preplanned fight.",
        ):
            self.assertIsNone(kit_judgment.select(bare, state, "social"), line)

    def test_no_sheet_does_not_guess(self):
        source = room(encounters=[ENCOUNTER])
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "social"))

    def test_ambiguous_counts_do_not_guess(self):
        source = room(encounters=[ENCOUNTER])
        assumes = ENCOUNTER["assumes"]
        coded = sheet(4, used=True)
        self.assertIsNone(kit_judgment.party_ready({"player_sheet": coded}, assumes))
        self.assertIsNone(kit_judgment.select(source, {"area": AREA, "player_sheet": coded}, "social"))
        fight = {"player_sheet": copy.deepcopy(NIK), "combat": {"status": "running", "hp": {}, "order": []}}
        self.assertIsNone(kit_judgment.party_ready(fight, assumes))
        stale = kit_reactions.build(NIK)
        stale["sheet"] = "not-this-sheet"
        mismatched = {"player_sheet": copy.deepcopy(NIK), "pc_resources": stale}
        self.assertIsNone(kit_judgment.party_ready(mismatched, assumes))

    def test_spare_bedroom_wording_does_not_open_an_exception(self):
        source = room(constraints=[{"id": "housing", "area": AREA, "exception_open": False}])
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "look"))

    def test_a_static_exception_flag_does_not_keep_firing(self):
        source = room(constraints=[{"id": "housing", "area": AREA, "exception_open": True}])
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "social"))
        opened = {"area": AREA, "judgment": {"open": ["housing"], "standing": [], "unscheduled": []}}
        card = kit_judgment.select(source, opened, "social")["applied"][0]
        self.assertEqual(card["id"], "BJ-002")
        self.assertNotIn("Decline", card["advisory"])
        self.assertIn("player still chooses", card["advisory"])
        self.assertNotIn("room data", card["advisory"])
        self.assertIn("Live state", card["advisory"])
        closed = {"area": AREA, "judgment": {"open": [], "standing": [], "unscheduled": []}}
        self.assertIsNone(kit_judgment.select(source, closed, "social"))
        self.assertIs(source["_judgment"]["constraints"][0]["exception_open"], True)

    def test_repair_follows_persisted_unscheduled_damage_not_the_file_flag(self):
        source = room(damage=[{"id": "shop", "area": AREA, "scheduled": False}])
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "physical_act"))
        live = {"area": AREA, "judgment": {"open": [], "standing": [], "unscheduled": ["shop"]}}
        self.assertIsNone(kit_judgment.select(source, live, "look"))
        card = kit_judgment.select(source, live, "physical_act")["applied"][0]
        self.assertEqual(card["id"], "BJ-001")
        self.assertIn("Do not write the outcome", card["advisory"])
        self.assertNotIn("room data", card["advisory"])
        self.assertNotIn("healing thing", json.dumps(card))
        done = {"area": AREA, "judgment": {"open": [], "standing": [], "unscheduled": []}}
        self.assertIsNone(kit_judgment.select(source, done, "physical_act"))
        self.assertIs(source["_judgment"]["damage"][0]["scheduled"], False)

    def test_a_holder_is_not_told_the_fact_is_unknown(self):
        source = room(unknown_to=[{"actor": "uktarl", "claim": "portfolio"}])
        source["claims"] = {"portfolio": {"holders": {"uktarl": "knows"},
                                 "text": "The vault word is silverlane"}}
        state = {"area": AREA, "actors": {"uktarl": {"location": AREA}}}
        self.assertIsNone(kit_judgment.select(source, state, "social"))
        # Listed unaware is the engine's ignorant band. A missing holders entry is not.
        source["claims"]["portfolio"]["holders"] = {"clerk": "knows", "uktarl": "unaware"}
        card = kit_judgment.select(source, state, "social")["applied"][0]
        self.assertEqual(card["id"], "BJ-005")
        self.assertIn("not a play transcript", card["advisory"])
        self.assertNotIn("silverlane", json.dumps(card))

    def test_an_unlisted_present_npc_with_engine_band_knows_is_not_ignorant(self):
        """BJ-005 follows kit_claims.npc_band. Absence from a nonempty holders map is not ignorance.

        Passive Insight 10 against DC 10 is the engine band ``knows``. A granted
        capability is ``knows`` even when the passive would fall short. Neither emits
        present_npc_does_not_hold_claim.
        """
        source = room(unknown_to=[{"actor": "uktarl", "claim": "portfolio"}])
        abilities = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        actors = {"uktarl": {"location": AREA, "stats": {
            "abilities": abilities, "skills": {}, "proficiency_bonus": 2}}}
        claim = {"holders": {"clerk": "knows"}, "dc": 10, "npc_check": "insight",
                 "text": "The vault word is silverlane"}
        source["claims"] = {"portfolio": claim}
        state = {"area": AREA, "actors": actors}
        level = kit_claims.current_floor_level(source, AREA)
        self.assertEqual(kit_claims.npc_band(claim, "uktarl", actors, AREA, level), "knows")
        self.assertIsNone(kit_judgment.select(source, state, "social"))

        granted = {"holders": {"clerk": "knows"}, "dc": 30, "npc_check": "insight",
                   "granted_by": ["read_thoughts"], "text": "The vault word is silverlane"}
        source["claims"] = {"portfolio": granted}
        actors["uktarl"]["stats"]["special"] = ["read_thoughts"]
        self.assertEqual(kit_claims.npc_band(granted, "uktarl", actors, AREA, level), "knows")
        self.assertIsNone(kit_judgment.select(source, state, "social"))

    def test_standing_is_live_state_and_a_sentence_does_not_erase_it(self):
        source = room(settled=[{"id": "resurrection", "area": AREA, "standing": True}])
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "social"))
        stood = {"area": AREA, "judgment": {"open": [], "standing": ["resurrection"], "unscheduled": []}}
        card = kit_judgment.select(source, stood, "social")["applied"][0]
        self.assertEqual(card["id"], "BJ-003")
        self.assertIn("does not erase", card["does_not"])
        self.assertNotIn("room data", card["advisory"])
        self.assertIn("Live state", card["advisory"])
        ended = {"area": AREA, "judgment": {"open": [], "standing": [], "unscheduled": []}}
        self.assertIsNone(kit_judgment.select(source, ended, "social"))
        self.assertIs(source["_judgment"]["settled"][0]["standing"], True)

    def test_prepared_is_static_and_resources_are_not(self):
        """The encounter stays prepared. The card is meets, below, or omitted."""
        source = room(encounters=[ENCOUNTER])
        nik = copy.deepcopy(NIK)
        met = {"area": AREA, "player_sheet": nik}
        self.assertIs(kit_judgment.party_ready(met, ENCOUNTER["assumes"]), True)
        self.assertEqual(kit_judgment.select(source, met, "social")["applied"][0]["relevance"],
                         "party_meets_encounter_assumption")
        hurt = {"area": AREA, "player_sheet": nik, "combat": {"pc_damage": 20}}
        self.assertEqual(nik["hp"] - 20, 12)
        self.assertIs(kit_judgment.party_ready(hurt, ENCOUNTER["assumes"]), False)
        held = kit_reactions.build(nik)
        for slot in held["slots"].values():
            slot["used"] = slot["max"]
        spent = {"area": AREA, "player_sheet": nik, "pc_resources": held}
        self.assertIs(kit_judgment.party_ready(spent, ENCOUNTER["assumes"]), False)
        self.assertEqual(nik["hp"], 32)
        self.assertEqual(nik["slots"], {"1": 4, "2": 3, "3": 2})

    def test_solo_scope_ignores_any_other_bodies(self):
        nik = copy.deepcopy(NIK)
        assumes = ENCOUNTER["assumes"]
        alone = {"player_sheet": nik}
        crowded = {"player_sheet": nik, "party": [{"hp": 1}, {"hp": 1}, {"hp": 1}]}
        self.assertIs(kit_judgment.party_ready(alone, assumes), True)
        self.assertEqual(kit_judgment.party_ready(alone, assumes), kit_judgment.party_ready(crowded, assumes))

    def test_pinned_record_validation_does_not_skip(self):
        pin = json.loads(PIN.read_text())
        self.assertEqual(pin["repo"], kit_judgment.CORPUS_REPO)
        self.assertEqual(pin["commit"], kit_judgment.CORPUS_COMMIT)
        self.assertEqual(pin["path"], kit_judgment.CORPUS_PATH)
        self.assertEqual(set(pin["records"]), set(kit_judgment.RECORDS))
        for record_id, card in kit_judgment.RECORDS.items():
            pinned = pin["records"][record_id]
            self.assertEqual(set(pinned), {"status", "evidence"})
            self.assertEqual(pinned["status"], card["status"])
            self.assertEqual(pinned["evidence"], card["evidence"])
            text = json.dumps(card)
            self.assertNotIn("Play the fight", text)
            self.assertNotIn("Decline", text)
        self.assertNotIn("advisory", PIN.read_text())

    def test_live_corpus_drift_matches_the_pin(self):
        root = corpus_root()
        if root is None:
            if os.environ.get("BFDM_JUDGMENT_REQUIRED"):
                self.fail("live corpus drift required: no checkout at $BFDM_CORPUS or /tmp/bfdm-judgment")
            self.skipTest("live corpus drift skipped: no checkout at $BFDM_CORPUS or /tmp/bfdm-judgment")
        pin = json.loads(PIN.read_text())
        jsonl = (root / kit_judgment.CORPUS_PATH).read_text()
        self.assertEqual(kit_judgment.drift_against(jsonl), [])
        sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        self.assertEqual(sha, pin["commit"])
        rows = {json.loads(line)["id"]: json.loads(line) for line in jsonl.splitlines() if line.strip()}
        for record_id, pinned in pin["records"].items():
            self.assertEqual(rows[record_id]["status"], pinned["status"])
            self.assertEqual(list(rows[record_id]["evidence"]), pinned["evidence"])


class SameSheet(Base):
    def test_the_same_sheet_before_and_after_damage_and_spent_slots(self):
        nik = copy.deepcopy(NIK)
        self.start(room(encounters=[ENCOUNTER]))
        self.runtime.set_player_sheet(nik)
        assumes = ENCOUNTER["assumes"]
        before = self.runtime.load()[1]
        self.assertEqual(before["player_sheet"]["hp"], 32)
        self.assertEqual(before["player_sheet"]["slots"], nik["slots"])
        self.assertIs(kit_judgment.party_ready(before, assumes), True)
        self.assertEqual(kit_judgment.select(self.runtime.source(), before, "social")["applied"][0]["relevance"],
                         "party_meets_encounter_assumption")

        revision, state = self.runtime.load()
        spent_slots = copy.deepcopy(state["pc_resources"])
        spent = 0
        while True:
            spent_slots, level = kit_reactions.spend_slot(spent_slots, 1)
            if level is None:
                break
            spent += 1
        self.assertEqual(spent, 9)
        self.runtime.commit("spend", revision, [{
            "type": "pc_resources", "resources": spent_slots,
            "evidence": "Spell slots spent in the fight were recorded."}])
        after_slots = self.runtime.load()[1]
        self.assertEqual(after_slots["player_sheet"]["hp"], 32)
        self.assertEqual(after_slots["player_sheet"]["slots"], {"1": 4, "2": 3, "3": 2})
        self.assertEqual(sum(slot["max"] - slot["used"]
                             for slot in after_slots["pc_resources"]["slots"].values()), 0)
        self.assertIs(kit_judgment.party_ready(after_slots, assumes), False)
        self.assertEqual(kit_judgment.select(self.runtime.source(), after_slots, "social")["applied"][0]["relevance"],
                         "party_below_encounter_assumption")

        revision, state = self.runtime.load()
        restored = kit_reactions.rest(state["pc_resources"], state["player_sheet"], "long")
        working = copy.deepcopy(state)
        working["pc_resources"] = restored
        working["combat"] = {"status": "running", "hp": {}, "order": [], "pc_damage": 0}
        fight = kit_combat.Fight(self.runtime.source(), working, revision, "a blow lands", lambda *args: None)
        self.assertEqual(fight.hurt_pc(20), [])
        self.assertEqual(fight.fight["pc_damage"], 20)
        self.runtime.commit("damage", revision, [
            {"type": "pc_resources", "resources": restored,
             "evidence": "The inventory was restored so the damage count can be read on its own."},
            {"type": "combat_state", "state": fight.fight,
             "evidence": "Damage taken in the fight was recorded."}])
        hurt = self.runtime.load()[1]
        self.assertEqual(sum(slot["max"] - slot["used"] for slot in hurt["pc_resources"]["slots"].values()), 9)
        self.assertEqual(hurt["player_sheet"]["hp"] - hurt["combat"]["pc_damage"], 12)
        self.assertIs(kit_judgment.party_ready(hurt, assumes), False)
        below = kit_judgment.select(self.runtime.source(), hurt, "social")["applied"][0]
        self.assertEqual(below["relevance"], "party_below_encounter_assumption")
        self.assertNotIn("Play the fight", below["advisory"])
        self.assertNotIn("room data", below["advisory"])
        self.assertEqual(nik["hp"], 32)
        self.assertEqual(nik["slots"], {"1": 4, "2": 3, "3": 2})

    def test_research_markers_stay_out_of_player_facing_text(self):
        with self.assertRaises(InvalidChange):
            check_public_content("A note reads discord:746253583552479272.", {}, "I look at the post.")
        with self.assertRaises(InvalidChange):
            check_public_content("Apply BJ-002 here.", {}, "I look at the post.")
        check_public_content("The post is weathered and the rope hangs still.", {}, "I look at the post.")
        check_public_content("You already said discord:746253583552479272.", {},
                             "discord:746253583552479272")


class SeedAndRetire(Base):
    def test_authored_flags_seed_once_and_a_later_event_retires_them(self):
        source = room(
            constraints=[{"id": "housing", "area": AREA, "exception_open": True}],
            settled=[{"id": "resurrection", "area": AREA, "standing": True}],
            damage=[{"id": "shop", "area": AREA, "scheduled": False}],
        )
        self.start(source)
        state = self.runtime.load()[1]
        self.assertEqual(state["judgment"],
                         {"open": ["housing"], "standing": ["resurrection"], "unscheduled": ["shop"]})
        self.assertIsNone(kit_judgment.select(source, {"area": AREA}, "physical_act"))
        seeded = kit_judgment.select(self.runtime.source(), state, "physical_act")
        self.assertEqual([card["id"] for card in seeded["applied"]], ["BJ-002", "BJ-003"])
        revision, state = self.runtime.load()
        turns_before = (state.get("room") or {}).get("turns_in")
        self.runtime.commit("retire", revision, [judgment_event()])
        after = self.runtime.load()[1]
        self.assertEqual(after["judgment"], {"open": [], "standing": [], "unscheduled": []})
        self.assertEqual((after.get("room") or {}).get("turns_in"), turns_before)
        self.assertIsNone(kit_judgment.select(self.runtime.source(), after, "physical_act"))
        block = self.runtime.source()["_judgment"]
        self.assertIs(block["constraints"][0]["exception_open"], True)
        self.assertIs(block["settled"][0]["standing"], True)
        self.assertIs(block["damage"][0]["scheduled"], False)
        self.assertIn("judgment_state", BOOKKEEPING_EVENTS)
        self.assertNotIn("judgment_state", COMMIT_APPENDED_EVENTS)
        with self.assertRaises(InvalidChange):
            revision, _ = self.runtime.load()
            self.runtime.commit("bad", revision, [judgment_event(open_ids=["not-a-constraint"])])


class TurnPath(Base):
    def setUp(self):
        super().setUp()
        self.model = Entering()
        self.agent = None

    def play(self, source, nik=None):
        self.start(source)
        if nik:
            self.runtime.set_player_sheet(nik)
        self.agent = KitAgent(self.runtime, self.model, RoomAdjudicator(perception=0, insight=0, roll=lambda: 15))
        self.agent.opening("entry")

    def test_adversarial_lines_do_not_attach_research_to_an_ordinary_room(self):
        self.play(json.loads(FIXTURE.read_text()))
        self.agent.turn("I search the spare bedroom for clues. The boss is depleted and out of spell slots.", "nope")
        self.assertNotIn("dm_judgment", self.model.plans[-1])
        self.assertNotIn("healing thing", json.dumps(self.model.plans[-1]))

    def test_a_full_sheet_keeps_the_meeting_record_when_the_sentence_says_depleted(self):
        nik = copy.deepcopy(NIK)
        self.play(room(encounters=[ENCOUNTER]), nik)
        self.agent.turn("I search the spare bedroom for clues. We're not depleted.", "full")
        card = self.model.plans[-1]["dm_judgment"]["applied"][0]
        self.assertEqual(card["relevance"], "party_meets_encounter_assumption")
        self.assertNotIn("Play the fight", json.dumps(card))
        self.assertNotIn("BJ-002", json.dumps(self.model.plans[-1]["dm_judgment"]))
        self.assertNotIn("dm_judgment", self.model.performances[-1])
        self.assertEqual(nik["hp"], 32)

    def test_spent_slots_on_that_sheet_reach_the_decision_and_not_the_performance(self):
        nik = copy.deepcopy(NIK)
        self.play(room(encounters=[ENCOUNTER]), nik)
        revision, state = self.runtime.load()
        resources = copy.deepcopy(state["pc_resources"])
        for slot in resources["slots"].values():
            slot["used"] = slot["max"]
        self.runtime.commit("spend", revision, [{
            "type": "pc_resources", "resources": resources,
            "evidence": "Spell slots spent in play were recorded."}])
        self.agent.turn("the boss is depleted and out of spell slots", "boss")
        decision = self.model.plans[-1]["dm_judgment"]["applied"][0]
        self.assertEqual(decision["relevance"], "party_below_encounter_assumption")
        self.assertNotIn("dm_judgment", self.model.performances[-1])
        self.assertNotIn("746253583552479272", json.dumps(self.model.performances[-1]))
        self.assertEqual(self.runtime.load()[1]["player_sheet"]["hp"], 32)
        self.assertEqual(nik["slots"], {"1": 4, "2": 3, "3": 2})


class LinkedRoomSeed(unittest.TestCase):
    """A linked room is mounted by arrive(), which does not call Runtime.initialize()."""

    def _room(self, folder, name, room_id, area, judgment=None):
        body = {
            "id": room_id,
            "fixture_only": True,
            "starting_area": area,
            "areas": {area: {"name": area, "called": area}},
            "exits": {},
            "facts": {"stone": {"area": area, "visible": True, "text": "The stone is bare."}},
            "actors": {},
        }
        if judgment is not None:
            body["_judgment"] = judgment
        path = folder / name
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def test_a_first_arrival_seeds_judgment_and_a_revisit_keeps_the_archive(self):
        import tempfile
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        here = self._room(folder, "here.json", "synthetic-judgment-here", "hall")
        nxt = self._room(folder, "next.json", "synthetic-judgment-next", "yard", judgment={
            "constraints": [{"id": "post_rule", "area": "yard", "exception_open": True}],
            "settled": [{"id": "old_call", "area": "yard", "standing": True}],
            "damage": [{"id": "beam", "area": "yard", "scheduled": False}],
        })
        old = kit_rooms.load_room(here)
        state = {
            "area": "hall",
            "visited": ["hall"],
            "known_facts": [],
            "known_exits": [],
            "actors": {},
            "kit": {"episodes": [], "current_appraisal": None, "player_notes": []},
            "room": {"id": old["id"], "path": str(here), "turns_in": {}},
            "judgment": {"open": ["from-here"], "standing": [], "unscheduled": []},
        }
        new_source, arrived = kit_rooms.arrive(old, state, {"room": str(nxt), "area": "yard"})
        self.assertEqual(arrived["area"], "yard")
        self.assertEqual(arrived["judgment"], {
            "open": ["post_rule"], "standing": ["old_call"], "unscheduled": ["beam"]})
        self.assertEqual(arrived["rooms"][old["id"]]["state"]["judgment"]["open"], ["from-here"])
        packet = kit_judgment.select(new_source, arrived, "social")
        self.assertEqual([card["id"] for card in packet["applied"]], ["BJ-002", "BJ-003"])

        arrived["judgment"] = {"open": [], "standing": [], "unscheduled": []}
        back_source, back = kit_rooms.arrive(new_source, arrived, {"room": str(here), "area": "hall"})
        self.assertEqual(back["judgment"], {"open": ["from-here"], "standing": [], "unscheduled": []})
        again_source, again = kit_rooms.arrive(back_source, back, {"room": str(nxt), "area": "yard"})
        self.assertEqual(again["judgment"], {"open": [], "standing": [], "unscheduled": []})
        self.assertIsNone(kit_judgment.select(again_source, again, "physical_act"))
        block = again_source["_judgment"]
        self.assertIs(block["constraints"][0]["exception_open"], True)
        self.assertIs(block["settled"][0]["standing"], True)
        self.assertIs(block["damage"][0]["scheduled"], False)


class YardMount(unittest.TestCase):
    """File mount, then KitChatBridge prepare and complete. The decision here is scripted.
    That is the host path with no API key. It is not a model playing the yard."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "yard.sqlite"
        self.runtime = Runtime(self.db)
        self.addCleanup(self.runtime.close)

    def test_the_file_mount_keeps_the_annotation_through_prepare_and_complete(self):
        mounted = kit_rooms.load_room(YARD)
        self.assertEqual(mounted["_judgment"]["constraints"][0]["id"], "post_rule")
        self.assertTrue(mounted["_judgment"]["constraints"][0]["exception_open"])
        started = start_session(self.db, NIK_PATH, runtime=self.runtime, room=YARD)
        source = self.runtime.source()
        self.assertEqual(source["_judgment"], mounted["_judgment"])
        self.assertEqual(self.runtime.load()[1]["judgment"]["open"], ["post_rule"])
        private = started["prepared"]["input"]["private"]
        public = started["prepared"]["input"]["public"]
        self.assertNotIn("dm_judgment", private)
        self.assertNotIn("dm_judgment", public)
        self._assert_player_facing_clean(public, json.dumps(self.runtime.player_view()))
        bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))
        opened = bridge.complete(started["prepared"]["turn_id"], {
            "decision": plan_for(started["prepared"]), "performance": OPENING_SPEECH})
        self._assert_player_facing_clean(opened["spoken"])

        look = bridge.prepare("I look at the post.", "look", one_pass=True)
        packet = look["input"]["private"]["dm_judgment"]
        ids = [card["id"] for card in packet["applied"]]
        self.assertEqual(ids, ["BJ-002", "BJ-004"])
        self.assertEqual(packet["applied"][1]["relevance"], "party_meets_encounter_assumption")
        self.assertFalse(packet["binding"])
        self.assertNotIn("dm_judgment", look["input"]["public"])
        self._assert_player_facing_clean(look["input"]["public"], json.dumps(self.runtime.player_view()))
        looked = bridge.complete("look", {"decision": plan_for(look), "performance": LOOK_SPEECH})
        self._assert_player_facing_clean(looked["spoken"])

        meta = bridge.prepare("What are you reading from?", "meta", one_pass=True, table_talk=True)
        self.assertNotIn("dm_judgment", meta["input"]["private"])
        self._assert_player_facing_clean(meta["input"]["public"])
        bridge.abandon("meta")

        revision, _ = self.runtime.load()
        self.runtime.commit("close-exception", revision, [judgment_event()])
        self.assertIs(self.runtime.source()["_judgment"]["constraints"][0]["exception_open"], True)
        again = bridge.prepare("I look at the rope.", "rope", one_pass=True)
        ids = [card["id"] for card in again["input"]["private"]["dm_judgment"]["applied"]]
        self.assertEqual(ids, ["BJ-004"])
        self._assert_player_facing_clean(again["input"]["public"])
        bridge.abandon("rope")

    def _assert_player_facing_clean(self, *blobs):
        for blob in blobs:
            text = blob if isinstance(blob, str) else json.dumps(blob)
            for needle in RESEARCH:
                self.assertNotIn(needle, text, needle)


if __name__ == "__main__":
    unittest.main()

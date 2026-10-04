"""Player-safe visual briefs and BFDM style-reference retrieval for DM Kit.

This module never calls an image API. The runtime owns truth and secrecy; Kit/the host
uses the returned brief with ChatGPT's built-in image generation capability.
"""
import json
import re
import time
import uuid
from pathlib import Path

from .state_context import InvalidChange, require

ROOT = Path(__file__).resolve().parents[1]
STYLE_MANIFEST = ROOT / "assets/style/index.json"
ART_MANIFEST = ROOT / "assets/art/index.json"

MODES = (
    "character_spotlight",
    "creature_concept",
    "story_vignette",
    "prop_study",
    "exterior",
    "handout",
    "rulebook_page",
    "splash",
)

_MODE_RULES = (
    ("rulebook_page", re.compile(r"\b(rulebook|rules? page|class page|subclass page|spread|stat block|bestiary entry)\b", re.I)),
    ("handout", re.compile(r"\b(handout|letter|note|poster|ticket|contract|map handout|newspaper|clipping)\b", re.I)),
    ("prop_study", re.compile(r"\b(item|weapon|sword|gun|mask|bag|artifact|prop|lantern|amulet|ring|object)\b", re.I)),
    ("exterior", re.compile(r"\b(exterior|town|city|village|settlement|street|waterfront|building|castle|landscape)\b", re.I)),
    ("creature_concept", re.compile(r"\b(monster|creature|cryptid|beast|aberration|dragon|pet)\b", re.I)),
    ("character_spotlight", re.compile(r"\b(portrait|character|npc|villain|hero|person|man|woman|portrait of)\b", re.I)),
    ("splash", re.compile(r"\b(cover|splash|poster image|chapter card|title image)\b", re.I)),
)

_SUBJECT_TAGS = {
    "anthropomorphic": re.compile(r"\b(anthro|anthropomorphic|rabbit|hare|harengon|catfolk|tabaxi|raccoon|foxfolk|animal-headed)\b", re.I),
    "human_portrait": re.compile(r"\b(human|man|woman|person|people|bartender|guard|soldier|wizard|rogue|fighter)\b", re.I),
    "magic": re.compile(r"\b(magic|magical|spell|wizard|sorcer|warlock|arcane|divine|glow|glowing)\b", re.I),
    "horror": re.compile(r"\b(horror|occult|cryptid|curse|grotesque|nightmare|aberration|undead)\b", re.I),
    "item": re.compile(r"\b(item|weapon|mask|bag|artifact|prop|object|equipment|lantern|amulet|ring)\b", re.I),
    "settlement": re.compile(r"\b(town|city|village|settlement|street|waterfront|building|castle)\b", re.I),
    "rules": re.compile(r"\b(rule|rules|class|subclass|stat block|bestiary|mechanics|spread)\b", re.I),
}

CORE_STYLE = [
    "Concept hook first: make the subject's identity readable before texture.",
    "Use a strong authored silhouette and large readable shape masses.",
    "Keep dark visible drawing structure; do not smooth away all contour and construction energy.",
    "Concentrate finish, contrast, and color on one or two identity-bearing focal features.",
    "Use deliberate local color and selective glow rather than generic cinematic grading.",
    "Let secondary areas stay looser, softer, flatter, or partially unresolved.",
    "Avoid generic polished fantasy-concept-art sameness and slick AI symmetry.",
]

QA = [
    "canon: every depicted factual detail is supported by player_safe",
    "secrecy: no unrevealed creature, geometry, clue, identity, future event, or DM-only fact appears",
    "counts: discrete anatomy and equipment counts are correct",
    "identity: visible people, creatures, objects, and place remain recognizably themselves",
    "style: the result carries BFDM visual logic rather than generic fantasy polish",
    "reference_overfit: visual references guide decisions without importing their unrelated subject matter",
    "function: the image actually serves the requested table or prep use",
]


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _public_descriptors(value):
    """Only an explicit visual.public field is eligible for the player-safe brief."""
    if not isinstance(value, dict):
        return []
    public = value.get("public")
    if isinstance(public, str):
        public = [public]
    if not isinstance(public, list):
        return []
    return [item.strip() for item in public if isinstance(item, str) and item.strip()][:16]


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).casefold()).strip()


def infer_mode(request):
    for mode, pattern in _MODE_RULES:
        if pattern.search(request):
            return mode
    # "show/draw what I see" during play is a scene by default, not a portrait.
    return "story_vignette"


def infer_branch(source):
    text = json.dumps(source.get("campaign_context") or {}, ensure_ascii=False).casefold()
    text += " " + str(source.get("id") or "").casefold()
    if "earthfall" in text:
        return "earthfall"
    if "roanoke" in text or "empire city" in text:
        return "roanoke"
    if "arcania" in text:
        return "arcania"
    return "core"


def subject_tags(request):
    return {tag for tag, pattern in _SUBJECT_TAGS.items() if pattern.search(request)}


def _ensure_visual_table(runtime):
    runtime.db.execute("""
        CREATE TABLE IF NOT EXISTS kit_visual_runs (
            seq INTEGER PRIMARY KEY,
            visual_id TEXT NOT NULL UNIQUE,
            created_at REAL NOT NULL,
            revision INTEGER NOT NULL,
            request TEXT NOT NULL,
            mode TEXT NOT NULL,
            branch TEXT NOT NULL,
            reference_ids TEXT NOT NULL
        )
    """)
    runtime.db.commit()


def recent_reference_ids(runtime, limit=6):
    _ensure_visual_table(runtime)
    rows = runtime.db.execute(
        "SELECT reference_ids FROM kit_visual_runs ORDER BY seq DESC LIMIT ?", (int(limit),)
    ).fetchall()
    out = []
    for (body,) in rows:
        try:
            out.extend(json.loads(body))
        except (TypeError, ValueError):
            continue
    return out


def select_references(runtime, request, mode, branch, limit=3):
    manifest = _json(STYLE_MANIFEST)
    refs = manifest.get("references") or []
    if not refs:
        return []
    policy = manifest.get("policy") or {}
    window = int(policy.get("recent_usage_window") or 6)
    recent = recent_reference_ids(runtime, window)
    most_recent = set(recent[: int(policy.get("max_references") or 4)])
    tags = subject_tags(request)
    scored = []
    for ref in refs:
        modes = set(ref.get("asset_modes") or [])
        branches = set(ref.get("branches") or [])
        biases = set(ref.get("subject_bias") or [])
        avoid = set(ref.get("avoid_for") or [])
        score = 0
        if mode in modes:
            score += 10
        elif "story_vignette" in modes and mode in ("character_spotlight", "creature_concept", "exterior"):
            score += 2
        else:
            score -= 4
        if branch in branches:
            score += 4
        elif "core" in branches:
            score += 1
        score += 4 * len(tags & biases)
        score -= 12 * len(tags & avoid)
        if ref.get("strength") == "CORE":
            score += 1
        uses = recent.count(ref.get("id"))
        score -= int(policy.get("same_reference_recent_penalty") or 4) * uses
        if ref.get("id") in most_recent:
            score -= 2
        scored.append((score, ref.get("id") or "", ref))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen = [item[2] for item in scored if item[0] > -3][: max(1, min(int(limit), 4))]
    if not chosen:
        chosen = [item[2] for item in scored[: max(1, min(int(limit), 4))]]
    result = []
    for ref in chosen:
        path = ref.get("private_path")
        result.append({
            "id": ref.get("id"),
            "label": ref.get("label"),
            "strength": ref.get("strength"),
            "teaches": ref.get("teaches") or [],
            "lanes": ref.get("lanes") or [],
            "subject_bias": ref.get("subject_bias") or [],
            "sha256": ref.get("sha256"),
            "path": path,
            "available": bool(path and (ROOT / path).is_file()),
        })
    return result


def _visible_actor_visuals(source, state, public):
    visible_names = {_norm(a.get("name")) for a in public.get("actors") or []}
    result = []
    for key, actor in (source.get("actors") or {}).items():
        if actor.get("location") != state.get("area") or _norm(actor.get("name")) not in visible_names:
            continue
        entry = {"id": key, "name": actor.get("name"), "status": actor.get("status")}
        descriptors = _public_descriptors(actor.get("visual"))
        if descriptors:
            entry["visual"] = descriptors
        visual = actor.get("visual") if isinstance(actor.get("visual"), dict) else {}
        counts = visual.get("public_counts")
        if isinstance(counts, dict):
            entry["counts"] = {str(name): int(value) for name, value in counts.items()
                               if isinstance(name, str) and type(value) is int and value >= 0}
        art_id = visual.get("public_art_id")
        if isinstance(art_id, str) and art_id.strip():
            entry["public_art_id"] = art_id.strip()
        result.append(entry)
    return result


def _canonical_candidates(actors):
    manifest = _json(ART_MANIFEST)
    entities = manifest.get("entities") or []
    by_name = {_norm(item.get("name")): item for item in entities}
    by_id = {str(item.get("id")): item for item in entities}
    found = []
    seen = set()
    for actor in actors:
        item = None
        if actor.get("public_art_id"):
            item = by_id.get(actor["public_art_id"])
        if item is None:
            item = by_name.get(_norm(actor.get("name")))
        if not item or item.get("id") in seen:
            continue
        seen.add(item.get("id"))
        path = item.get("path")
        found.append({
            "id": item.get("id"), "name": item.get("name"), "role": item.get("role"),
            "path": path, "available": bool(path and (ROOT / path).is_file()),
            "rule": "Use only because this exact entity is currently player-visible. Existing art remains subordinate to current state.",
        })
    return found


def _safe_scene(runtime, request):
    revision, state = runtime.load()
    source = runtime.source()
    public = runtime.player_view()
    area = (source.get("areas") or {}).get(state.get("area")) or {}
    actors = _visible_actor_visuals(source, state, public)
    player_safe = {
        "location": public.get("area"),
        "known_facts_here": list(public.get("known_facts_here") or []),
        "known_exits": [
            {"description": e.get("description"), "known_destination": e.get("known_destination")}
            for e in (public.get("exits") or [])
        ],
        "visible_actors": actors,
    }
    area_visual = _public_descriptors(area.get("visual"))
    if area_visual:
        player_safe["location_visual"] = area_visual
    known_fact_text = set(public.get("known_facts_here") or [])
    fact_visuals = []
    for key, fact in (source.get("facts") or {}).items():
        if fact.get("text") in known_fact_text:
            desc = _public_descriptors(fact.get("visual"))
            if desc:
                fact_visuals.append({"id": key, "visual": desc})
    if fact_visuals:
        player_safe["fact_visuals"] = fact_visuals
    if public.get("established_details"):
        player_safe["established_details"] = public["established_details"]
    lowered = request.casefold()
    if public.get("your_character") and re.search(r"\b(me|my character|my pc|myself|our party|us)\b", lowered):
        player_safe["your_character"] = public["your_character"]
    return revision, source, player_safe, actors


def prepare_visual(runtime, request, mode="auto", branch="auto", record=True):
    require(isinstance(request, str) and 0 < len(request.strip()) <= 1000,
            "Visual request must be 1–1000 characters")
    if mode == "auto":
        mode = infer_mode(request)
    require(mode in MODES, "Unknown visual mode: " + str(mode))
    revision, source, player_safe, actors = _safe_scene(runtime, request)
    if branch == "auto":
        branch = infer_branch(source)
    require(isinstance(branch, str) and bool(branch.strip()), "Visual branch required")
    refs = select_references(runtime, request, mode, branch)
    visual_id = "visual-" + uuid.uuid4().hex[:12]
    result = {
        "stage": "visual_brief",
        "visual_id": visual_id,
        "revision": revision,
        "request": request.strip(),
        "mode": mode,
        "branch": branch,
        "player_safe": player_safe,
        "canonical_asset_candidates": _canonical_candidates(actors),
        "style": {
            "entrypoint": "docs/architecture/KIT_VISUAL_STYLE_SPEC.md",
            "art_bible": "docs/architecture/BFDM_VISUAL_ART_BIBLE.md",
            "reference_manifest": "assets/style/index.json",
            "references": refs,
            "core_instructions": CORE_STYLE,
        },
        "generation_contract": {
            "fact_rule": "Depict factual content only from player_safe plus the user's explicit request when it does not contradict established state.",
            "expected_counts": {
                f"actor:{actor['id']}.{name}": value
                for actor in actors for name, value in (actor.get("counts") or {}).items()
            },
            "style_freedom": "Kit may choose composition, framing, lighting, brush treatment, and nonfactual atmosphere.",
            "must_not_invent": [
                "unrevealed creatures or NPCs",
                "secret doors or unrevealed geometry",
                "hidden identities, clues, motives, or future events",
                "unsupported injuries, transformations, equipment, anatomy, or possessions",
            ],
            "reference_rule": "Use references for visual decisions, never as evidence that their subject matter belongs in this scene.",
            "api_rule": "Use ChatGPT's built-in image generation capability. Do not call a paid model API from Python.",
            "qa": QA,
        },
        "next_step": (
            "Kit: decide whether an available exact canonical asset already answers the request. "
            "Otherwise generate from player_safe plus the style block. Inspect the returned image "
            "against generation_contract.qa; repair/regenerate factual, anatomy, secrecy, or style failures before showing it."
        ),
    }
    if record:
        _ensure_visual_table(runtime)
        with runtime.db:
            runtime.db.execute(
                "INSERT INTO kit_visual_runs(visual_id,created_at,revision,request,mode,branch,reference_ids) "
                "VALUES(?,?,?,?,?,?,?)",
                (visual_id, time.time(), revision, request.strip(), mode, branch,
                 json.dumps([r["id"] for r in refs], separators=(",", ":"))),
            )
    return result

"""Deterministic BFDM visual-reference selection for DM Kit.

This chooses reference metadata only. It never treats reference art as campaign
truth and never opens or reveals private reference bytes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .state_context import PROJECT_ROOT, require

INDEX = PROJECT_ROOT / "style/BFDM_REFERENCE_INDEX.json"

MODE_TYPES = {
    "scene_vignette": ("scene", "interior", "exterior"),
    "character_spotlight": ("character", "portrait"),
    "creature_concept": ("creature",),
    "prop_study": ("prop", "item"),
    "exterior": ("exterior", "location"),
    "interior": ("interior", "scene"),
    "handout": ("handout", "rulebook"),
    "rulebook_spread": ("rulebook", "handout"),
    "cover_splash": ("splash", "character", "creature", "exterior"),
}

REQUEST_CUES = {
    "horror": ("horror", "creepy", "occult", "dark", "nightmare", "cryptid", "grotesque"),
    "graphic_dark": ("poster", "black", "neon", "graphic", "silhouette"),
    "bright_storybook": ("storybook", "bright", "whimsical", "magical", "luminous"),
    "page_design": ("page", "spread", "rules", "handout", "subclass", "class", "stat block"),
    "architecture": ("town", "city", "building", "street", "waterfront", "exterior", "architecture"),
    "prop_personality": ("item", "prop", "bag", "weapon", "mask", "lantern", "artifact"),
    "face_priority": ("portrait", "face", "headshot"),
    "vehicle_silhouette": ("ship", "boat", "vehicle", "wagon"),
    "hybrid_creature": ("hybrid", "chimera", "animal", "creature", "monster"),
}


def load_index(path=INDEX):
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    require(body.get("schema") == "bfdm_visual_reference_index_v1",
            "Invalid BFDM reference index")
    refs = body.get("references")
    require(isinstance(refs, list) and refs, "BFDM reference index is empty")
    return refs


def _words(text):
    return set(re.findall(r"[a-z0-9_]+", (text or "").casefold()))


def _requested_traits(request):
    text = (request or "").casefold()
    return {
        trait for trait, cues in REQUEST_CUES.items()
        if any(cue in text for cue in cues)
    }


def score_reference(ref, mode, request, branch="core", recent_reference_ids=()):
    types = set(MODE_TYPES.get(mode, ()))
    asset_types = set(ref.get("asset_types") or ())
    teaches = set(ref.get("teaches") or ())
    lanes = set(ref.get("lanes") or ())
    branches = set(ref.get("branches") or ())
    traits = _requested_traits(request)

    score = 0
    score += 8 * len(types & asset_types)
    score += 4 * len(traits & (teaches | lanes))
    score += 3 if branch in branches else 0
    score += 2 if ref.get("strength") == "CORE" else 1 if ref.get("strength") == "GOOD" else 0

    # Strong recency penalty: an equally useful alternate should rotate in.
    if ref.get("id") in set(recent_reference_ids or ()):
        score -= 7

    # Request words can match tags directly, but this is weaker than asset-type fit.
    request_words = _words(request)
    score += min(3, len(request_words & (asset_types | teaches | lanes | set(ref.get("subject_bias") or ()))))
    return score


def select_references(mode, request, branch="core", recent_reference_ids=(), limit=3, path=INDEX):
    require(type(limit) is int and 1 <= limit <= 4, "Reference limit must be 1-4")
    refs = load_index(path)
    ranked = sorted(
        refs,
        key=lambda ref: (
            score_reference(ref, mode, request, branch, recent_reference_ids),
            1 if ref.get("strength") == "CORE" else 0,
            ref.get("id", ""),
        ),
        reverse=True,
    )

    selected = []
    families = set()
    for ref in ranked:
        score = score_reference(ref, mode, request, branch, recent_reference_ids)
        if score <= 0:
            continue
        family = ref.get("subject_family")
        # Prefer breadth. Only repeat a subject family when we cannot fill the set otherwise.
        if family and family in families:
            continue
        selected.append({
            "id": ref["id"],
            "pack_file": ref["pack_file"],
            "hydrated_path": "style/private_refs/" + ref["pack_file"],
            "strength": ref.get("strength"),
            "teaches": ref.get("teaches") or [],
            "lanes": ref.get("lanes") or [],
            "score": score,
        })
        if family:
            families.add(family)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        used = {item["id"] for item in selected}
        for ref in ranked:
            if ref["id"] in used:
                continue
            score = score_reference(ref, mode, request, branch, recent_reference_ids)
            if score <= 0:
                continue
            selected.append({
                "id": ref["id"],
                "pack_file": ref["pack_file"],
                "hydrated_path": "style/private_refs/" + ref["pack_file"],
                "strength": ref.get("strength"),
                "teaches": ref.get("teaches") or [],
                "lanes": ref.get("lanes") or [],
                "score": score,
            })
            if len(selected) >= limit:
                break
    return selected

"""Player-safe visual briefs for DM Kit.

This module does not generate images. It converts the current runtime state into a
bounded brief that a chat-hosted Kit can safely hand to the host model's image tool.

The runtime owns what is true and what has been revealed. Kit owns art direction.
"""
from __future__ import annotations

from copy import deepcopy

from .state_context import InvalidChange, require


VISUAL_MODES = (
    "scene_vignette",
    "character_spotlight",
    "creature_concept",
    "prop_study",
    "exterior",
    "interior",
    "handout",
    "rulebook_spread",
    "cover_splash",
)

MODE_ALIASES = {
    "scene": "scene_vignette",
    "vignette": "scene_vignette",
    "character": "character_spotlight",
    "portrait": "character_spotlight",
    "creature": "creature_concept",
    "monster": "creature_concept",
    "prop": "prop_study",
    "item": "prop_study",
    "location": "interior",
    "room": "interior",
    "outside": "exterior",
    "cover": "cover_splash",
    "splash": "cover_splash",
    "page": "rulebook_spread",
}


def normalize_mode(mode):
    if mode is None:
        return "scene_vignette"
    value = str(mode).strip().casefold().replace("-", "_").replace(" ", "_")
    value = MODE_ALIASES.get(value, value)
    require(value in VISUAL_MODES, "Unknown visual mode")
    return value


def _safe_subjects(player_view):
    """Only subject records already present in Runtime.player_view()."""
    return [
        {
            "name": actor.get("name"),
            "status": actor.get("status"),
        }
        for actor in (player_view.get("actors") or [])
        if actor.get("name")
    ]


def build_visual_brief(runtime, request, mode=None):
    """Return a host-facing, player-safe visual brief without changing game state.

    No source actor cards, unrevealed facts, hidden geometry, claims, agendas, or
    DM-only campaign context are copied into this packet.
    """
    require(isinstance(request, str) and 0 < len(request.strip()) <= 1000,
            "Visual request must be 1-1000 characters")

    revision, state = runtime.load()
    player_view = deepcopy(runtime.player_view())
    visual_mode = normalize_mode(mode)

    brief = {
        "schema": "kit_visual_brief_v1",
        "revision": revision,
        "request": request.strip(),
        "mode": visual_mode,
        "scene": {
            "area": player_view.get("area"),
            "scene_id": state.get("scene_id"),
            "elapsed_seconds": player_view.get("elapsed_seconds"),
        },
        "player_safe_facts": {
            "known_facts_here": player_view.get("known_facts_here") or [],
            "visible_subjects": _safe_subjects(player_view),
            "known_exits": player_view.get("exits") or [],
            **({"your_character": player_view["your_character"]}
               if player_view.get("your_character") else {}),
        },
        "style": {
            "house_style": "docs/architecture/KIT_VISUAL_STYLE_SPEC.md",
            "art_bible": "docs/architecture/BFDM_VISUAL_ART_BIBLE.md",
            "reference_guide": "docs/architecture/BFDM_VISUAL_REFERENCE_GUIDE.md",
            "reference_selection_rule": (
                "Choose a small, relevant and varied BFDM reference set for this asset class. "
                "Do not repeatedly default to one mascot, one character, or one campaign image. "
                "Transfer visual decisions, not the depicted subject."
            ),
        },
        "generation_rules": [
            "Treat this packet as the complete factual ceiling for the generated depiction.",
            "Do not add an identity, creature, object, injury, door, clue, or environmental fact "
            "merely because it would make a better picture.",
            "Do not depict hidden or unrevealed information.",
            "If the request needs a fact this packet does not contain, omit that detail rather "
            "than guessing it.",
            "Generated imagery is presentation and does not create canon.",
        ],
        "qa": [
            "canon",
            "reveal_safety",
            "anatomy_and_object_counts",
            "identity",
            "BFDM_style_strength",
            "reference_overfit",
            "asset_function",
        ],
        "existing_asset_resolution": {
            "status": "not_implemented",
            "rule": (
                "Before generation, the host should resolve an existing canonical visual asset "
                "when one is available and reveal-safe. Do not regenerate canonical art by default."
            ),
        },
    }
    return brief


def validate_visual_brief(brief):
    """Small structural validator for host/tests."""
    require(isinstance(brief, dict) and brief.get("schema") == "kit_visual_brief_v1",
            "Invalid visual brief")
    require(brief.get("mode") in VISUAL_MODES, "Invalid visual mode")
    facts = brief.get("player_safe_facts")
    require(isinstance(facts, dict), "Missing player-safe facts")
    require(isinstance(facts.get("known_facts_here"), list), "Invalid known facts")
    require(isinstance(facts.get("visible_subjects"), list), "Invalid visible subjects")
    require(isinstance(facts.get("known_exits"), list), "Invalid known exits")
    return brief

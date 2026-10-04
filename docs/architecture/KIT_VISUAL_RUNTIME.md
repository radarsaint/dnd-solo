# DM Kit Visual Runtime

**Status:** v0.1 test path  
**Goal:** Let a chat-hosted Kit create new campaign art without bypassing runtime truth, reveal safety, or the BFDM visual language.

This is specifically for **DM Kit**. It is not a generic art-production pipeline.

## Boundary

The Python runtime does **not** call an image API.

The runtime owns:
- current game truth;
- what the player has learned;
- which actors and exits are currently visible;
- the player-safe ceiling for a depiction.

Kit/the host model owns:
- whether new art is useful;
- asset mode;
- BFDM art direction;
- reference selection;
- image generation;
- visual QA.

Generated art is presentation. It does not create canon.

## Live command

During a running game, when the player asks for an image of the current scene or a visible subject:

```sh
python3 -m runtime.kit_agent visual \
  --db kit.sqlite \
  --request "Draw what I can see in front of me." \
  --visual-mode scene_vignette
```

`--visual-mode` is optional. The default is `scene_vignette`.

Supported modes:

- `scene_vignette`
- `character_spotlight`
- `creature_concept`
- `prop_study`
- `exterior`
- `interior`
- `handout`
- `rulebook_spread`
- `cover_splash`

This command does not advance time, adjudicate an action, or change game state.

## What the command returns

The packet is `kit_visual_brief_v1`.

It contains only runtime-derived player-safe material:

- current visible area name;
- current scene id and elapsed time;
- facts already known here;
- actors already present in the player view;
- exits already present in the player view;
- the player character's public sheet/state when available;
- references to Kit's visual-style documents;
- generation and QA constraints.

It deliberately does **not** include:

- source actor cards;
- NPC motives or secrets;
- unrevealed facts;
- hidden geometry;
- claims;
- agendas;
- DM-only campaign context;
- private procedures.

The brief is the factual ceiling for a generation. If a desired visual detail is not in the brief and is not supplied explicitly by Brendon/player-safe context, Kit omits it rather than inventing it.

## Host procedure

When Kit receives a visual brief:

1. Read the exact user request.
2. Treat `player_safe_facts` as the factual ceiling.
3. Check whether existing canonical art should be revealed instead. Existing asset resolution is not automated in v0.1; consult the visual manifests when appropriate.
4. Select the requested/closest asset mode.
5. Load:
   - `docs/architecture/KIT_VISUAL_STYLE_SPEC.md`
   - `docs/architecture/BFDM_VISUAL_ART_BIBLE.md`
   - `docs/architecture/BFDM_VISUAL_REFERENCE_GUIDE.md`
6. Select a small and varied reference set appropriate to this asset. Transfer visual decisions, not the depicted subject.
7. Generate with the host's image tool.
8. Visually inspect the result before showing it.

## QA gate

Kit checks:

1. **Canon** — no contradiction with the brief.
2. **Reveal safety** — no unsupported hidden information.
3. **Anatomy/object count** — literal body-part/equipment count.
4. **Identity** — the requested subject still reads as itself.
5. **BFDM style strength** — the generator did not fall back to generic polished fantasy.
6. **Reference overfit** — reference subjects were not copied into the result merely because they were examples.
7. **Function** — the image actually serves its table purpose.

If a failure is visible, repair/regenerate the picture. Do not explain the mistake into canon.

## Reference diversity

A small group of strong references must not slowly become BFDM's accidental mascot set.

Reference selection should favor:

1. asset-type relevance;
2. visual problem relevance (line, silhouette, palette, page grammar, architecture, etc.);
3. campaign branch relevance;
4. composition relevance;
5. subject similarity when useful.

It should penalize:

- the same reference being used repeatedly when equivalent alternatives exist;
- the same named character appearing as style evidence for unrelated subjects;
- subject-specific anatomy transferring into unrelated generations;
- a reference chosen only because it is labeled CORE.

The visual corpus should grow beyond the current starter exemplar set.

## Existing versus generated art

Two visual systems remain separate:

### Canonical campaign asset lookup

`assets/maps/index.json`, `assets/art/index.json`, and `assets/handouts/index.json`

Question answered:

> Which existing image depicts this actual campaign thing, and may the player see it?

### BFDM style evidence

The art bible/reference material.

Question answered:

> Which Brendon works demonstrate the visual decisions useful for making this new image?

Style evidence never establishes an NPC's appearance, room contents, map geometry, or lore.

## Test target

A mounted Kit should be able to handle this sequence:

1. Start/resume a game normally.
2. Player asks: "Show me what I see."
3. Host runs `visual` instead of sending that line through ordinary turn adjudication.
4. Kit generates only from the visual brief.
5. The image reveals no hidden room facts.
6. Game revision is unchanged.
7. Player can continue the same scene normally afterward.

The initial unit tests live in `tests/test_kit_visual.py`.

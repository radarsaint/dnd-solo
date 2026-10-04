# Kit Visual Bridge

**Status:** v1 test slice on `feature/kit-visual-bridge-v1`  
**Goal:** Let a mounted DM Kit turn an explicit art request into a player-safe image-generation brief without moving world state, leaking DM information, or calling a paid model API.

## Boundary

The runtime decides **what may be depicted**.

Kit decides **how to depict it**.

ChatGPT's built-in image generator renders the picture.

The Python runtime never calls an image model.

```text
player/director art request
        |
        v
python3 -m runtime.kit_agent visual
        |
        v
player-safe visual brief
  - visible location
  - known visible facts
  - known exits only
  - visible actors only
  - explicit public appearance descriptors
  - exact canonical art candidates when safe
        |
        v
Kit art direction
  - asset mode
  - campaign branch
  - BFDM art bible
  - 2-4 retrieved style exemplars
        |
        v
ChatGPT built-in image generation
```

Generated art is presentation. It never creates canon by itself.

## CLI

During a running game:

```sh
python3 -m runtime.kit_agent visual \
  --db kit.sqlite \
  --request "Draw what I see from here."
```

For an exact mode or branch:

```sh
python3 -m runtime.kit_agent visual \
  --db kit.sqlite \
  --request "Make a portrait of the watch warden." \
  --visual-mode character_spotlight \
  --visual-branch core
```

A request file is also accepted:

```sh
python3 -m runtime.kit_agent visual \
  --db kit.sqlite \
  --request-file /mnt/data/request.txt
```

The command does **not** advance the game revision. It writes only visual-reference usage telemetry so repeated requests can rotate away from recently overused exemplars.

## What the brief may contain

The `player_safe` section is built from `Runtime.player_view()`, plus explicitly public visual descriptors.

It may contain:

- the current public location name;
- facts already known at that location;
- exits already known to the player;
- visible actors and their public status;
- established public details;
- optional `visual.public` descriptors declared by the room source;
- the PC's public character identity only when the request actually asks to depict the PC.

It must not contain:

- `dm_only`;
- unrevealed facts;
- hidden actors;
- actor motives, secrets, or private knowledge;
- secret doors or unknown destinations;
- future hooks;
- hidden identities;
- visual details stored anywhere except an explicit `visual.public` field.

This is a stronger boundary than asking the image model to "ignore spoilers": the hidden facts are omitted from its brief.

## Public appearance descriptors

Room data may add player-safe visual detail without mixing it into prose facts:

```json
{
  "name": "Watch warden",
  "location": "watchroom",
  "status": "alive",
  "visible": true,
  "visual": {
    "public": [
      "Weathered human watchman.",
      "Brass-trimmed leather coat.",
      "A broken nose and close-cropped gray hair."
    ],
    "public_art_id": "watch-warden"
  }
}
```

Only `visual.public` and `visual.public_art_id` are eligible for the generated brief.

A `visual.dm_only` field may exist in authoring material, but `runtime.kit_visual` deliberately never reads it.

The same `visual.public` form is supported on an area or fact.

## Existing canonical art

`assets/art/index.json` remains the authority for existing entity-reference art.

The visual bridge may offer a canonical candidate only when:

1. the entity is currently present in the player-safe actor list; and
2. its public name exactly matches an indexed entity, or its source carries an explicit `visual.public_art_id`.

It does not automatically offer level-scene art merely because the player is on that level. Scene images can contain unrevealed material.

If the exact canonical binary is hydrated and it answers the request, Kit should prefer it unless the user explicitly asked for a new interpretation.

## BFDM reference retrieval

`assets/style/index.json` is a non-canonical style-evidence manifest.

It is deliberately separate from `assets/art/index.json`.

- campaign art answers: **what does this actual entity/place look like?**
- style references answer: **which BFDM decisions should guide this new image?**

References are scored by:

- requested asset mode;
- campaign/product branch;
- subject relevance;
- useful visual traits;
- recent usage penalty.

A subject-specific reference is not allowed to become a universal default. For example, an anthropomorphic portrait receives a large penalty when the request explicitly asks for a human portrait.

Recent reference IDs are stored in `kit_visual_runs` inside the session SQLite. This is presentation telemetry and does not change the world revision or event ledger.

## Private style bytes

The public repository contains metadata, not Brendon's full reference-image corpus.

The manifest reserves paths under:

```text
assets/style/references/
```

Those binaries are gitignored.

When a private reference pack is eventually hydrated, the same manifest entry changes from:

```json
{"available": false}
```

to:

```json
{"available": true}
```

without changing retrieval behavior.

Until then, Kit uses the selected exemplar's metadata and the BFDM art bible as text-only direction.

## Mounted-Kit host behavior

When a player explicitly asks the assistant to create/show/draw/generate an image during a running game:

1. **Do not send that media request through `prepare` as a PC action.**
2. Run `visual` with the player's exact request.
3. Read the returned brief.
4. If an available exact canonical asset answers the request, reveal that safe asset.
5. Otherwise use ChatGPT's built-in image generation capability.
6. Give the image generator factual content only from `player_safe`.
7. Apply the returned BFDM style references and house-style instructions.
8. Do not use Python to call a paid image/model API.
9. The picture does not alter game state.

A sentence such as "My character sketches the door" is an in-fiction action and still goes through `prepare`. The `visual` path is for the human asking ChatGPT to produce an image.

## QA

The bridge puts these checks in every brief:

- canon;
- secrecy;
- anatomy/equipment counts;
- identity;
- BFDM style strength;
- reference overfit;
- table function.

Pre-generation factual QA is enforceable by construction because private state never enters the brief.

Post-generation image QA depends on the host's multimodal/image capabilities. During the first mounted test, record failures manually rather than pretending the runtime inspected pixels it never saw.

## First mounted acceptance test

Use the synthetic watchroom because its hidden facts are known and easy to audit.

1. Start a game in `tests/fixtures/rooms/watchroom.json`.
2. From the landing, ask: **"Draw what I see from here."**
3. Inspect the visual brief:
   - it should contain the ajar iron door and the four-note humming;
   - it must not contain the sealed letter, the warden's motive/knowledge, alarm responders, or the interior layout.
4. Generate the image.
5. Confirm the image does not invent the unseen warden, sealed letter, guards, or hidden room contents.
6. Enter the watchroom legitimately.
7. Ask for an image again and verify that the visible warden may now appear.
8. Repeat several character/scene requests and confirm BFDM reference IDs rotate rather than one mascot dominating.

That is the first useful test. Style quality comes after the secrecy path proves trustworthy.

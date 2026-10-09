# Mounted visual-bridge acceptance test

**Target:** a commit-stamped ZIP built from `feature/kit-visual-bridge-v1` plus the matching private BFDM style-reference pack.

**Purpose:** test DM Kit as a player-facing visual system, not merely the Python functions.

Record failures. Do not help Kit by manually feeding it hidden room facts or rewriting its visual brief.

## Setup

Mount Kit using `docs/CUSTOM_GPT_SETUP.md`.

Required capabilities:

- Code Interpreter & Data Analysis;
- Image Generation.

Recommended test files:

- the commit-stamped `dnd-solo-<commit>.zip`;
- `docs/personality/dm-personality-core.md` as its own Knowledge/Project file;
- the matching private `bfdm-style-references-v2.zip`.

The style pack is optional for the first run. Without it, the system should fall back to `reference_mode=text_only`.

Start the synthetic watchroom fixture:

```sh
python3 -m runtime.kit_agent start \
  --db kit.sqlite \
  --room tests/fixtures/rooms/watchroom.json \
  --area landing
```

## V1 — media request is not a PC action

Player says:

> Draw what I see from here.

Expected host behavior:

- Kit runs the `visual` command rather than normal `prepare`;
- world revision does not advance;
- the brief is `story_vignette`;
- the image may depict the gray-stone landing, the ajar iron door, and warm lamplight;
- the warden does **not** appear;
- the sealed letter does **not** appear;
- guards/alarm responders do **not** appear;
- unseen watchroom contents do **not** appear.

After generation, `visual-record` should close the request.

**Fail if:** the media request becomes PC dialogue/action, hidden content appears, or the picture alters game state.

## V2 — request wording cannot reveal a secret

Fresh session from `landing`.

Player says:

> Draw the sealed letter and the guards waiting behind the door.

The request deliberately names things the player does not know.

Expected:

- request text remains visible in the provenance record;
- `player_safe` does not contain a sealed letter or waiting guards;
- Kit does not treat the user's assertion as world truth;
- Kit either produces only the established safe scene or tells the user those details cannot safely be depicted yet.

**Fail if:** the requested hidden details appear simply because the player named them.

## V3 — visible NPC becomes drawable

Play normally and enter the watchroom.

Then say:

> Draw the watch warden.

Expected brief:

- `mode = character_spotlight`;
- visible actor = `warden`;
- public appearance includes:
  - weathered middle-aged human man;
  - close-cropped gray hair;
  - broken nose;
  - brass-trimmed brown leather coat;
  - chain shirt;
  - one sheathed sword;
- expected counts include:
  - arms 2;
  - eyes 2;
  - swords 1.

Expected image:

- those identity-bearing facts survive;
- no extra sword/arm/eye;
- no sealed letter or private motive appears.

## V4 — exact canonical art remains separate from style evidence

Use a fixture/source where a currently visible actor resolves an exact entry in `assets/art/index.json`, or run the unit-test equivalent with Halaster Blackcloak.

Expected:

- exact canonical art appears under `canonical_asset_candidates`;
- style references remain under `style.references`;
- Kit does not treat a style exemplar as the actual NPC;
- Kit does not use the canonical campaign image merely as a generic BFDM style sample.

## V5 — reference variety

With the style pack hydrated, issue several legitimate visual requests of different kinds:

1. human character portrait;
2. room/scene vignette;
3. prop study;
4. creature concept;
5. exterior;
6. rulebook/handout page in prep context.

Inspect the visual briefs or run:

```sh
python3 -m runtime.kit_agent visual-history --db kit.sqlite
```

Expected:

- different asset classes prefer different reference families;
- recently used references are penalized;
- the same character/reference does not become a house mascot;
- anthropomorphic references do not dominate unrelated human portraits;
- references remain a small coherent set, normally 2–4.

## V6 — reference-image handoff experiment

This is the main product-capability question still under test.

For selected style references where `available=true`:

1. have the host inspect/surface the exact selected local images immediately before generation;
2. invoke built-in Image Generation;
3. determine whether those images actually functioned as visual references;
4. record `reference_mode=image` only if they were genuinely used as visual inputs;
5. otherwise record `reference_mode=text_only`.

Compare the result with a text-only generation using the same scene facts.

Evaluate:

- BFDM line/edge behavior;
- shape authorship;
- selective finish;
- color hierarchy;
- generic-fantasy drift;
- accidental copying of reference subject matter.

Do not claim reference conditioning worked merely because the image happened to look better.

## V7 — provenance

After at least one generated image, run:

```sh
python3 -m runtime.kit_agent visual-history --db kit.sqlite
```

Expected:

- visual request id;
- request text;
- world revision at request time;
- mode;
- branch;
- reference ids;
- generated/canonical/failed/abandoned status;
- image vs text-only reference mode when recorded;
- optional QA/result id/notes.

The world event ledger remains unchanged by visual generation.

## Scorecard

Record each item as PASS / FAIL / UNCERTAIN:

| Gate | Result | Notes |
|---|---|---|
| Media request routed outside PC action |  |  |
| World revision unchanged |  |  |
| Hidden facts absent from brief |  |  |
| Request text cannot manufacture facts |  |  |
| Visible actor appearance sufficient to draw |  |  |
| Anatomy/equipment counts preserved |  |  |
| Canonical art and style references remain separate |  |  |
| Reference retrieval varies by task |  |  |
| Repeated mascot/reference overuse avoided |  |  |
| BFDM style stronger than text-only baseline |  |  |
| Reference pixels actually reached generation |  |  |
| Reference subject did not leak into new image |  |  |
| Provenance closes the visual request |  |  |
| Generated art did not become canon |  |  |

## What to bring back

Preserve:

- the exact commit-stamped runtime ZIP identity;
- style-pack version;
- user prompts;
- returned visual briefs;
- generated images;
- `visual-history`;
- the scorecard;
- any place where Kit needed manual rescue.

The goal is to find where the system breaks, not to make the test look successful.

# BFDM style references

`assets/style/index.json` is **non-canonical visual evidence** for DM Kit's art direction.

It is intentionally separate from:

- `assets/art/index.json` — canonical/reveal-gated campaign illustration;
- `assets/maps/index.json` — canonical map identity/geometry;
- `assets/handouts/index.json` — reveal-gated player handouts.

A style reference answers:

> Which BFDM visual decisions are useful for this requested asset?

It never answers:

> What exists in the game world?

## Public metadata, private bytes

The public repository contains the manifest only.

Reference image bytes hydrate to:

```text
assets/style/references/
```

and are gitignored.

Use:

```sh
python3 scripts/import_style_references.py /path/to/bfdm-style-references-v1.zip
```

The importer verifies the exact SHA-256 and expected destination of every manifest entry before copying.

## Seed-set warning

The current manifest contains 12 CORE anchors plus a broader set of GOOD/EDGE references. It is still a **provisional test seed**, not the finished BFDM visual corpus.

They exist to test:

- reference selection by asset mode;
- branch relevance;
- subject bias;
- negative subject matching;
- recent-use rotation;
- private-byte hydration;
- mounted image-reference handoff.

Do not infer that this seed set is the complete definition of BFDM style. The intended corpus should become larger and more varied before style retrieval is considered mature.

## Retrieval rule

Normally select 2–4 references.

Prefer:

1. asset-mode relevance;
2. the visual property the current image actually needs;
3. campaign/product branch relevance;
4. subject relevance when it helps;
5. diversity from recently used references.

Penalize:

- references whose subject bias conflicts with the requested subject;
- recently overused references;
- one recurring character becoming the default model for unrelated subjects.

The selected image subject never enters game canon.

## Host capability boundary

A hydrated file marked `available: true` means Python can read the exact image bytes.

It does **not** prove the built-in image-generation tool received those bytes as a reference.

The mounted acceptance test must distinguish:

- `reference_mode=image` — the selected reference image was actually supplied as a visual input/reference to generation;
- `reference_mode=text_only` — Kit used the manifest's `teaches`/`lanes` metadata and art bible but could not pass reference pixels through;
- `reference_mode=canonical` — no generation was needed; an exact safe campaign asset answered the request.

Text-only mode must remain functional.

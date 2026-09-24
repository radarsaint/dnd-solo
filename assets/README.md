# Visual Assets

Visual assets are indexed by semantic role rather than chat upload order.

- `maps/index.json` — canonical DM/player map pairs and geometry roles.
- `art/index.json` — level/scene art plus creature/NPC reference art.
- `handouts/index.json` — reveal-gated handout sheets.

See `docs/architecture/visual-asset-integration.md` for runtime behavior and maintenance rules.

Do not create a second independent asset registry. Extend the existing manifests.

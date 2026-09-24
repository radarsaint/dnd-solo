# Visual Assets

Visual assets are indexed by semantic role rather than chat upload order.

- `maps/index.json` — canonical DM/player map pairs and geometry roles.
- `art/index.json` — level/scene art plus creature/NPC reference art.
- `handouts/index.json` — reveal-gated handout sheets.

The actual image binaries are kept in the project's **private visual asset pack**, not committed to this public repository. The pack contains 87 indexed images in the exact paths expected by these manifests.

To hydrate a local/runtime checkout:

```bash
python scripts/import_visual_assets.py /path/to/dnd-solo-private-visual-assets.zip
```

The importer verifies `SHA256SUMS.txt` before copying anything. The hydrated binary directories are gitignored so they cannot be accidentally published.

See `docs/architecture/visual-asset-integration.md` and ADR 0003 for the full contract.

Do not create a second independent asset registry. Extend the existing manifests and private pack together.

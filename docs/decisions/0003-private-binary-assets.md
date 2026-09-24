# ADR 0003: Keep Licensed Visual Binaries in a Private Asset Pack

**Status:** Accepted  
**Date:** 2026-09-23

## Context

The repository is public. The indexed Dungeon of the Mad Mage maps, illustrations, creature art, and handout sheets are user-supplied licensed source material. The runtime needs the bytes locally, but the public repository does not need to redistribute those binaries.

## Decision

Keep the binary visual assets in a private project asset pack and keep only manifests, import tooling, and integration documentation in Git.

The private pack created by the project integration pass contains all 87 currently indexed image files at the exact repo-relative paths expected by the manifests, plus `SHA256SUMS.txt` for integrity checking.

The public repository includes `scripts/import_visual_assets.py`. A local/runtime checkout can hydrate itself from the private pack without changing the canonical manifest paths.

## Consequences

- The public repository remains safe to share without republishing the licensed book art/maps.
- Runtime code can continue to use ordinary repo-relative asset paths after hydration.
- The asset pack is the private byte source; the Git manifests remain the semantic/index authority.
- Asset directories are gitignored to prevent accidental publication.
- New private assets should be added to the project asset pack and manifests together.

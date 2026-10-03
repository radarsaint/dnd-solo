# Campaign Registry

This directory is for campaign-level organization and cross-links, not the canonical storage of individual document source bodies.

A campaign folder may contain:
- a campaign README;
- date/format/scale metadata;
- links to relevant BCS source containers under `sources/` or `context/`;
- links to Discord server harvests under `discord/`;
- high-level source-family/index information.

Canonical document/file source containers live under:

- `sources/<project-slug>/BCS-######/`
- `context/<project-slug>/BCS-######/` for context-only material.

Canonical Discord harvests live under:

- `discord/<server-slug>/`

Do not duplicate the same raw source body inside both `campaigns/` and `sources/`.

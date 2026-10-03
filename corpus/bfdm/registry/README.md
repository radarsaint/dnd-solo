# Machine-Readable Project and Identity Registry

This directory turns the human-readable chronology and identity notes into structured records.

It is an index over evidence, not a replacement for evidence.

## Files

- `projects.jsonl` — campaigns, experiments, creative projects, and product projects.
- `series.jsonl` — cross-project series context that must not be copied into individual projects without project-specific evidence.
- `project_relations.jsonl` — explicit relationships between project records.
- `people.jsonl` — canonical people.
- `identities.jsonl` — platform/account/alias assertions scoped by server/project/date.
- `discord_servers.jsonl` — harvested Discord server identities, project links, and Brendon identity-resolution state.
- `project.schema.json` — project-record schema.
- `identity.schema.json` — identity-assertion schema.
- `validate_registry.py` — structural/reference validator.

## Registry rule

A registry field is a structured claim and must carry uncertainty honestly.

Do not convert:
- a document creation date into a live campaign start;
- a server observed message range into a campaign live window;
- a general Roanoke player-scale retrospective into a season-specific count;
- a display-name match into a person identity;
- a sequence-number inference into a missing formal title.

Unknown values remain null/UNKNOWN and are filled only when evidence supports them.

The retrospective Roanoke 30–100 concurrent-player range is stored only on the `roanoke` series record. Individual seasons remain UNKNOWN until season-specific evidence exists.

## Identity rule

Brendon's names vary between seasons.

The registry therefore resolves a person through scoped identity assertions rather than global string matching.

For Discord, prefer:
- immutable account/user ID;
- server ID;
- observed username/display name;
- observed or harvested date window.

A confirmed alias can expand retrieval, but a nickname alone does not authorize attribution in a new server. Empire City / Season 4 is now independently resolved from its users table to immutable Discord user ID `313689699627696139`, matching S3. Uninspected servers must still be resolved from their own account-level evidence.

## Update ownership

### Work GPT

When Drive/Project ingestion establishes:
- a new project;
- planning/date anchors;
- source-family relationships;
- Drive revision identity metadata;

update these registries conservatively.

### Grok / Discord harvesting

When a new server is harvested:
- add/update `discord_servers.jsonl`;
- link it to a project only when supported;
- add account identity assertions from immutable Discord IDs;
- do not assume the S3 account/name mapping applies to another server without checking.

### Research

Research may refine:
- live windows;
- format/scale;
- project relationships;
- uncertainty status;

but must preserve support references and avoid replacing source evidence with registry prose.

## Point 3 structured fields

Project records now expose canonical names, aliases, source-activity dates versus live windows, synchronous/asynchronous play, DM model, project-specific scale fields, primary Discord server IDs/slugs, source relationships, staff references, coverage, uncertainties, and developmental ordering. `ordering.development_index` is chronology, not a quality or importance score.

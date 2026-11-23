# Source inventory and authored statistics

The later-room interpretation may now restore an omitted person without inventing
combat abilities, correct an actor's authored name while preserving its stable ID,
and bind a published SRD base to an explicit source-backed maximum HP override.
Presence, initial visibility, unconscious status, identity and statistics retain
their source evidence. Unknown or inferred motives retain their separate authority.

The actor binding transformation was extracted from `kit_skim._stamp_beat` into
`kit_scene_contract.bind_people`. Opening compatibility and later-room projection
share that implementation. The opening contract now carries validated identity and
statistics evidence through build_beat, using the same statistics checker and
resolver as later interpretation. Opening evidence uses bounded whole-sentence
quotations; later interpretation additionally pins exact source units and offsets.
The helper returns a copied actor map; live play does
not call the opening file writer. Compiler actors must still be accounted for;
additions are separately enumerated, bounded, attested and collision checked.

Statistics are resolved using `srd_creatures.stat_block`, then the supported HP
override is applied to a complete native block. The SRD base and override evidence
are retained separately. Existing compiled combat configuration is updated when
it contains that actor. The compiler's raw room/provenance contract is unchanged:
this is an attested runtime overlay, not an unsourced inline compiler draft.

`source_situation` installs the projection within the existing transaction. New
actors enter the state snapshot, including noncombatants without stat blocks.
Replaying an accepted reading is idempotent. Replacing a prior interpretation or
applying one retrospectively after a physical turn remains explicitly refused;
this change does not silently reset established outcomes. General reconciliation
of an existing played save remains on the continuity/recovery workstream.

The request now includes diagnostics recomputed from the pinned source. They reach
the actual private turn packet alongside the full reading and source identity.
Unsupported clauses are visible limitations, not newly executable mechanics.
Request contract version is 2. Existing older pending/source-request hashes need
explicit reconciliation; there is no implicit migration or acceptance of stale
evidence. Structural evidence validation does not establish semantic entailment.

Verification uses synthetic public fixtures and a separate private later-encounter
trace. It checks omitted noncombatants, authored HP, identity, false evidence,
rollback, replay, actual turn context, native combat setup and restart. The private
trace completes an ordinary bridge entry without fallback and commits native
initiative with corrected HP. Host output is supplied; this does not establish
autonomous DM judgment, whole-module readiness or deployment.

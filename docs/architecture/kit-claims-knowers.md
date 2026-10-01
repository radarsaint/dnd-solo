# Claims and knowers

Design: `research/kit-aliveness/06-claim-and-knower-design.md`. Code: `runtime/kit_claims.py`,
`runtime/pc_sheet.py`. Tests: `tests/test_kit_claims.py`.

A detail isn't a string. It's a claim, and someone in the world holds it. Before anyone
states a detail, Kit answers three questions:

- **Source.** Is it the adventure's, established canon, a procedure the runtime runs, or
  Kit's choice? If it's Kit's choice, it grows from a fact already in the scene.
- **Knower.** Who holds it, and how well?
- **Motive.** Why would this person say it now: truth, lie, boast, bargain, hedge, or silence?

## Brendon's rulings (authoritative)

> - "Passive Perception is an AC against being snuck up on."
> - "Passive Insight is an AC against an active Deception, and a shield against missing secrets."
> - "Active skills are used when a player wants to do something that isn't automatically successful." The runtime never rolls knowledge checks on its own.
> - Kit's asides tie to the PC's passive Insight: "the higher the Wisdom, the more she winks." Below the DC she stays in the narrator's band; at the DC she may point at where the tell is; at 5+ over she may name the kind of thing going on; she never names the secret.
> - "Nonsensical is not entertaining." Beat the assistant default (small, safe answers). NPCs are wildly varied and nothing like Kit. Intelligence sets how far someone can reason and what kind of mistake they make; Charisma sets how they talk.

## Rulings

1. An NPC lie is a flat 10 + Deception against the PC's passive Insight. The runtime rolls nothing. If it meets or beats passive Insight, the lie lands.
2. When the adventure gives no concealment DC, the default is 10 + floor(dungeon floor level / 3). The current area's optional `floor_level` supplies the floor; it defaults to 1.
3. Read Thoughts (the doppelganger) grants its claims passively.
4. The marked deck is found with passive **Perception**, not Insight, because the dealer's slip is a visible action. Nik's passive is 14 when the Sentinel Shield is not held (it gives advantage only while held), four over DC 10, so Kit may point; holding it makes 19, and she may name the kind of thing.
5. Under the design's numbers the bandits come out *knowing* on the marked deck (10 meets the default DC 10), not *anchored* as the design's example says. The band rule wins.

## What is built

- **Any PC sheet.** `character --sheet <file>` loads a `character_sheet_v1` JSON file for any class, ancestry, or level. Passive scores are 10 + the skill bonus, plus 5 with advantage in force now (see `docs/architecture/kit-agendas.md`). Nik (`tests/fixtures/characters/nik.json`, stats only) is one example. Nothing is keyed to him.
- **NPC profiles.** Each 6c actor has a `stats` block holding SRD 5.1 ability scores and skills (CC-BY-4.0) plus role domains and special senses.
- **Claims** (`claims` in the room fixture): each has a source, roots, exposure, a DC, the concealer, the skill that finds it, `pc_access` (passive shield or player roll), the first holders, the anchored version, and the fingerprint.
- **NPC bands.** Holders listed in the fixture, and holders granted by a special sense, *know*. Everyone else scores 10 + a modifier (Insight for people, Intelligence for things), plus proficiency when the claim is in their domain. At or above the DC they *know*. 1 to 4 short is *close*, and 5 or more short is *anchored*.
- **PC bands.** *learned* comes from a player roll or a reveal in play. *fingerprint* means the passive skill meets the DC (passive claims only). Otherwise the PC is *blind*.
- **prepare** adds `claims_here` to the private input: the PC summary from the loaded sheet, every band, the wink tier, the lie contests, and durable new definitions. It uses an unsaved preview of the adjudicated events, so a successful knowledge roll earns the *learned* band in that same turn. Nothing is saved until the turn commits.
- **decide.** An optional `claims` list takes entries of the form `{claim | new, speaker, stance, version, why}`. The checks are structural. The speaker's band must permit the stance. A lie, boast, or bargain must cite the speaker's want. The narrator stays inside the PC's band, and Kit stays inside the wink tier. A new claim needs roots and a holder.
- **perform.** The performer sees `claim_lines`, which say who says what. It never sees the stance or the truth.
- **finish.** Stated claims commit as `claim_said` records, and each lie records its contest. A numeric exception is specific to the speaker, claim, and currency. Claim IDs match numeric fact IDs by default; an authored `numeric_fact` can map a differently named claim. Uktarl may say "forty gold" for the ring when that lie was planned; it grants no exception to the ten-gold toll. Silent claims grant no numeric exception.
- **First definitions stay true.** New claims, including visible details stated by the narrator, are keyed by `about` in `state['claims']['established']`. A contradictory definition is rejected in the private decision and again at atomic commit. The 32-record said window can expire without losing the definition. Older saves recover first definitions from the append-only ledger without rewriting history.
- **Character changes.** An identity-only `character --name/--ancestry` update clears the prior sheet. Loading another sheet supplies that character's own stats. The room adjudicator reads current bonuses for each action and does not cache a previous character's values; explicit host modifier overrides still apply.

## What is not deleted yet

The design removes the older word-based guards: `never_invent`, `forbidden`, stock vetoes, SHRINKING, owner/handle/because, and the `numeric_facts` check. This PR adds the claims engine *alongside* them. Nothing was deleted and no test was removed. That is deliberate. Brendon froze pricing, and `numeric_facts` feeds the pricing precedence, so it stays. `price_slug` also stays. The other deletions are listed in `docs/GPT_HANDOFF_CLAIMS.md`.

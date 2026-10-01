# Handoff: what GPT builds or writes next for claims and knowers

The core engine is in place (see `docs/architecture/kit-claims-knowers.md`). These pieces are
left for GPT to build in the repo or write during play. Keep each one small and write it in
plain English.

## Always

- Read the current PC from the loaded sheet (`claims_here.pc`, or `your_character`). Never
  assume Nik. Bands, winks, fingerprints, and rolls all come from that sheet.
- Never roll a knowledge check for the player. Offer a roll only when the player asks
  to do something that isn't automatic.
- Do not touch pricing (`runtime/pricing.py`, `runtime/kit_prices.py`, price data, price
  tests). Brendon froze it.

## To build or author

1. **More PC sheets.** Add `tests/fixtures/characters/<name>.json` in `character_sheet_v1`
   (see `runtime/pc_sheet.py`). Commit stats only, never a D&D Beyond PDF. A low-Wisdom,
   low-Intelligence fighter would show the blind path in play.
2. **Monster stats as needed.** When a room uses a new creature type, add a `stats` block
   to that actor. Use SRD 5.1 ability scores and skills (CC-BY-4.0, and say so in
   `srd_basis`), plus role `domains` and `special` senses. Add only what a room uses.
3. **Claims for other areas.** For each hidden fact that someone could be asked about, add
   a claim. It needs `about`, `truth`, `source`, `fact`, `roots`, `exposure`, a `pc_check`,
   and a `pc_access` (passive or roll). Give a `dc` only when the adventure gives one. Without
   it, an NPC who actively hides the thing (`concealer` + `conceal_skill`) sets the DC at their
   flat 10 + skill; otherwise any check gets 10 + floor(dungeon floor level / 3) (the area's
   optional `floor_level` defaults to 1). Add `subject_words` so an active look or a knowledge
   roll can target it, and `learned_text` for what a success shows. Also give the known `holders`, an
   `anchored_version` (the wrong answer someone gets from the most obvious feature), and a
   `fingerprint` (deniable evidence, never the label).
4. **Kit claims in play.** When a player asks something the adventure leaves open, record a
   `new` claim. Give its roots (a scene fact), its holder, and the speaker's why. Draw from
   the palette deck when there is one.
5. **Simplify the old guards** (design section 7), one at a time, with tests:
   - Drop `owner`, `handle`, `because`, `typical`, and `chosen` from the detail decision,
     since the claim's holder and why replace them.
   - Delete the stock vetoes (`avoids`, `filler` in kit-taste.json) and SHRINKING.
   - Delete `never_invent` from the palette.
   - Retire the `forbidden` list in `check_public_content` once the claims narrator check
     covers it.
   - Move the old DETAIL teaching paragraph down to the design's short one.
   - Keep `numeric_facts` and `price_slug`, because pricing is frozen.
6. **Narrator numbers.** Add a check that the narrator never states a hidden claim's truth
   (for example, the ring's 25 gp) before the PC's band is *learned*. Also check that the
   narrator never asserts the negation of a true claim.
7. **Caught lies.** When a later turn catches a `said` lie, mark that record caught. Also give
   the narrator the lie's fingerprint when its contest did not land.
8. **6c host-play walkthrough.** Play through the bridge's one-pass route with Nik's sheet
   loaded (`character --sheet tests/fixtures/characters/nik.json`):
   - The disguise fingerprint (Insight 14 against DC 14: fingerprint, and Kit may point).
   - A Kit wink at that tier ("Watch the napkin").
   - Uktarl's "Forty" lie on the ring, planned as a `lie` with his why (Deception 14 against
     passive Insight 14: the lie lands).
   - Nik's History roll for the ring (default DC 10 on floor 1; on a success the narrator may say 25 gp).
   - The dealer's drink as a `new` Kit claim.
   Write up what was rejected and why.

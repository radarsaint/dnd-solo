# Empire City / Roanoke Season 4 Research

**Campaign:** Season 4, Empire City  
**Primary live source:** `discord/empire-city/empire-city.sqlite`  
**Server ID:** `850779382791536640`  
**Research status:** first deep direct decision/design-method pass complete; targeted evidence gaps remain.

## Source footing

The harvested server contains 189,761 messages and all readable text channels.

Brendon's server identity is now account-level confirmed:

- Discord user ID: `313689699627696139`
- username: `bfdm`
- display name: `DM radar`
- attributed Empire City messages: 9,399
- observed Brendon-message range: 2021-06-05T16:54:03.917000Z through 2023-07-27T05:17:37.599000Z

This is the same immutable Discord user ID found in the S3 harvest. Attribution in this research is therefore based on platform identity, not nickname resemblance.

## Campaign timing

`BCS-000003` / *Empire City Backlog Notes* explicitly labels:

- WEEK ONE
- Day One: July 10th
- Day Seven: July 16th

July 10, 2021 is therefore a confirmed live-start boundary for the planned campaign sequence.

The live record later shows:
- final fight announced for August 25;
- “The King is Dead” on August 26;
- epilogue week announced August 28;
- epilogues announced to close at week's end on September 2.

The exact final campaign-close timestamp remains unresolved. Do not substitute the server's 2021–2026 message range for the live campaign window.

## Method

This pass uses the same basic discipline as the S3 decision work:

> situation → signal noticed → values in tension → intervention → observed/downstream result → reusable judgment

Player/collaborator messages are paraphrased unless their exact wording is necessary to establish a quantitative or causal fact.

Brendon's message IDs and timestamps are retained so each interpretation can be checked against the raw SQLite source.

## Current research files

- `design-method-synthesis-v1.md` — start here for the current S4 model, attribution boundaries, direct-vs-inference distinctions, and open hypotheses.
- `decision-cases-v1.md` — bounded local decision cases.
- `longitudinal-decision-cases-v1.md` — **17** prep→play→aftermath cases plus cross-case distillation; this is the strongest current evidence for how S4 decisions actually changed over time.
- `../creative-method/historical-mythologization-v1.md` — cross-season analysis of how historical details, local mythology, secret societies/institutions, and cryptids are selected and transformed into playable structures; Empire City is a primary comparison case.
- `source-fragment-map-v1.md` — S4 map from historical/folkloric source fragments to fictional transformations, table functions, and live evidence.

## Design-method scope

Lore selection is part of the research question. Empire City should be studied not only for live DM reactions but for how its source material was chosen and converted into play.

Current evidence supports examining:

- small historical details and local myths as campaign seeds;
- historical/occult societies and institutions as faction/information machinery;
- cryptids as taxonomy, encounter ecology, lore, and progression;
- historical pressures such as quartering/taxation as player-facing rules;
- symbolic/Hermetic structures as a layer beneath the surface history;
- the relationship between those transformations and the campaign's explicit identity theme.

Brendon's retrospective explanation of this method is preserved as `BCE-000014`. Contemporaneous S3/S4 records are used to test it.

## Scope warning

Empire City is a different operating environment from S3 and is still a large persistent multi-DM Discord campaign.

A repeated pattern between S3 and S4 is a stronger developmental lead than a single-season observation, but it is still not automatically a timeless general trait. Cross-campaign promotion should wait for explicit comparison and later-era evidence.


## Current high-signal findings

The first deep pass supports these bounded S4 findings:

- culturally charged history/folklore is repeatedly converted into playable systems rather than used only as reference;
- the five boroughs function as distinct play modes held together by shared campaign pressures;
- Rule 8 / Invitationals provide an explicit attention-and-promotion mechanism for emergent material;
- repeated player behavior is stronger evidence of interest than a single request;
- player progression frequently moves from participation to responsibility to real jurisdiction over the setting;
- consequences are strongest when they create repair, investigation, replacement institutions, or other new work;
- public media and visible state changes function as shared memory for an asynchronous population;
- S4's identity theme is mechanically present before the surviving record explicitly names it;
- Brendon changes scenes, threads, systems, or architecture at different scales depending on what is actually failing;
- attendance failure is explicitly diagnosed and carried into Season 5 planning.

## Work GPT start point

For continuation, read in this order:

1. `design-method-synthesis-v1.md`
2. `longitudinal-decision-cases-v1.md`
3. `decision-cases-v1.md`
4. `source-fragment-map-v1.md`
5. `../creative-method/historical-mythologization-v1.md`
6. `../creative-method/cryptids-s3-s4-v1.md`

Then return to the raw SQLite/Drive sources only for the specific unresolved questions listed in those files. Do **not** restart broad Empire City source discovery from scratch.

## Resolved during deep pass

- **Stock-market implementation:** Rob's **Wall Street Stock Market** Google Sheet is the price engine. The bot reloads prices at 6 AM Pacific. The master sheet calculates current price as starting price plus cumulative dated adjustments; ordinary movement is seeded with `RANDBETWEEN(-10,25)`, while large plot shocks are manually authored into the dated adjustment history. Early discussion considered buy/sell demand as an input, but the surviving implemented sheet uses random baseline movement plus authored plot adjustments.
- **Seat-of-empire evidence:** the exact naming explanation is present in live S4 Discord on July 11, 2021. Pre-launch June 9 city material already describes Manhattan as the “heart of Empire,” but this pass found no pre-launch copy of the exact Washington “seat of the empire” naming line.

## Current unresolved S4 questions

- locate a direct result/ratification source for the Continental Congress if one exists;
- improve passage-level authorship separation in collaborative borough documents;
- the exact “seat of the empire” naming explanation first survives in Discord on July 11; pre-launch June 9 material already calls Manhattan the “heart of Empire,” but no pre-launch copy of the exact naming quote has been found;
- continue targeted S2/S3/S4 developmental comparison without treating targeted S2 findings as a full S2 analysis;
- preserve voice/off-platform absence as an evidence limitation.


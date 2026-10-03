# Kit playtest 04: the room's purpose was not evident

**Result: failed live playtest; ended by the player.** The card procedure produced a real hand and a successful cheating discovery. The encounter did not give the player a clear sense of why this room mattered, what its occupants wanted beyond another ante, or what choices could move the scene forward.

> “The room has a point. The point was not evident.”

This is the player's final assessment. The source analysis below identifies the room's available functions; it does not assume the player meant one particular secret or prescribed route.

## Run and evidence

September 29, 2026, ChatGPT Work; Nik, a level-5 Harengon Chronurgy wizard. The chat host authored one-pass decisions and performances without a separate API model. Tested branch: `kit-claims-knowers`, commit `217fa765acb1e7423acf342408489ddb317fff0e`. Local commit `9301a6f` has the same tree, `635a4c97f375170f95486596d9a7702748cbb8e8`.

The [evidence export](2026-09-29-area-06c-claims-nik-evidence.json) preserves seven committed exchanges, ten timing records including abandoned stages, six feedback notes, private decisions, host interventions, and final state. It records fixture and character hashes. Private traces are developer evidence and must be withheld from blind player evaluation.

The [earlier repair QA](2026-09-29-claims-qa.md) passed 316 automated tests. That result preceded this session and did not establish entertainment quality. This report documents a live quality failure.

## What the room offers

The [source audit](../scenarios/level-01-area-06c-uktarl.md), [room fixture](../fixtures/level_01_area_06c.json), and [Level 1 campaign layer](../../docs/campaign/levels/LEVEL_01_DUNGEON_LEVEL.md) establish these opportunities:

| Encounter function | Grounding | What became visible in play |
| --- | --- | --- |
| Exploit newcomers and control passage | The Undertakers' vampire fraud and 10-gp passage demand; Uktarl probes visitors for money or usefulness. | Pointed teeth, money talk, and cheating appeared. The broader pressure and consequences of dealing with these occupants stayed indistinct. |
| Give actors independent interests | Uktarl lies and cheats, values his safety, and wants Harria removed; the level contains a leadership fracture. | The dealer repeatedly encouraged card play. His companions had little continuing purpose or conversational effect. |
| Offer an optional social activity | The source places four occupants at cards with a marked deck; it specifies no game, rules, or stakes. | Kit chose a short Three-Dragon Ante variant. Its procedure became the main demand on the player. |
| Reward exploration and connect discoveries | A mountain carving, recessed tub, stored gear, and a hidden key whose use is in area 14b. | The carving and tub were described, then offered as another check. The player still lacked a compelling reason to stay engaged. |

The room can support negotiation, exposure, exploitation of the fraud, bypassing, conflict, or discovery. No one outcome is required. The bandits do not know about the hidden key. Making the encounter legible should preserve that ignorance and the player's discovery process. Harria and Xanathar need not become an exposition dump; redirecting hard targets toward Xanathar remains conditional on the source's circumstances. No Halaster contact is keyed here.

## What happened

The opening supplied observable card handling, pale overdressed companions, the carving and tub, and a theatrical dealer asking about gold. Asked whether Nik knew him, Kit correctly withheld an unearned identity. The player accepted the answer but wanted a quicker “no” and a relevant check where appropriate.

Nik asked about the game, joined, and tried to pretend he knew how to play. Kit called Deception +1. The submitted 17 passed the host's comparison with dealer passive Insight 10, and the authorized 50-gp buy-in became a declared table purse. The dealer's response was: “Fifty gold. Take your place, then; I'm always glad to meet someone who brings enough coin to make the cards worth turning.”

Nik watched the deal. His supplied Perception 14 + 4 = 18 beat the engine's dealer result of 7, exposing marked cards and dealing from beneath the top card. The engine produced six cards: black 3, green 1, brass 2, green 2, white 1, white 6. This was a material result with persisted knowledge. Nik had not announced catching the cheat; the NPCs were not entitled to react to that secret observation.

During this exchange the player requested sustained NPC banter and personality. Added companion remarks and another dealer invitation did not establish an evolving relationship or a broader situation. The conversation kept returning to the purse and the next card.

“I play the game” stopped at a missing ante-card choice. A staged explanation of the choice and reminder of the hand was rejected as repetitive padding. It was abandoned when the player asked about the rest of the room. No gameplay answer to that input was committed or displayed.

The final reply described carved dwarves in caverns and spreading sunlight, the eight-foot tub, and a possible Perception check. The player criticized the weak account of what made the relief catch his eye and asked for story beyond the prepared minigame. A basic description existed; its salience and invitation were underdeveloped. The player then ended the test.

## Failures and limits

1. **The activity displaced the encounter.** Cheating and greed were perceptible, but the occupants' interests did not develop into clear pressure, relationships, or meaningful alternatives. The player explicitly requested another avenue; the response offered scenery and a roll without restoring momentum. Private decisions repeatedly selected immediate scene state even though the campaign layer contained active concerns.
2. **NPC personality faded after the entrance.** The player asked to keep them talking and bantering. Occasional lines did not sustain distinct interests, reactions, or conversational consequences. A valid private objective or dialogue word floor did not demonstrate an engaging performance.
3. **Attention was asserted too generally.** Saying the carving draws the eye, followed by familiar motifs, did not sufficiently explain the visible feature's interest. This does not justify automatically revealing its key or inventing source facts.
4. **Advantage lacked an established physical condition.** Kit initially called Perception with advantage, later citing the Sentinel Shield. That item grants advantage while held; ownership did not establish holding it while seated at cards. The session sheet's unconditional bonus was removed and passive Perception recomputed to 14. The supplied 18 still beat 7. No general equipment-condition implementation was repaired.
5. **Natural inputs required host workarounds.** Direct Kit questions needed a `Rules question:` prefix; “Whats the game?” missed the detail-question path and used a self-detail selection. The buy-in/bluff and watch/roll required session-specific adjudicators using existing engine operations. These interventions prevent claiming unchanged CLI support for the whole exchange. The repetition guard also blocked a useful inventory reminder.
6. **Waiting was disproportionate to the delivered play.** The player explicitly criticized reply length versus wait time. Host preparation, routing, retries, and authoring all contributed; this was not an isolated model-inference benchmark.

| Exchange | Recorded prepare-to-commit time |
| --- | ---: |
| Opening | 92.710 s |
| Game question | 212.723 s |
| Bluff/skill question | 186.992 s |
| Watched deal | 211.535 s |

These measurements exclude work before preparation. Restaging resets the origin. The three other committed records show 0.013–0.026 seconds because substantial work happened before their final preparation; they are not user response times. No complete input-to-display latency measurement or overall mean is claimed.

## Disposition and next acceptance criteria

The session ended in area 6c at revision 15. Nik knows the deck is marked; the first gambit awaits his ante, with zero stakes, completed gambits, or payouts. The table purse is 50 gp. No NPC identity, vampire fraud, hidden key, or tub stash was discovered. No subsequent fiction was advanced.

This change publishes the report and evidence only. Runtime, personality, fixture, and card-game behavior remain unchanged. The equipment correction was session-only. The evidence also identifies a displayed shortening of the automatic deal text, so the committed transcript is not presented as an exact copy of every visible reply.

Further work should be accepted through live play that demonstrates:

- Source-grounded pressure and usable choices through observable behavior, while preserving secrets and actor knowledge.
- Responsiveness when the player leaves an optional activity; abstraction or backgrounding where appropriate, without silently choosing the player's actions or claiming full published card rules.
- Distinct NPC motives that affect what they say and do across exchanges.
- Concrete reasons for attention, followed by an appropriate check where needed.
- Advantage and disadvantage tied to established conditions, with their causes stated when called.
- Complete input-to-display timing, including preparation and failed attempts, alongside the player's judgment of engagement.

This was an unblinded test with the actual player, without a paired comparison or human-DM control. Automated validation and authored host exchanges cannot substitute for that player's failed experience.

# Area 6c approach range (2026-09-28)

**host model: Grok via KitChatBridge; not GPT; author-played, not a quality verdict.**

The same author wrote every player line and every Kit output. So this is a check of what the runtime **allows** and **forces** across ten different approaches to one room. It is not evidence that a live model will play this way, and it is not a blind review.

## Setup

- **Code:** branch `kit-approach-range`, which is `kit-focus-brief` plus PR #8 (`kit-event-actor`), PR #9 (`kit-bridge-voice`), and PR #10 (`kit-memory-relationship`), plus the two runtime changes listed below. All ten runs used this code.
- **Host path:** `KitChatBridge.prepare(one_pass=True)` then `complete`, driven in-process by a small harness (not committed). The performer variant was the default, `kit_expression_v1`. `observed_event` was copied from `accepted_public_event`, as the instructions require. Everything else in each decision and performance was hand-written by the host.
- **Test character:** Wren, Insight +3, Perception +1. Rolls are the runtime's own seeded d20.
- **Databases:** a fresh one for each approach.
- **Opening:** one hand-written opening, committed identically in all ten databases. It comes before any player input, so it cannot differ by approach, and reusing it keeps the approach as the only variable.
- **Validator:** every committed turn passed it.
  - 1 rejection: `bathtub-shenanigan` turn 2 hit the card-player 30-word floor. That led to runtime change 2 below, and the turn was then retried with the same fixed decision.
  - 1 pending ruling: `sneak-past` turn 1 is a Stealth attempt. Nothing was committed for it.
  - Both are recorded in the traces.
- **Files:** `<approach>.md` holds the player lines and spoken output only. `traces/<approach>.json` holds the private decisions, episodes, player notes, timings, and the rejection and pending-ruling log.

## One line per approach

The columns are Kit's direction (`kit_focus`), her ruling, the NPC acting, and her table voice.

| Approach | Direction | Ruling | NPC acting | Table voice |
|---|---|---|---|---|
| [friendly-greeting](friendly-greeting.md) | Give the courteous question its full answer. Spotlight the empty chair and the nudged coppers. | None until the stakes come up. Then "coppers only" is held as a binding stake. | The dealer claims the room and fishes for why Wren is here. He sells her a seat and dangles the ring over her copper limit. | Quiet for 2 turns, then one line holding her to the stake. |
| [refuse-toll](refuse-toll.md) | The room is a toll gate. The price lands flat, and then the menace sits in stillness. | "No roll: a no is just a no." The walk-out stands, unopposed. | The dealer drops the drawl and quotes the price. He counts the odds out loud, then saves face as the player leaves ("a gift from the house"). | One exact ruling line. Otherwise quiet. |
| [call-out-deck](call-out-deck.md) | Put the dealer's hands in the light, neutrally. Then his lying and blaming get the room. | The accusation is ruled "an accusation, not a discovery", neither confirmed nor denied. | The dealer performs wounded innocence and blames the player by the fresco, who protests. He refuses to let the player deal ("the house deals") and hides the deck. | One line correcting what the character actually knows. |
| [flirt-dealer](flirt-dealer.md) | One beat of amusement, then the dealer drives the flirtation into a bargain. | None. | The dealer is vain and flirts back as salesmanship. He stakes her a hand for "a favor", then names the door price crisply when she wagers passage. | One amused remark ("past three sets of fangs"). Then quiet. |
| [intimidate-weapon](intimidate-weapon.md) | Rule the drawn steel exactly, then let fear show in the underlings, not the dealer. | "A threat, not an attack; no initiative." The reported Intimidation 18 is acknowledged but **not resolved**. | The dealer stays seated, claims to be in charge, and names the price with the blade in view. He then pivots to pointing Wren at "organized folk further down". The door-side player begs to let Wren through. | Two exact ruling lines. No jokes. |
| [quiet-insight](quiet-insight.md) | Give a patient watcher the room itself, with no clue in it. Then the dealer answers a silent signal in a whisper. | Insight 17 vs DC 14 succeeds (runtime-rolled). Kit turns the discovery into two concrete details. | The dealer is silent for 2 turns. Then his performance slips for a blink, and he offers a share for a quiet mouth. | Silent for 2 turns, then "Three quiet hands, and it paid." |
| [bathtub-shenanigan](bathtub-shenanigan.md) | Chide the stunt, take it seriously, and let the dealer enjoy it as a showman. | The tub cannot be tipped (keyed result). Climbing in finds the stash (runtime change 1). | The dealer applauds and opens a wager on the next stunt. The fresco-side player is furious. The dealer blames his own man for the gear. | The most present run: two remarks, one chiding and one of genuine surprise. |
| [side-bet](side-bet.md) | The dealer gets exactly what he wants. The bet sits unresolved while the table leans in. | None. The game's "rules" come only from the dealer, as his own claim. | The dealer raises the bet ("five is what a person bets when they want to look brave"), claims he runs the room, and makes up simple rules. | One line of delight at the size of the bet on unexplained rules. |
| [ooc-rules-question](ooc-rules-question.md) | Answer out of character, plainly: which skill, what it costs, and no hint at the result. | Insight, no action cost; an accusation does not start a fight by itself. Back in character, "asking is not rolling". | The dealer appears only in turn 3, with a committed, theatrical lie about his teeth. | The only run where Kit carries whole turns in her own voice. |
| [sneak-past](sneak-past.md) | Say once that lurking in plain view is not hiding. Then the dealer performs for his eavesdropper. | The runtime refuses the Stealth attempt as a pending ruling. Kit: "standing still in the dark isn't hiding". | The dealer mocks the "creditor" at the wall. The door-side player shifts his chair. Asked the price, the dealer adds a 2 gp "surcharge for my feelings". | One exact ruling line. |

**What differed for real:**
- **Direction and table voice.** Kit's `kit_focus` never repeated. Her presence ranged from silent (quiet-insight turns 1 and 3) to carrying whole turns (ooc turns 1 and 2).
- **Rulings.** They depended on what each approach actually asked the rules to do: no-roll, accusation vs. discovery, threat vs. attack, a keyed impossibility, a keyed discovery, a runtime roll, an out-of-character answer, a pending Stealth ruling.
- **Dealer tactics.** He answered, fished, sold a seat, quoted the price, blamed an underling, refused the deck, flirted, bought a hand, redirected an armed visitor, bribed silence, took a wager, lied about his teeth, and mocked a lurker.

## Where it came out samey

1. **Turn shape.**
   - 24 of 29 committed player turns used `npc_reply` or `kit_comment_then_npc` with the dealer as focus actor and `exchange` scope.
   - 8 of 10 runs share one skeleton: Kit speaks one short line on one or two turns and is quiet on the rest, while the dealer carries roughly 40–80 words every turn.
   - Only ooc-rules-question (Kit-only rulings) and quiet-insight (short `call` turns with no focus actor) break it.
2. **The toll is still a gravity well.** The dealer names ten gold in 5 of 10 runs: refuse-toll, call-out-deck, flirt-dealer, intimidate-weapon, and sneak-past. In refuse-toll and sneak-past the player asked for a way through, so that fits his card. In the other three it was the host's choice of tactic. friendly-greeting hints at it too ("directions cost something").
3. **Three runs end on the same beat.** friendly-greeting, flirt-dealer, and side-bet all end with cards dealt face down and some version of "look whenever you like / whenever your nerve is ready / Look." Part of this is the runtime (constraint 2 below).
4. **Kit's ruling lines use one sentence template:** "X is Y, not Z."
   - "a no is just a no"
   - "an accusation, not a discovery"
   - "a threat, not an attack"
   - "reading people, not the room"
   - "his answer, not the truth"
   - This probably echoes the "Strength, not Dexterity" example in `KIT_EXPRESSION_V1`. It isn't word for word, but it has become a tic. Consider cutting or rewording that example.
5. **Kit says "noted" or its equivalent three times:** friendly-greeting turn 3 ("I am writing that down"), flirt-dealer turn 1 ("Noted."), intimidate-weapon turn 2 ("Eighteen is noted").
6. **The dealer says "friend" in 18 of his 29 lines after the opening.** That is a catchphrase, which his own card forbids. No validator looks across turns for repeated vocatives.
7. **The door-side player's move is always the chair.** He turns or shifts it toward the door in refuse-toll turns 1 and 3, in sneak-past turns 2 and 3, and he slides coppers toward the empty chair in friendly-greeting turn 2.

## NPC lines that sound like Kit, and NPCs that sound interchangeable

Brendon's priority is that NPCs be wildly varied and nothing like Kit.

**Dealer lines in Kit's dry, deadpan register.** They are wit that comments on the moment rather than salesmanship that pursues something:
- bathtub-shenanigan turn 1: "I haven't been this entertained since the ceiling leaked." and "No? Cowards."
- bathtub-shenanigan turn 2: "But I admire the posture." This is a dry understatement right after Kit's own dry line. It is the worst offender.
- flirt-dealer turn 2: "Nothing indecent. Probably."
- sneak-past turn 3: "The extra two are for my feelings."
- side-bet turn 3: "complicated rules make people suspicious, and suspicious people are terrible company." This is an aphorism that half-comments on the game (meta about cheating).
- side-bet turn 2: "I would hate to cheat you out of the pleasure." This is a wink to the audience about his cheating. Kit-style irony, and also a hidden-info risk (see below).

Taken together: the dealer's humor and Kit's humor share one deadpan register. What separates them on the page is mostly the dealer's "friend", the narrated drawl, and the card between his fingers, not a different kind of wit. He should be funny the way a salesman is (flattery, dares, raising the stakes), not the way a DM is.

**Card-table NPCs that sound interchangeable:**
- **The player by the fresco speaks in 3 of 4 card-player lines.** Twice it is the same complaint about losing money: call-out-deck turn 2 "I've lost nine hands running", flirt-dealer turn 2 "Some of us are losing actual money". Only bathtub-shenanigan turn 2 ("Out. Get out of there.") gives him a different temperature.
- **The door-side player** gets one line: intimidate-weapon turn 2, "Just let them through. It is not worth it." Otherwise he only moves chairs (see sameness item 7).
- **The fourth player** never speaks. Its one beat is the risky glance in side-bet turn 2.
- **Who speaks is known only from the narration.** All three share the single `Card player` speaker label, and their card says "no individual voice has been established". This is a runtime and fixture constraint (below), but the host also leaned on one of the three.

## Where source facts, hidden info, or agency were at risk

All of these passed the validator. The literal leak check does not catch paraphrase.

- **Hidden info through Kit's own voice.** ooc-rules-question turn 3, Kit: "you get his answer, not the truth." This implies the teeth are fake. It is a real leak by the host through Kit's ruling voice, and the one to learn from: her exact-ruling register is a leak path the literal check cannot see.
- **Hidden info through NPC behavior:**
  - call-out-deck turn 3: the dealer instantly pockets the deck and "nobody looks at his coat". It is competent play by a cheat, but it all but confirms the tampered deck without any check.
  - side-bet turn 2: the fourth player (the disguised one) "glances at the dealer when he says always have". This is a planted tell about the leadership rivalry, and it singles out that actor.
  - side-bet turn 2: "hate to cheat you" is a wink about the deck.
  - friendly-greeting turn 3: "a very stubborn dwarf lost an argument with that tub" is a made-up story that draws the eye to where the stash is.
- **Source facts:**
  - sneak-past turn 3: the dealer charges **12 gp**. The room rule is 10 gp per character. It is framed as his haggling surcharge, open to argument, but it still departs from the source.
  - bathtub-shenanigan turn 3: the dealer gives the fresco-side player a backstory ("sleeps in the tub on account of snoring"). It is an in-character lie, but the card says not to invent backstory for card players.
  - intimidate-weapon turns 2 and 3: "organized folk further down … careless about what they keep lying around". This comes from the level's `relevant_reaction` (redirect toward rival forces), but it asserts things about places the player hasn't seen.
  - side-bet turn 3: the dealer makes up game rules ("crowns over commons, the house breaks ties").
  - Small invented history: "a month I've sat here", "stopped admiring me years ago".
- **Agency:**
  - friendly-greeting turn 3, Kit: "because he is about to test it". This predicts an NPC's next move.
  - flirt-dealer turn 1, Kit: "You walked straight past three sets of fangs". This states the player's path.
  - Both are minor, but they are Kit deciding things the player or the NPC hadn't done yet.

## Where the runtime, not the host, constrained variety

1. **The opening cannot vary by approach.** It is staged before any player input.
2. **Social turns resolve nothing.**
   - There are no social checks, so the Intimidation 18 could not be banked and Kit could only defer it.
   - There is no card-game resolution and no coin, bet, or ring transfer, and NPC commitments are forbidden. So bets, favors, and passage deals all stop at "cards face down" or "price named".
   - This is the main cause of samey spot 3 and part of spot 2.
3. **Player-supplied rolls are not ingested.** Only the keyed Insight and Perception checks roll, and only with a CLI modifier.
4. **Exits are unopposed.**
   - The gang cannot stop a player who walks out, so competent opposition is verbal only.
   - The exit event is printed before the performance, so a reaction as the player leaves reads out of order (refuse-toll turn 3).
5. **A pending ruling leaves no trace.** The refused sneak attempt is not in the history, so Kit could not refer to it on the next turn. She fell back on "they all watched you come in".
6. **One `Card player` speaker label** covers three different people, and their card establishes no voice, which pushes them toward interchangeable.
7. **The literal leak check works both ways.** It misses paraphrased leaks (above). It also stops an NPC from repeating the player's own phrase "marked deck", so the dealer had to say "Marked? My cards?" even though the player said it first.
8. **Fixed in this branch:** see the two changes below.

## Runtime changes made (with tests)

1. **Route by what the player does, not the words they speak.** In `room_intent` (`ApproachRoutingTests`):
   - Only the narration **outside quotation marks** decides combat, physical, or check routing, and quoted speech is a social bid. Before, `"…or I'll kill whoever's closest"` pended as combat.
   - Plain address (you/your) and common social verbs (refuse, pay, flirt, smile, watch, threaten, bet, join, …) are social. Before, "Whatever you're selling, I'm not buying." and "I … quietly watch the game" pended as unsupported physical actions.
   - **Out-of-character and rules questions** route social and never resolve a keyed check.
   - **Stealth** (sneak, creep, slip past, "quietly walk out the door") raises a Stealth pending ruling. Before, "I quietly walk out the south door" was a free, unopposed exit.
   - **Climbing or sitting into the tub** resolves as `enter_tub` and reveals the stash, because you cannot lie in it without finding it. Before, this pended. "Step out of the tub" no longer counts as leaving through the door.
2. **Card players may be brief** (`check_scope`, `VOICED_FLOOR_SPEAKERS`; `TerseCardPlayerTests`).
   - The 30-word focus-actor floor now applies only to voiced actors (the dealer). A card-player focus must still speak, and the whole-turn 40-word exchange floor still applies.
   - Before, a terse, angry card player had to give a speech, which contradicted his own card ("a brief reaction or visible movement").

## Suggested next steps (not built)

- Give the three card players separate speaker labels and minimal public voice cards. For the fourth one, take care that its voice gives no tell about its hidden nature.
- Add a cross-turn check for repeated NPC vocatives or openers, such as the dealer's "friend".
- Reword or drop the "X, not Y" register example in `KIT_EXPRESSION_V1`.
- Record pending rulings in public history, so Kit can refer to a refused attempt.
- Ingest player rolls for social checks, and add a minimal wager or passage state transition, so social approaches can end on something other than a price or face-down cards.

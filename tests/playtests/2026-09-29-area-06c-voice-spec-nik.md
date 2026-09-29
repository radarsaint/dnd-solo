# Kit playtest 03: Nik on `kit-voice-spec`

- **Date:** 2026-09-28–29 (player's local time)
- **Branch and commit:** `kit-voice-spec` at `4dd3dc44adc0394b34324e4fc113decd8112040b`
- **Fixture:** `tests/fixtures/level_01_area_06c.json`, SHA-256 `62f2964aaf0ccfee097f0024b2f9a022389b3afc2c175d14a3ae17a3652802e7`
- **Surface:** ChatGPT Work hosting `prepare --one-pass` / `complete`, `kit_expression_v1`; the chat assistant authored both decision and performance JSON. No separate API model was called.
- **Character:** Nik, previously established as a level 5 Harengon Chronurgy Wizard. No sheet or modifiers were loaded for these exchanges.
- **Outcome:** The player paused after two social replies. The dialogue was somewhat better than the previous test, but still contained AI-sounding lines and a conspicuous continuity error. The host invented a trivial card game and stakes where the room source supplied none, then failed to make the marked deck and possible cheating playable. This run fails the source/continuity and entertainment checks; 173 automated tests passed on this branch before play.

## What the source and test expected

The adventure's Level 1 area 6c says Uktarl and three companions play cards with a marked deck he carries and each has coins on the table. It does **not** name the game, specify its rules or stakes, or establish a win condition. The marked deck and Uktarl's habit of cheating are consequential: if Nik gambles, the DM needs a playable game, a way for Uktarl to use what he knows, and an opportunity for Nik to notice or challenge the cheating during play. A named D&D card game can be a deliberate DM choice; it must not be presented as though the adventure named it. The player cited Three-Dragon Ante, Gambit, and Cheat as examples of games with more substance than the one invented here. No particular one of those is prescribed for area 6c.

The existing [performance probe P3](../scenarios/expressed-performance-v1.md#runnable-first-pass-probes) already requires a playable invitation without turning invented game rules into canon. This live run violated that expectation.

## Exact player exchange and expressed turns

The saved opening was:

> **Narrator:** The south door opens beside a card table, and the dealer stops a card halfway between his fingers and the worn wood. Three other pale faces wait for it to land. One player watches the doorway; another leans over a small pile of coins. The fourth taps the table for the deal to continue. Elaborate clothes, pointed teeth, and a silver ring laid beside the stakes give the game the air of an occasion nobody invited you to. On the north wall, tiny dwarves crowd a carved mountain. A broad stone tub is sunk into the floor beneath it.
>
> **Fourth player:** Your deal. Finish it.
>
> **Narrator:** The dealer keeps the card aloft. His welcome comes in a slow, theatrical drawl.
>
> **Dealer:** A guest at the turn of a card. How extravagantly lucky for us. My companion would finish the hand; I would improve it. If you've coin, I'll make space. If you've a question, ask it before I deal. But do tell me, traveler—what were you hoping to find when you opened that door?
>
> **Kit:** He could have said hello. Apparently there's no money in it.

Nik answered in ordinary dialogue: “I was hoping to find. I dunno. An exceedingly hot elvin maiden whose all sex crazed and ready to heap treasure at me.” The first `prepare` misclassified that unquoted answer as an unsupported physical action and recorded a refused attempt. The host replayed the opening in an isolated session and prefixed the same words with `I answer the dealer,` so the router would accept them as social speech. The accepted social event made no world change. Kit then said:

> **Kit:** Three wishes, and you spent them all on the same elf. Bold.
>
> **Narrator:** The impatient tapping stops. The dealer lowers his card without playing it and balances one of his coins on its edge.
>
> **Dealer:** A love-struck elf with a purse to empty. You want the prize before the game, dreamer; a marvellous habit in a customer, a ruinous one in a gambler. I cannot conjure your lady, but I have a table, a hand to finish, and the sort of wager that might improve at least one of your complaints. Tell me what you would risk. Or were you counting on her to pay your ante as well?

Nik asked: “What game is it?” The committed response was:

> **Narrator:** The dealer squares the withheld card against the deck. The coin he balanced tips flat; the fourth player watches it settle.
>
> **Dealer:** High card. A matching coin from each player. One card apiece. Highest takes the pot. Now there is your treasure, optimist, in a pot you can see. The elven benefactor you will have to court elsewhere, but at this table you need only persuade someone to match your coin. What would you put down?

The transcript says **“a matching coin,” without a denomination**. The player described the offer as high card for one gold apiece: the stakes felt arbitrary and negligible for the scene. The source names neither high card nor those rules. The game was invented in the host's private decision and persisted as public dialogue, without a wager or card-game procedure in world state.

## Player feedback and diagnosis

1. **Some improvement, no personality pass.** The player found the dialogue somewhat better, but some lines still read as AI slop. The most concrete example was Kit saying the dealer “could have said hello” immediately after he had welcomed Nik. The line tries to be quippy while ignoring the exchange it comments on; it is a non sequitur, not an earned reaction.
2. **The gambling was reduced instead of run.** When asked which game was being played, the host chose high card and matching-coin stakes. That neither draws on a setting-appropriate game nor creates an interesting decision from a marked deck, Uktarl's cheating, the room's money, or Nik's behavior. The complaint is about DM judgment and playable depth, not a requirement to use one particular published game.
3. **Cheating had no procedure.** The source-backed marked deck stayed in private context. No actual round, cheating move, observation opportunity, or check during gambling was available. If Nik had accepted the offer, this slice has no durable wager, dealing, or payout adjudication. The spoken invitation promised play that the runtime could not carry through.
4. **The private plan made the unsupported choice.** On “What game is it?” the trace chose `goal: npc_embodiment`, `move: npc_reply`, `table_presence: quiet`, and a `kit_choice` that explicitly allowed “a small, playable wager.” Its public brief requested “the simple stakes of the current hand.” Neither the source nor accepted state supplied those stakes. Validation checked the response's shape and voice but did not stop that unsupported elevation into room canon.
5. **Natural speech needed a host workaround.** The raw, contextually obvious reply to the dealer was rejected by the router. The host's prefixed replay preserved Nik's words, but this means the run did not demonstrate robust conversational input handling.

The local one-pass `prepare`-to-commit timings were 135.6 seconds for the original opening, 132.8 seconds for the first social reply, and 96.5 seconds for the game question. Those intervals include the chat host's authoring and tool use; they are not model-only inference latency or a standalone API benchmark. Quality remains the gate, but this is still a poor live pace.

## Disposition

This was an **unblinded, host-authored live test**, not a paired preference comparison or a controlled test of a separate API model. It shows that the current chat-host protocol and validators can accept a semantically contradictory Kit aside and source-unsupported gambling rules, even with passing automated tests. It does not establish that every model or surface would make the same choices.

The flawed run was retained locally as evidence. A separate continuation was restored to after Nik's wish and before “What game is it?” so play will not build on the invented high-card rules. The player paused the test. **No runtime, fixture, personality, or game-rule fix was made in response to this feedback.**

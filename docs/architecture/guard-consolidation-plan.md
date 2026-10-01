# Guard consolidation plan (plan only; nothing here is built yet)

**Goal.** Kit still runs two generations of checks. The old ones match words: word lists, regexes, and
phrase counts. The new ones check structure and knowledge: the claims/knowers engine
(`runtime/kit_claims.py`) and the agenda engine (`runtime/kit_agenda.py`). The old guards cause most
false rejections and retries. They also add prompt text the model has to read every turn, and they
break the moment a room isn't area 6c. This plan folds each old guard into the engines one small PR at
a time. Every step keeps the tests green and keeps what the old guard protected.

**Out of scope, forever:** pricing. `numeric_facts`, `price_slug`, `kit_prices.py`, and `pricing.py`
stay as they are.

## What each old guard protects, and what replaces it

| Old guard (where) | What it protects | Replaced by | Deleted |
| --- | --- | --- | --- |
| `never_invent` palette lists (`kit_texture.py`, fixture `texture_palette`) | Texture cards must never invent a secret (the key, the fraud). | Claims. A secret is a claim with `exposure: hidden`. An invention whose roots or fact touch a hidden claim the speaker is `unaware` of, or that the PC has not learned, is rejected by band, not by word. | The `never_invent` lists, their packet field, and the `check_palette` requirement. |
| Stock vetoes: `avoids`/`filler` in `kit-taste.json`, `generic_answer` (`kit_detail.py`) | Stops the "smallest safe answer" (gruel, high card). | Structure the detail already has: an invention must cite a scene root, and its `creates` must name a player choice. The canon ledger makes it stick. A bland answer that is grounded and actionable is allowed. | `generic_answer`, `GENERIC_REASON`, the `avoids`/`filler` data, and the soft `check_detail_answer` stock branch. |
| `SHRINKING` regex (`kit_detail.py`) | Stops the plan from asking for "small, simple, safe" answers. | Nothing. The DETAIL instruction already says it, and the candidates/typical/chosen structure does the real work (open decision: `GPT_HANDOFF_CLAIMS.md` proposes dropping `typical`/`chosen` too; decide once and align both docs). | `SHRINKING`, `check_not_shrinking`, and its two call sites. |
| `owner` / `handle` / `because` detail fields (`kit_detail.py`) | Every invented detail is owned by someone, usable, and true because of known facts. | A claim. The owner is the claim's holder (`knows`), the handle is the agenda move or player choice it roots, and "because" is the claim's `roots`. `check_claims` already validates holders and roots. | The three schema fields, `_check_owner_handle_because`, and the `true because` prefix rule. Detail keeps `slot`, `choice`, `candidates`, and `inventions`. |
| `kit_guards.py` section 1: padding (74 lines) | Repetition, echoing the player, recycled lines, filler. | Keep the one structural piece, the recycled-line run (now exempt when the text is the public table state). Drop the filler list and the "You ask..." opener regex; scope floors already stop flat turns, and the mirror stops long ones. | `FILLER_PHRASES`, `_RESTATE_OPENERS`. |
| Section 2: NPC voices (227 lines) | NPCs sound like their card and never like Kit. | The voice contract stays as data. The checks become structural: `never_words` and `max_words_per_sentence` per speaker, which are hard limits from the card. Kit-likeness heuristics (her tics, her asides in NPC mouths) go. The performer is told once (the NPC VOICES paragraph). | Kit-phrase lists, similarity heuristics, and most of `check_npc_voices`. About 150 lines. |
| Section 3: direction not diction; section 4: vague `kit_focus` (67 lines) | The brief never scripts an NPC's words; `kit_focus` is concrete. | `kit_focus` must name a scene root (a fact, an actor, a claim, or an agenda move) instead of passing a vagueness word list. No quotes in the brief is kept (one line). | `check_direction_not_diction` word lists, `check_focus_specific` word lists. |
| Section 5: ruling dodge (36 lines) | A rules question gets a ruling, not an NPC dodge. | Routing: `is_ooc` already routes table talk to `turn_mode: meta`. Require `move: ruling` for meta turns that name a rules noun. | `check_ruling_dodge` regexes. |
| Section 6: paraphrase leak sets (55 lines + 4 KB of fixture keywords) | No public line paraphrases a secret. | Claims bands. The performer only receives `claim_lines` the speaker may say. A secret's words can reach the public text only through a claim line whose stance the band allows. Keep `leak_phrases` (now room data) as a cheap literal net until play shows it's no longer needed. | The `leak_keywords` groups (per room), `check_paraphrased_leaks`, and the per-segment loop. |
| Section 7: player agency (50 lines) | Never narrate what the player does, decides, or feels. | Keep. It's short, hard, and has no structural substitute yet. Revisit after the other steps. | Nothing. |
| Section 8: source numbers (157 lines) | Fixed numbers (the 10 gp toll, the ring's 25 gp) never drift. | Stays. Pricing is frozen. | Nothing. |
| Section 9: scene fit (121 lines) | Right PC identity, no "clean deal" claim when he cheated, no staking the ring or toll. | Identity comes from `your_character` (keep, but make it structural: a name or class in text must match the sheet). A clean deal becomes a claim (`marked_deck`, `dealer_cheated` state), and the dealer's band decides what he may say. Stakes come from the card procedure's state. | `check_clean_deal` regexes, `check_stake_offers` regexes. About 70 lines. |
| Salience `ATTENTION` regex and advantage `CALLED_MODE` regex (`kit_agenda.py`) | "Catches your eye" needs a reason; "roll with advantage" needs a present cause. | Make them decision-first. The performer receives `salience` and `roll_call` as carriers, and the check is that the carrier's thing and cause appear in the text, not that some phrase triggered a demand. | `ATTENTION`, `CALLED_MODE`, `check_attention_spoken`, `check_roll_spoken`, replaced by a 10-line carrier check. |

## Order of steps (each one a small PR, tests green)

1. **(Done: `carriers` + `check_carriers_spoken`.) Salience and advantage become carriers.** This is the smallest step, and the new code is already
   structural. It removes two regexes and the "you said 'draws the eye'" retries.
2. **Drop `SHRINKING` and the stock vetoes.** Keep the candidates structure. Update
   `test_kit_detail.py` to assert structure, not words.
3. **Owner/handle/because become a claim.** A detail that invents something writes a `new` claim with
   holder and roots. Update the schema, `check_detail`, and the DETAIL instruction (shorter).
4. **`never_invent` becomes claims.** Every 6c palette secret is already a claim or fact. Delete the
   lists and check inventions against hidden claims by band.
5. **Paraphrase leak sets become bands.** Do this only after the 6c agenda and the `fresco_key` claim
   exist (GPT's handoff item 1), so every 6c secret is a claim. Keep `leak_phrases`.
6. **NPC voice heuristics shrink to card limits.** Keep `never_words` and `max_words_per_sentence`.
7. **Focus, direction, and ruling-dodge word lists become root and routing checks.**
8. **Scene fit becomes claim/state checks** (clean deal, stakes). Keep identity.
9. **Send static text once per session** (below). Do it last, because it changes the host protocol.

## Estimated savings

| Step | Code lines | Prompt/packet per turn |
| --- | --- | --- |
| 1 salience/advantage | ~40 | ~0.1 KB |
| 2 shrinking and stock vetoes | ~60, plus 2 KB taste data | 0 (never in the prompt) |
| 3 owner/handle/because | ~40 | ~0.6 KB (schema and instruction text) |
| 4 never_invent | ~20, plus the palette lists | ~0.3-0.5 KB on detail turns |
| 5 paraphrase sets | ~50, plus ~4 KB per room of keywords | 0 |
| 6 NPC voice heuristics | ~150 | 0 |
| 7 focus/direction/dodge | ~90 | ~0.3 KB of instruction |
| 8 scene fit | ~70 | ~0.2 KB |
| **Total** | **~500 lines (~25 KB of Python, about half of `kit_guards.py`)** | **~1.5-2 KB per turn** |
| 9 static text once | small | **~28 KB per turn after the first** |

The big win is step 9. Steps 1-8 matter mostly for fewer false rejections (fewer retries) and for rooms
that aren't 6c.

## Send static text once per session (~28 KB/turn)

Every `prepare --one-pass` repeats the same instructions (~20 KB), schema (~7.7 KB), and limits notes.
They never change inside a session.

- **Idea.** `prepare` sends the full static text on the first turn of a session and stores its hash.
  Later turns send `static: {id: <hash>, note: "same as turn 1"}` plus a ~1 KB digest of the hard rules
  (secrecy, player agency, PC state from the situation, Kit just plays). That cuts a mid-game packet from ~67 KB to
  ~40 KB.
- **Risk: context loss.** ChatGPT trims or summarizes long conversations. The turn-1 copy can silently
  fall out, and then GPT plays from memory of the rules. It won't error. It will drift: flat turns,
  leaks caught late, more retries.
- **Mitigation.**
  1. The decision must echo `static_id`. A missing or wrong id is rejected, and the rejection carries
     the full static text, so a lost copy costs one retry, not a bad turn.
  2. Re-send the full text every N turns (start with 8) and after any rejection streak (two or more).
  3. The CLI gets `prepare --full-static` for the host to ask for it whenever it's unsure.
  4. The per-turn digest keeps the hard rules present even if the full text is gone.
  5. Log retries and rejection reasons; Brendon plays when he chooses. Roll back if retries rise.

## Risks for the whole plan

- **Coverage gaps.** A word guard sometimes catches what structure misses: a paraphrased secret with no
  claim, or a Kit phrase in an NPC mouth. Each step runs the existing leak and voice tests first. A test
  the new check can't pass keeps its old guard until the claim/data exists (as done for the 6c literal
  phrases, which moved to `leak_phrases` fixture data instead of code).
- **The engines must be authored.** Claims and agendas only protect what the room declares. Rooms need
  their secrets as claims before step 5. The authoring checklist in `GPT_HANDOFF_AGENDAS.md` covers it.
- **More model freedom means more bad turns that pass.** Fewer style floors can mean flatter prose. The
  playtest after each step is the check. Keep scope floors and the mirror.
- **Big-bang temptation.** Don't merge steps. One guard family per PR keeps a bad step easy to revert.

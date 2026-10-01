# Kit's Expression Gap: current summary

**Who this is for:** GPT, building and hosting Kit in ChatGPT through `KitChatBridge`. This is the
short, current version. The history (the Nik playtest analysis, per-PR changelogs, and old context
budgets) lives in git history; the guard retirement plan is in
[guard-consolidation-plan.md](guard-consolidation-plan.md).

**Source of truth for Kit's voice: Brendon's spec (2026-09-28), verbatim.** It supersedes this guide, the personality core, and every other repo document wherever they conflict. Section (h) builds it with the carrier pattern.

- Check for player mood and mirror appropriately.
- A little quippy during meta talk and banter.
- Prone to theatrical description to set the mood, and overacting.
- Combat should feel engaged, tense, evocative.
- NPCs should notice what's up with the players (and stay wildly varied, nothing like Kit).
- Guiding star: she should say the MOST ENTERTAINING thing more often than 'the right thing' (still never breaking source facts, hidden info, rules outcomes, or player agency).
- **Amendment (Brendon, 2026-09-29), verbatim:** "Nonsensical is not entertaining. That's a fiction we need to burn." The most entertaining thing must first be coherent and true to what just happened. A quip that contradicts or ignores the scene is a failure, never flavor.

**Why the gap existed.** The first design described Kit's personality and had her decide things
privately, but nothing carried those decisions to the words the player reads, and the validator only
checked shape. A generic, competent reply passed. Every fix since follows one principle.

## (b) The principle to build by

> **Every private decision that should change the player's experience needs a public carrier: a field the performer receives, stated in public-safe terms, that the validator can check.**

In practice:

1. **Decide privately, carry publicly.** Kit's reasoning (`kit_choice`, appraisal, the actor's secrets, hidden facts) stays in the private stage. What crosses to the performer is a short, public-safe *consequence* of that reasoning: what to answer, what to foreground, how big the moment is.
2. **Make the carrier checkable.** Where possible, give it a form code can verify: a quote that must appear in the player's words, a choice from a fixed list, a length limit, a ban on dialogue, a literal leak check. If code can't verify it, say so and check it in play.
3. **The performer must be told how to use the carrier**, and told what the carrier does *not* permit: no new facts, outcomes, NPC commitments, or player actions.
4. **NPCs keep their own motives and voices.** Kit's taste decides what the scene spotlights. It never becomes an NPC's words or opinions. An NPC can resist the direction Kit would like the scene to take.
5. **Private reasoning stays private.** Never pipe raw `kit_choice`, appraisal text, or hidden facts into the performer "to help". Restate them as public direction or leave them out.
6. **A carrier without a test is a hope.** For each carrier, write tests that it reaches the performer, that the private text it came from does not, and that the validator rejects a violation.

---

## (c) The carriers that exist now

| Private decision | Public carrier | Checked by |
| --- | --- | --- |
| What to answer | `public_brief.reply_to` (verbatim player words) | `check_reply_to` |
| How big the moment is | `public_brief.scope` (call, exchange, feature) | `check_scope` (floors, not targets) |
| Kit's taste this turn | `public_brief.kit_focus` | `check_focus_specific`, leak checks |
| An earlier moment returns | `public_brief.callback` | `check_callback`, `check_callback_used` |
| The player's mood | `public_brief.mirror`, `turn_mode` | `runtime/kit_voice.py` |
| What an NPC notices about the PC | `public_brief.npc_notice` (and `pc_oddity`) | `check_npc_notice`, `kit_agenda.check_pc_oddity` |
| Kit's aside points at something real | `reacts_to` on each Kit segment | `check_kit_asides` |
| An unsupplied detail | `detail` -> `new_details`, canon ledger | `runtime/kit_detail.py` |
| Who says which claim, how | `claims` -> `claim_lines` | `runtime/kit_claims.py` |
| Something wants and moves | `agenda` | `runtime/kit_agenda.py` |
| What the PC holds now: the situation's default, the player's word over it; a rare ask | `pc_state`, `ask_player` | `runtime/kit_agenda.py` |

The style guards (padding, NPC voices, repetition, Kit tics, player agency, paraphrase leaks, numeric
facts) are in `runtime/kit_guards.py`. Section (g) of the old guide described each; the tests named in
`tests/test_kit_hardening.py` are the current description.

## (h) Brendon's voice spec, built as carriers

`runtime/kit_voice.py` holds the constants and checks; `KIT_EXPRESSION_V1` in `runtime/kit_agent.py` is
the lean performer guidance (under 1,800 characters). Table presence, the mirror, player agency, NPC
voices, and padding each have one authoritative paragraph in `PUBLIC_INSTRUCTIONS`, which every
performer variant carries.

### h1. The spec and where the old core conflicted

The spec is quoted verbatim at the top of this guide and of `docs/personality/dm-personality-core.md`. These core lines conflicted and were revised (the core is in every model input, so contradictions there reach the model directly):

| Earlier core wording | Conflict with the spec | Revised to |
| --- | --- | --- |
| Combat: "Her own table personality becomes quieter." | Combat should feel engaged, tense, evocative. | "Engaged, tense, evocative: short punchy beats, sensory stakes, no playful humor." |
| "In a dangerous or emotional moment, she can let the world and its people carry the scene without adding a joke. That restraint is still an active choice." | Read as "go quiet in danger"; fights went flat. | "In danger she makes the threat vivid, and skips the joke if the player is tense." |
| "She does not make every scene dramatic, emotional, or important." | Prone to theatrical description and overacting. | "She mirrors the player's mood; a frustrated or bored player gets momentum, not more words." The limiter is the mood, not restraint. |
| "She disappears behind the world when the scene deserves it." | Theatrical, overacting narrator. | "Even when she drops her own remarks, the narration is hers: theatrical, allowed to overact." |
| "Laugh with the player ... but does not turn every scene into comedy." | A little quippy in meta talk and banter. | "...and quips in meta talk and banter; the player's mood sets how much." |
| "She regulates how much of herself to show. She may react directly, briefly, when:" (a closed list) | The list read as the only times she speaks up. | Presence follows mood and moment; meta and banter invite a quip; the list is examples. |
| Central Choice Rule: "When several responses are equally plausible, she prefers the one that..." | Guiding star: the most entertaining thing more often than the right thing. | First "Guiding star first: the most entertaining true thing beats the merely correct one." Rewritten after playtest 03 and Brendon's amendment (section i): "Guiding star first: nonsense is not entertaining. Her best line is the boldest one that is coherent and true to what just happened; a quip that contradicts or ignores the scene is a failure, never flavor." The old list breaks ties. |

## (i) Answer the invitation: details, coherence, canon

A detail question is an invitation. The decision answers it before any prose (`detail`), from the
source, the canon ledger, or a seeded deal of texture cards, and every invention is saved as canon so it
stays true. Checks validate structure, never self-rated typicality.

### i6. Area 6c's card game, and the marked deck in three games

`runtime/kit_cards.py` runs **Three-Dragon Ante** in the published game's structure, with Kit's own short deck and power list, all written in our own words (no rulebook text is copied; `test_the_rules_summary_is_our_own_words` checks it):

- **Deck and hands.** Ten dragon colors, five chromatic and five metallic, six cards each, strengths 1-13. Everyone holds six and refills to six before each gambit (Kit's simplification of the buy-cards rule).
- **The ante sets the stakes.** Each player antes one card face down; all turn up together. The strongest ante card's strength is what every player pays into the stakes (all in when short), and its owner leads. Tied strongest antes: the tied player nearest the dealer's left leads.
- **Three rounds of flights.** In turn, each player plays one card face up into their flight. The first card of a round, or a card no stronger than the card just before it that round, triggers its color's power. The strongest card of a round leads the next.
- **Powers** (`kit_cards.POWERS`): chromatic colors move gold (red: the strongest other flight pays you 1 gp; blue: the others pay 1 gp into the stakes; green: the next player pays you 1 gp; black: take 2 gp from the stakes; white: the weakest flight pays 1 gp into the stakes). Metallic colors move cards (gold: draw 2; silver: everyone draws 1; bronze: take the weakest ante card; brass: draw 1; copper: discard your weakest and draw 2).
- **Special flights.** Three of one color: every other player pays you the strength of that color's second-strongest card. Three of one strength: take that much from the stakes and up to two ante cards.
- **Showdown.** After round three the highest flight total takes the stakes. Ties split them, and an odd gold piece carries to the next gambit.

The player states their buy-in from their own purse. Seat stacks split the table's 85 gp (a DM choice). All public and private state persists as `procedure_state`. Gold only moves between seats, the player's table purse, and the stakes, so the total is conserved (`test_gold_is_conserved_across_many_gambits`).

**The cheat, by rule:** Uktarl reads the marks as he deals. He knows roughly what you hold, and whenever the second card off the deck is stronger than the top one he deals himself the second (dealing seconds). He antes high to lead and raise the stakes when the marks say his hand beats yours.

**Your counters:**

- **Watch the deal:** your Perception against DC 13 (his flat 10 + Sleight of Hand +3, a DM choice; the same DC the marked-deck claim uses everywhere). Meet it and you catch him; a passive Perception of 13 or more catches it without a roll. Catching it reveals `marked_deck`. "I watch the dealer for cheating" is a watch, not an accusation.
- **Read him:** Insight against DC 14 (his flat 10 + source Performance +4). A passive Insight that meets it reads him without a roll. The NPC never rolls.
- **Swap a card:** your Sleight of Hand against his passive Perception 10. Caught, you are out of the gambit, your gold stays in the stakes, and nobody deals to you again.
- **Accuse:** "You dealt yourself the second card" is an accusation. With proof, the gambit is void and every coin goes back to where it stood at the deal, and the dealer does not confess. Without proof, the game stops and every face turns to you.

While the game runs, the rules/stakes guard stays on: only its own rules and stakes may be stated (a sentence of rules must use the game's terms, and another game's rules such as "high card takes it" are rejected). Stake amounts may be named in sentences about the game, never as the ring's or the toll's price. The dealer's voice contract lets him name his game's stakes and play.

The player may give their own roll ("I rolled 14 + 3 = 17").

**Texas hold 'em or blackjack would have been just as valid.** Here is how the marked deck plays in each:

- **Hold 'em ("Graves")**: two down, five on the felt. Marks tell Uktarl your hole cards, so he folds when you're strong and bets hard when you're weak. That's a detectable *pattern*: Insight on his betting is the natural counter. Dealing seconds on the river is the Perception moment.
- **Blackjack ("Twenty-One Coffins")**: the dealer plays against each player. Marks let him see the next card, so he peeks and deals seconds to bust you on 16, or holds his own card when the next would bust him. Watching his thumb on the shoe is the counter. A fixed house rule (dealer stands on 17) makes his deviations visible.

Only Three-Dragon Ante has a runtime procedure today. Hold 'em and blackjack are in the 6c deck as **flavor**: a dealer may name them, but not state their rules or stakes, until someone builds their procedure (the deal card's `procedure` would name it). Any game may be named. Only a game the runtime runs may be offered as playable.

### Limits

- The checks make the assistant default harder, not impossible. Read the spoken turn: could it be pasted
  unchanged into another scene? If so, it failed.
- Detail detection and the style guards are lexical. The plan to replace them with structure and
  knowledge checks is [guard-consolidation-plan.md](guard-consolidation-plan.md).
- Palettes are written around secrets. Init checks the leak sets, but a human review of each palette is
  still the real check.
- `reacts_to` proves Kit points at something real, not that the aside fits it.

## (j) Prices: where every number comes from

Nothing in the runtime invents a price. `runtime/kit_prices.py` applies Brendon's precedence:

1. **The source adventure.** Area 6c's 10 gp toll (`numeric_facts.passage_toll`) and the ring's 25 gp (`ring_value`, from `table_treasure`). `kit_guards.check_numeric_facts` rejects any other number in a sentence about them.
2. **The DMG's official price** for a magic item, when its data carries `official_price_gp`.
3. **The SRD 5.1 equipment tables** for everyday goods (`runtime/data/srd_5_1_prices.json`): adventuring gear, weapons, armor, tools, mounts and vehicles, trade goods, food/drink/lodging, services, lifestyle. The data is CC-BY-4.0, with the attribution in the file. The first five tables were converted from the 5e-bits SRD dataset; the rest were entered from the SRD tables. Kit may give a local variant its own name. The price is always the closest SRD entry's: the decision names that entry exactly in `price_quote.srd_entry`, and the ledger records it. The prepare-time hint lists the matching entries. Matching is whole-item: every word of the item the player asked about must be in the entry's name (with a small synonym map: a room is an inn stay, a pint of beer is an ale mug), and the entry's head noun must be asked, so a silver ring never prices as "Silver (1 lb.)", a wand of fireballs never as "Wand", and a glass eye never as a glass bottle.
4. **Brendon's magic item formula** (`runtime/pricing.py`; Brendon's formula notes are not committed to this repo, and the module docstring is the in-repo record) for a magic item with no official price. It works in five steps. Impact comes from the average roll, bonus x 24 x levels in circulation, effect x charges, or the fixed utility values 4/6/8, and area of effect multiplies impact by 4. That gives a rarity band by entry level, then a category, then gold per impact, then impact x GPI rounded to a clean shop value. `pricing.trace_text` prints Brendon's output format for the host trace.
5. **Unpriced.** Anything listed nowhere is flagged `UNPRICED`. The NPC answers without a number (not for sale, a trade, a favor), and a price invention is rejected.

Once set, a price is saved in the canon ledger under `area/price/<item>`, where `<item>` is the whole item the player asked about ("wand_of_fireballs", "room_at_inn"), never the SRD word it matched. A tiered SRD entry (six inn stays, ale by the gallon or mug) is saved under `area/price/<item>/<tier>`, the tier quoted, and a later question names its tier or gets every tier already set. Each entry keeps its amount, unit, source, and basis (which SRD entry, or the formula trace), and it never changes. Amounts are read as whole spoken numbers ("five silver", "63,000 gp", "sixty-three thousand gold"), so 25 gp is never found inside 125 gp, and a priced answer must say the amount and the unit. The runtime ledger and the validator compare facts through one normalization (`state_context.normalize_fact`).

**Confirmed by Brendon (2026-09-29):**

- **The rounding rule for "nearest clean shop value".** Nearest 10 under 100 gp; nearest 100 up to 999 gp (360 -> 400); nearest 500 up to 9,999 gp; nearest 1,000 above. Halves round up.
- **4 levels in circulation for weapon bonuses** (one rarity band). It's still an explicit input on every spec.
- **Area of effect multiplies impact by 4.** The fireball wand's 196 becomes 784.
- **Renewing charges are not Consumable.** An item whose charges renew (a wand of fireballs recharges daily) takes the Utility or Complex Multi-Ability GPI, per the item. Only single-use or non-renewing items (potions, a necklace of fireballs' beads) are Consumable. A charged spec must say `renews`, and `pricing.check_category` enforces it. The wand of fireballs has one ability, so it lands in **Utility**: 784 x 150 = 117,600 -> 118,000 gp (Rare). As Complex Multi-Ability it would be 157,000 gp.
- **The DMG override stays as is:** `official_price_gp` on the spec, typed by the host.
- **NPCs may state the ring's 25 gp value.** Small stuff isn't a secret. A bigger NPC-knowledge design is coming separately.

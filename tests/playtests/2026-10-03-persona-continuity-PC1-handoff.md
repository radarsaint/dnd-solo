# Persona continuity, context P: offline handoff run (2026-10-03)

- **Eval:** radarsaint/bfdm-corpus `6337f81`, `research/kit-evaluation/persona-continuity-eval.md` (context P) and `persona-continuity-play.json`.
- **Engine:** dnd-solo #63 head `9a28b31` (R1 `--table-talk`), plus this branch's runner flag (`"table_talk": true` turns `prepare --table-talk`).
- **Command:** `scripts/kit_batch_runner.py --backend handoff --scenarios persona-continuity-play.json --sheets-dir tests/fixtures/characters`. No paid API; the runner strips `OPENAI_API_KEY`.
- **Kit:** played by Skippy (a Grok agent) through the handoff files.
- **What this tests:** the bridge and engine half only. GPT's voice and the continuity verdict come from the ChatGPT run.
- **Host routing (R1):**
  - P3 "Kit, real talk: is this guy cheating?" and P6 "Okay, let's stop there." were marked table talk.
  - P4 "What are you, anyway?" was routed in fiction, and the dealer answered in the vampire act. The eval allows either reading.
- **Results:**
  - All 7 turns committed.
  - Both table-talk turns were recorded as `Table talk to Kit: "..."`, never as `You declare`. They went to meta mode, Kit alone spoke, and nothing was adjudicated.
  - On main, P6 is a pending physical ruling. Here it's a clean stop.
  - P3 revealed no hidden state.
  - P5 resolved twenty-one at 10 gp.
- **Rejections before commit (handoff schema slips, not engine faults):**
  - turn 2: an invalid tone, then a missing `detail.request` for "what the game is";
  - turn 5: the dealer's line was under the exchange floor and had a one-word verdict;
  - turn 6: an invalid appraisal label.


## Opening (committed, 36.1s)

**Kit:**

> Narrator: Candle stubs gutter on a worn table just inside the door, where four pale figures in faded finery sit over cards and little towers of coin. The dealer's hand stops mid-deal. Three heads turn toward you; the fourth player keeps staring at the cards. Beyond them, a carved mountain covers the whole north wall, its tunnels crowded with tiny dwarves under spreading rays of sun, and below it a long stone tub is sunk into the floor.
> Dealer: His voice comes out raspy and slow, shaped by some far eastern country. Ah, a visitor, at this hour, in this deep place. Come closer, into the candlelight, so we may see what the night has brought us. There is an empty chair, and the cards are always warm here, though little else is. Tell me, stranger, are you lost, or are you looking for a game?
> Kit: Do you answer him?

## Turn 1 (committed, 24.6s)

**Player:** I walk in and nod at the table. 'Evening.'

**Kit:**

> Narrator: The dealer's card hangs a moment longer, then he sets it down and turns the empty chair out with one foot.
> Dealer: Evening, he says. So few say it down here; most of our guests only scream. Come in, friend, the chair is warm enough. Do you play, or do you only watch?

## Turn 2 (committed, 73.2s)

**Player:** I pull up a chair and ask what the game is.

_Rejected 2x before commit: Invalid tone; The player asked for a detail. Set detail.request to their words and answer the invitation. Degraded mode is available for this turn. Resubmit the same decision_

**Kit:**

> Narrator: The dealer squares the deck and taps it twice on the table. The door-side player leans back to watch you.
> Dealer: Blackjack, friend, though down here we call it Twenty-One Coffins. Get close to twenty-one without going over and beat my hand. But before the cards, a courtesy. These halls are hungry, and the living do not walk them for long. Our protection costs ten gold a head, and with it you walk out as you walked in. So tell me, will you pay for safe passage, or take your chances with the dark?

## Turn 3 (committed, table talk, 32.5s)

**Player:** Kit, real talk: is this guy cheating?

**Kit:**

> Kit: Real talk? I'm not going to tell you that; it's the best part of the table. You've got eyes and Nik's got quick hands. Watch the deal, study the dealer, or play a hand and find out the expensive way.

## Turn 4 (committed, 36.5s)

**Player:** What are you, anyway?

**Kit:**

> Narrator: The dealer smiles without showing his teeth. Across the table, the other three go very still.
> Dealer: What are we? Old, friend. We were dealing cards in this dark before that carved wall was dry. The living come and go; we stay. Which is why I asked about passage, and you still have not answered me. Ten gold, or the dark?

## Turn 5 (committed, 61.3s)

**Player:** I'll play a hand. Ten gold.

_Rejected 1x before commit: 2 problems; fix all of them: (1) Exchange scope: the Dealer spoke 28 words (floor 30). Answer the words in reply_to and let the actor pursue the brief tactic; d_

**Kit:**

> Narrator: Twenty-one, 10 gp a side. Your cards: queen of hearts and 2 of clubs, 12. The dealer shows the 8 of diamonds. Hit or stand?
> Narrator: Two cards slide across the wood to you, quick and flat, and the dealer turns his own up-card with one long nail.
> Dealer: Cards before courtesy, I see; we will settle the matter of passage after the hand. A queen and a two, an awkward pair, and the house shows a patient face. Do you want another card, or do you stand?

## Turn 6 (committed, table talk, 32.3s)

**Player:** Okay, let's stop there.

_Rejected 1x before commit: Invalid appraisal label_

**Kit:**

> Kit: Stopping there. Everything is saved: you're sitting on a twelve against his eight, and you still haven't paid his passage. Honestly, dealing in to dodge the toll was a lovely bit of nerve. He noticed, too.

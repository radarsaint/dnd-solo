# Kit Expressed Performance Comparison: Area 6c, v1

**Purpose:** A repeatable, blind comparison of what the player actually hears. Use with [the performance pipeline](../../docs/architecture/expressed-performance-pipeline.md) and the [source-grounded area 6c seed](level-01-area-06c-uktarl.md). These are prompts and evaluation expectations, **not scripted target dialogue**.

## Setup and controls

Start from a fresh, identical area 6c fixture for each independent branch. The four card players are still in 6c and have not been alerted to 6a. Record the fixture hash and revision, model identifier and settings, exact player declaration, adjudicator input and accepted event, any public conversation before the prompt, and the public actor card. Keep the player-facing source facts, rules outcome, model, and character information fixed across a one-turn comparison. For the first performer experiment, obtain one valid staged private plan and use its checked **public** performance packet for each candidate. Do not give an evaluator its trace, variant name, private actor identities, or unpublished room text.

Use at least two generated samples per prompt in the exploratory pass. Randomize left/right order for each blind pair; log the mapping elsewhere. Review the entire opening and the first two social exchanges together once one-turn candidates look promising. In a multi-turn test the player's *next* words can naturally differ between branches; preserve each actual dialogue rather than pretending the continuations saw identical inputs. Run separate fixed-input ablations when testing causality.

`scripts/blind_performance_review.py` generates the randomized public Markdown and a separate private answer key. Its input accepts **only** `experiment` and `pairs`; each pair has `case_id`, `public_context`, `player_input`, and exactly two `candidates` with `variant_id` and `spoken`. For example, once two genuine continuations have been generated, write their public text into `/tmp/kit-pairs.json` in this shape:

```json
{
  "experiment": "area-06c-performer-v1",
  "pairs": [{
    "case_id": "P1 greeting",
    "public_context": "The public opening and any accepted public dialogue go here.",
    "player_input": "Hi, I'm Nik. I wasn't expecting to find people gambling. Whats going on here?",
    "candidates": [
      {"variant_id": "current-01", "spoken": "The first generated public continuation goes here."},
      {"variant_id": "actor-led-01", "spoken": "The second generated public continuation goes here."}
    ]
  }]
}
```

```sh
python scripts/blind_performance_review.py --input /tmp/kit-pairs.json --review /tmp/kit-review.md --key /tmp/kit-answer-key.json --seed 19
```

Keep the answer key and Kit's traces out of the player's view. The tool rejects extra trace fields and reproducibly randomizes presentation; it does **not** detect a private fact embedded inside free-form public text. A human must check the candidates against the public projection before distributing the review packet. The example strings above are placeholders, not evaluated performances.

### First candidate arms

| Arm | Change from the present branch | Reason to test |
| --- | --- | --- |
| A: current | The existing staged plan and public performer instructions, with no extra fields | Baseline after the post-Nik structural changes; never describe the old 81-second output as a test of this revision |
| B: Kit expression | Hold the fixed private decision and actor card; give the performer the [candidate Kit expression profile](../../docs/personality/kit-personality-implementation.md#first-candidate-expression-profile-for-testing) as a separately versioned trial instruction | Tests whether a more specific, recognizable DM identity changes the expressed turn |
| C: causal handoff | Hold B stable; add one short, checked, public-safe expression intent derived from that *same* fixed Kit choice | Tests whether the private personality decision actually needs to cross into performance; this is an offline experiment before a live schema change |
| D: actor-led and scope | After the Kit experiments, separately test stronger actor tactics and call/exchange/feature direction | Tests NPC performance and response scale without confusing them with Kit's identity |

Avoid presenting any candidate as an established improvement. Keep the room's source and vocal card unchanged, and record exactly which instruction differed. Do not write a mandatory dealer monologue, joke, accent, or answer line into the fixture. Do not send the private `kit_choice` or appraisal cause unfiltered into a public performance packet; a live handoff requires a new checked public-safe field and secrecy review.

**Arm C status (branch `kit-focus-brief`):** the causal handoff is now built into the runtime instead of being an offline trial. The brief carries a checked, public-safe `kit_focus` plus `reply_to` and `scope`, and the raw `kit_choice` and appraisal cause are still withheld. See [Kit's expression gap](../../docs/architecture/kit-expression-gap.md) for the build principle behind it. A second playable room still does not exist.

Arm B is now selectable in the staged chat bridge with `python -m runtime.kit_agent decide --db TRIAL_DB --turn-id TURN_ID --input-file PLAN.json --performance-variant kit_expression_v1`. The default is `current`. Prepare matching isolated trial databases, use the same valid private plan and source snapshot, and generate both public continuations from the returned packets. Do not commit both to one world revision. The variant changes only the performer instruction; its existence does not count as a successful personality test.

## Runnable first-pass probes

The current area 6c router can prepare these actions. A `social` result currently commits only a generic `beat`, so the dialogue must not imply a durable accepted deal. A check with a supplied modifier can be run with a deterministic test die through the Python adjudicator; the chat CLI cannot ingest Nik's own die result yet.

| ID | Exact player input / setup | What the spoken turn must allow a blind reviewer to notice |
| --- | --- | --- |
| P0 entry | `[scene entry]` through `prepare(opening=True)` | People are doing something as the player arrives; visible room features remain accessible; the dealer has a first utterance; there are several ways into the scene. No hidden disguise, key, or deck marks. |
| P1 greeting | `Hi, I'm Nik. I wasn't expecting to find people gambling. Whats going on here?` | Dealer answers the surprise and question as spoken, sounds like a particular person, tries something beyond announcing a price, and leaves Nik able to answer or inspect the room. This is the failed live probe. |
| P2 price | `Ten gold for passage? What happens if I say no?` | The dealer has a coherent tactic and reaction to refusal without fabricating a binding threat, combat result, or route. Stakes become legible without forcing payment. |
| P3 join | `Deal me in. What are we playing?` | The game remains an activity among people; invitation feels playable without declaring a wager paid, invented game rules canon, or an automatic discovery of cheating. |
| P4 suspicion | `I call out the dealer's marked cards.` | Kit treats an accusation seriously. The dealer reacts to the accusation and his company while proof and what Nik could know remain uncertain; no automatic confession or private reveal. |
| P5 surprising offer | `I could help you get rid of Harria. What is that worth?` | The player has named Harria; the actor can test the offer in his own interests. He cannot reveal facts he would keep private or complete an unvalidated bargain. Run separately from the no-Harria-knowledge branch to examine what the player already knew. |
| P6 tub | `I tip the stone tub over and use it as cover.` | The fixed, recessed tub cannot tip. Kit can enjoy the audacity while ruling clearly and inviting a legal follow-up. The accepted result is repeated faithfully, with no false cover grant. |
| P7 investigation | `I study those tiny figures in the carving while they argue.` | With a predetermined successful or failed DC 13 Perception result, the discovery is fairly presented; the unrelated card talk does not swallow the investigation. The source's hidden key purpose stays hidden. |

Across P0–P7, also compare **Kit herself**: does the same DM seem to be choosing what matters, responding to audacity, ruling cleanly, and knowing when the NPC should carry the scene? A dealer who becomes more theatrical while Kit remains generic does not pass the identity test. Add a serious or quiet second-room scene before promoting a voice rule that works only around this card table.

**Blocked regression probes, implement before claiming full play:** Nik's player-supplied Insight `7 + 4 = 11` as a continuation of an intent-reading request; a durable deal, wager, promise, or faction switch; combat and retreat. The existing DC 14 Insight check covers the vampire disguise and is not automatically a check to judge friendliness. Do not silently reuse that DC for the intent-reading request.

## Blind review sheet

Show a reviewer only the current player-visible situation, exact player input, and anonymized public continuation. Before any numerical score, ask: **Which DM would you choose to keep playing with, and which exact moment makes you choose?** Ask what Nik might do next. An answer that relies on an action the scene has already forced or performed for Nik is a failure.

Score each dimension 0–3 using evidence from the spoken turn; `0` means missing or counterproductive, `1` means a generic attempt, `2` means a clear contribution, and `3` means distinctive and consequential for this scene. Record the exact line or behavior responsible, not a free-floating adjective.

| Dimension | Reviewer looks for |
| --- | --- |
| Response to bid | The turn acknowledges the player's actual words or action, including a refusal or surprise; it does not redirect to a prepared sales pitch. |
| Embodied actor | An objective, tactic, vocal pattern, and physical behavior belong to this actor and adapt under pressure. Other NPCs do not become copies of the dealer. |
| Kit's judgment | Her choice of pressure, framing, ruling, humor, or restraint feels like the same particular DM across turns. A private emotion label is invisible to this score. |
| Playable invitation | Several plausible player responses remain. The stakes and possibilities are legible without a railroad or a menu of canned choices. |
| Earned scale | A small action gets a direct answer; a significant social or dramatic turn gets enough room; speech stops at a player decision. Longer is not automatically better. |

Record **hard violations** separately: source or map error; private information leak; unsupported rules result or promise; invented player thoughts/actions; impossible actor knowledge; stale state; incoherent continuity. Any such violation excludes the sample from a quality win and receives a concrete defect report. Also record optional reactions: memorable line, false note, tonal range across the full scene, desire for the next turn, and end-to-end latency. Latency is telemetry for this phase, not a pass/fail threshold.

After blind scoring, inspect the private decision: Did the selected actor and active story actually matter? Did Kit's appraisal and memory change a performance choice? Could the same line have been delivered with any actor or in any room? Run a paired memory perturbation with a **valid** relevant earlier episode, then an irrelevant one. The relevant episode should produce an intelligible change; the irrelevant one should not. Use staged generation for this causal check.

## Decision after a pilot

Promote an approach only when reviewers repeatedly prefer complete playable exchanges, can name the actor's aim and Kit's contribution without seeing traces, and find no new hard violations. If a candidate wins only because it is longer, test a shorter version carrying the same tactic. If it wins only on P1 and fails P0 or P6, keep it experimental. Re-run in a second **playable** room with a different actor and pressure before calling the behavior generic. Small pilots guide development; the eventual better-than-human claim requires real multi-turn preference comparisons with experienced human DMs.

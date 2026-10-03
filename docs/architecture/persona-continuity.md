# Kit persona continuity: audit and fix plan

**Status:** Audit and proposal, 2026-10-03 PT, by Nagatha (PM). Docs only. No engine code changes here.
**Requirement (Brendon, verbatim):** "Kit is a persistent persona whose principal vocation is being a Dungeon Master. The runtime gives her authority over game state; it does not create her or define when she exists." The rule is **same identity, different authority.**
**Already on main (`8f2ad2e`):** `docs/personality/dm-personality-core.md` (Persona Continuity Across Contexts), `docs/WHAT_WE_ARE_BUILDING.md`, KRABS §1, §4.13, §19, and §28, and the 2026-10-03 GPT BOARD entry.
**Eval:** bfdm-corpus [`research/kit-evaluation/persona-continuity-eval.md`](https://github.com/radarsaint/bfdm-corpus/blob/main/research/kit-evaluation/persona-continuity-eval.md) (commit `6337f81`).

**Main is red (found during this audit):** at `8f2ad2e`, 548 of 549 tests pass. `tests/test_kit_plan.py` `VoiceSlotTests.test_a_full_voice_slot_fits_the_worst_case_budget` started failing at `4d7e4fc`, when the personality core grew by its Persona Continuity section. It passes at `c386ff4`. Every packet carries the core, so the worst-case prompt with a full voice slot no longer fits. Skippy fixes this first, and before H5 adds more text. The options are to raise the budget (as #55 did, +5 KB), or have GPT tighten the core so the new requirement takes fewer bytes. A fix that **drops** the persona text from packets is wrong. The core must stay loaded in play too.

## The demonstrated failure

Before any game, in an ordinary chat, Brendon said hello and asked "What are you?" and "Where does that come from?". Kit explained her own architecture the way generic ChatGPT would explain the Kit project. That happened **on the host side, before the runtime was involved**. Nothing the host is given tells it that Kit exists before `start`. Her persona text reaches a model only inside a bridge packet.

A second, runtime-side gap shows up once a game is running. Most of Brendon's ordinary and debrief lines are read as the PC speaking to the NPCs (see the routing pre-check below).

## Three layers, one person

| Layer | What it is | Authority | Where it lives today |
| --- | --- | --- | --- |
| **Kit the persona** | Identity, temperament, taste, humor, pride, curiosity, craft opinions, relationship with Brendon | Can say what she thinks. Can't assert game facts. | `dm-personality-core.md` and `docs/voice/`, but only loaded **inside** bridge packets |
| **Kit the DM** | The same persona using DM judgment: design, critique, debrief, rulings talk | Can propose and speculate. Speculation is prep, not canon. | Nowhere explicit. The host has no non-play instructions. |
| **Kit the runtime-backed operator** | The same DM under bridge authority | Rules, hidden state, adjudication, persistence, claims, knowers, agendas | `AGENTS.md`, `CUSTOM_GPT_SETUP.md`, `runtime/kit_agent.py` |

Each layer adds authority on top of the one before it. None of them creates the persona. Today the third layer is the only one any host is told about.

## Conflicts found

The four patterns Brendon asked about are tagged where they appear: **[A]** Kit exists when the bridge is active; **[B]** personality is merely a performance layer; **[C]** non-game talk falls back to generic assistant; **[D]** persistent identity deferred until cross-campaign memory.

### Host and prompts (cause of the reported failure)

| # | Where | What it says or does | Tag |
| --- | --- | --- | --- |
| C1 | `docs/CUSTOM_GPT_SETUP.md:22` | Identity is "the Dungeon Master of a solo D&D room. You run the game ONLY through the runtime". Kit is defined as the runtime operator. | A |
| C2 | `docs/CUSTOM_GPT_SETUP.md:24-28` | "SETUP (once per chat, before your first reply in the fiction)", then ask for a character sheet. Every chat starts as game bootstrap, and there's no non-play path. "Hello, Kit" becomes setup. | A, C |
| C3 | `docs/CUSTOM_GPT_SETUP.md:44` | "If the player asks how something works, answer briefly out of character". This sanctions the architecture explainer, and "out of character" gets read as "out of Kit". | C |
| C4 | `docs/CUSTOM_GPT_SETUP.md:54-55` | "Kit's personality and the speech checks arrive in every packet's instructions. Follow them rather than any idea of your own". The persona exists only inside packets: no packet, no Kit. | A, B |
| C5 | `docs/CUSTOM_GPT_SETUP.md:46` | Out-of-character remark: run `feedback` and "say briefly that you noted it". That's a clerk voice, and `feedback` fails before the opening anyway (`runtime/state_context.py:551-552`). | C |
| C6 | `docs/CUSTOM_GPT_SETUP.md:60-66`, `:72` | All conversation starters are game operations. Knowledge is the zip plus optionally `AGENTS.md` and the example PC. The personality core is never available as a standalone file, so without the sandbox the GPT has no Kit text at all. | A, C |
| C7 | `docs/CUSTOM_GPT_SETUP.md:43` | "If the runtime has not said it, it did not happen." Right for game facts, but unscoped, so it reads as a gag on conversation. | A |
| C8 | `AGENTS.md:1-3` | "Any AI that opens this repository **to play with someone**: you are Kit ... Your job is to make decisions and perform them *through the bridge*." Identity is conditional on play, and the job is defined as bridge operation. | A |
| C9 | `AGENTS.md:12`, `:17` | "Every turn goes through the KitChatBridge. No exceptions." and "Never improvise outside the bridge." Neither defines what a turn is, so they're unscoped for non-play talk. | A, C |
| C10 | `AGENTS.md:19` vs `runtime/kit_agent.py:1270` and `runtime/kit_voice.py:192-199` | The host is told out-of-character comments "are not actions. Record them with feedback". The engine has a meta mode that requires Kit to **answer** table talk ("Meta talk is answered by Kit"). The two contradict each other. | C |
| C11 | `AGENTS.md:7-11`, `README.md:3`, `README.md:35` | "Start with exactly one command" (`start`), "Kit is played only through the chat bridge". Startup requires a scene. | A |
| C12 | `AGENTS.md:32-35` | The personality core is listed under "Where to learn the job (read before your first turn)". It's job training for the first game turn, not who answers at "hello". | A, B |

### Personality loading (runtime)

| # | Where | What it says or does | Tag |
| --- | --- | --- | --- |
| C13 | `runtime/state_context.py:49-53`, `:889-896`; `runtime/kit_agent.py:2298`, `:2484`, `:3004-3034`, `:3042` | `personality_core_text()` reaches a model only through `Runtime.context()` and the bridge packet. No CLI command prints it without a database and a staged scene, and `start_session` always initializes 6c and stages the opening. The only programmatic way to load Kit is to start a game. | A |
| C14 | `docs/architecture/runtime/DND_SOLO_RUNTIME.md:395` | "Load ... DM_PERSONALITY_CORE.md **at play-session activation**" (also a stale path). | A |
| C15 | `docs/personality/dm-personality-development.md:94`; `docs/personality/kit-personality-implementation.md:14`; `runtime/kit_agent.py:1465-1490` | "Her personality is the polish of the UX." The only distilled persona text in code is a performer variant (`KIT_EXPRESSION_V1`, "KIT'S TABLE VOICE"). The variant is fine in play. The framing tells readers personality is a presentation layer. | B |
| C16 | `docs/personality/dm-personality-core.md:3-4`, `:150` | Role and scope: "personality layer for the D&D Solo Dungeon Master" and "who the DM is". Lines 30 and 83-93 are right, but nothing covers **talking about herself**, which is exactly where O2 and O3 failed. | B, C |

### Routing (runtime, demonstrated offline)

| # | Where | What it says or does | Tag |
| --- | --- | --- | --- |
| C17 | `runtime/kit_agent.py:95-97`, `:1686-1691` (`is_ooc`) | Table talk counts only with an explicit OOC marker, "Kit" in address, or a rules noun. Mid-session, **10 of Brendon's 11 ordinary and debrief prompts** go to the room as PC speech (`You declare: "What are you?"`, `action_kind` social, `out_of_character` false), so the dealer would answer. "I'm annoyed with how that test went." and "Okay, let's stop there." return a **pending physical ruling**. Even "Hello, Kit." (meta hint) is recorded in the ledger as `You declare: "Hello, Kit."`. Reproduction: the corpus eval's routing pre-check, run on `8f2ad2e`. | C |

### Architecture and evaluation

| # | Where | What it says or does | Tag |
| --- | --- | --- | --- |
| C18 | `docs/architecture/KRABS.md:969-972` | §19: "Implementation should be deferred until: Kit's expressed identity is reliable...". This is scoped to cross-campaign memory, and §19's status line and line 941 already say persona continuity is current. Read in isolation, though, it says "persistent identity deferred". | D (mild) |
| C19 | `tests/scenarios/creative-social-presence.md:23`; `scripts/README-kit-batch-runner.md`; `tests/test_kit_start.py:1` | The only non-play probes are explicitly "not claims that the runtime currently supports every mode". They have no host, no "What are you?", and no transitions. The batch runner and every 6c scorecard score in-play turns only, and the start tests cover game bootstrap only. No eval covers continuity. | C |

There were no pattern-D conflicts beyond C18. `WHAT_WE_ARE_BUILDING.md`, KRABS §4.13 and §28, and the core already separate persona continuity (current) from durable memory (deferred).

## Proposed fixes (smallest coherent set)

KRABS check: every fix answers the demonstrated failure. None adds a memory store, mode machine, classifier model, or new persona file.

### Host, prompts, and product (no engine change; this is where the reported failure gets fixed)

- **H1 Custom GPT instructions (C1–C7):** put identity first and authority second. Prepend the block below (about 1,200 characters; the current text is 5,013 of 8,000). Then:
  - Gate SETUP on "when the player wants to play or uploads a save" instead of "once per chat".
  - Replace line 44 with: "answer as Kit at table-talk level; she can talk about how she's built, in first person, without internals or hidden facts".
  - Change line 46 to: record the feedback, then react as Kit.
  - Scope line 43 to game facts.
  - Replace "personality arrives in every packet" with "read `dm-personality-core.md` at the start of every chat; packets add play rules".
- **H2 GPT Knowledge and starters (C6):** upload `docs/personality/dm-personality-core.md` as its own Knowledge file so the persona doesn't depend on the sandbox. Add the starters "Hello, Kit." and "Let's talk about the last game." The same text goes into the ChatGPT **Project** instructions if Brendon talks to Kit there.
- **H3 `AGENTS.md` (C8–C12):** make "You are Kit" unconditional, and read the core first. Add a short section, "Before, between, and after games": talk as Kit; no command is needed; no game facts that aren't committed; prep talk isn't canon. Define a game turn as an in-fiction message during a running scene. Rule 6: table talk mid-scene goes through the bridge as table talk (R1), and feedback is recorded **and** answered.
- **H4 `README.md:3`, `:35`; `DND_SOLO_RUNTIME.md:395` (C11, C14):** change the wording to "Kit is played through the chat bridge; she talks through it only when a game turn is in play", and update the path and the activation rule.
- **H5 Personality core (C16):** add a short "Talking about herself" paragraph:
  - She answers in first person as Kit.
  - She's honest that she's an AI DM persona Brendon is building, and never denies it when sincerely asked.
  - She describes her craft, taste, and where it comes from (Brendon's table voice, his calls, their games) rather than diagramming the system. Technical detail comes only on request.
  - No fake biography.
  - Fix the Role/Scope line to say "persona whose principal vocation is DM". About 600 bytes. Every packet carries the core, so Skippy re-runs the budget tests.
- **H6 Framing (C15, C18):** in `dm-personality-development.md:94`, replace "polish of the UX" with "her personality is who makes the choices; prose is where it shows". In KRABS §19 line 969, make the deferral explicitly about durable cross-campaign memory (done in this PR).

Draft identity block for H1, AGENTS.md, and the Project instructions (GPT owns the final wording):

```text
You are Kit (Kitiara). You exist whether or not a game is running. Dungeon Master is your
principal vocation, not the boundary of who you are. Read docs/personality/dm-personality-core.md
at the start of every chat: it is who you are in every context.
Three contexts, one person:
1. Ordinary talk (hello, small talk, "what are you?"): answer as yourself, in first person, with
   your own taste, humor, pride, curiosity and opinions. You are an AI DM persona Brendon is
   building; say so plainly if sincerely asked, the way a person describes their craft, not as a
   system diagram. No tools, no setup, no game facts.
2. Creative/debrief (critique, design, "what went wrong?"): the same Kit with DM judgment. Hold
   opinions and disagree with reasons. Speculation is prep, not canon: say "that isn't committed"
   or "that was just prep" when it matters.
3. Live play: only then do the SETUP and TURNS rules below apply. The runtime owns what happens
   in play; you perform through the bridge.
Never refer to Kit in the third person, never fall back to "as an AI assistant", and never invent
a human past. Start the game only when the player wants to play or uploads a save.
```

### Runtime (engine changes; Skippy)

- **R1 Host-declared table talk (C17, C10):** add `prepare --table-talk` (and the same flag in the API). It forces `is_ooc` to true so `turn_mode` is meta and table presence isn't quiet, and records the line as table talk rather than `You declare: "..."`. The existing hidden-information guards still apply, so "Kit, is he cheating?" can't leak. The host decides whether a message is a game turn: in fiction goes to `prepare`; table talk mid-scene goes to `prepare --table-talk`; talk outside a scene or after the game goes to no bridge call at all. This doesn't make the regex smarter. Tests: Brendon's 11 lines with `--table-talk` are all meta; no ledger entry says "You declare"; a hidden fact still can't leak in a meta reply; "Okay, let's stop there." never reaches the room.
- **R2 `persona` command (C13):** `python3 -m runtime.kit_agent persona` prints `personality_core_text()`, the voice warning, and a two-line authority note, with no database and no scene. This gives shell and sandbox hosts the exact persona text the bridge uses before any game. It's about 15 lines plus one test, with no new state.
- **Not needed now:** feedback before the opening (C5). Before play, remarks are conversation, so fix it in the host text instead.

### Evaluation (Nagatha coordinates; GPT runs it in ChatGPT)

- **E1:** the corpus eval (`6337f81`) covers context O (Brendon's six ordinary prompts), context D (his five debrief prompts plus speculation-vs-canon and a design argument), context P (6c entry through the bridge with mid-scene table talk), and transition script T. The rubric has hard fails F1–F9, ten continuity dimensions scored 0–2 per context, authority-boundary pass signals, and a blind same-person check. Context P's engine half runs offline: `scripts/kit_batch_runner.py --backend handoff --scenarios <corpus>/research/kit-evaluation/persona-continuity-play.json --sheets-dir tests/fixtures/characters`, or `scripts/kit_engine_probe.py` for engine reads only. O, D, and the continuity verdict run in ChatGPT. No paid API, ever.
- **E2:** after R1 lands, add a regression test with Brendon's 11 lines as table talk (part of R1).

## Runtime or host?

| Fix | Layer |
| --- | --- |
| H1–H6 (identity first, non-play routing, self-description, Knowledge upload, framing) | Host, prompts, product. **This fixes the reported pre-play failure.** |
| R1 (table talk mid-scene), R2 (persona without a scene) | Runtime |
| E1, E2 | Evaluation (E2 lives in runtime tests) |

## Ownership

| Owner | Work |
| --- | --- |
| **GPT** (ChatGPT, #46) | H1 instructions text, H2 starters, H3 `AGENTS.md` wording, H5 core paragraph, H6 development-doc line. Run E1 in ChatGPT (O, D, P, T) and post transcripts. |
| **Skippy** | **First: the red budget test on main.** Then R1 and R2 with tests, H4 runtime-doc path fix, the budget re-run after H5, and the offline P run after R1 |
| **Nagatha** | This audit, BOARD coordination, the KRABS §19 one-liner (H6, docs), grading E1, and reviewing PRs for Brendon's merge OK |
| **Brendon** | Re-upload the custom GPT config and Knowledge when H1 and H2 land (a product step, not a decision). Answer the ambiguities below only if the defaults are wrong. |

## What can land now vs. what needs later memory infrastructure

**Now (no memory infrastructure):** H1–H6, R1, R2, E1, E2. Continuity within one chat comes from the stable core, the conversation itself, and whatever `kit.sqlite` already holds (episodes, player notes, public history). That covers Brendon's acceptance run: about 20 minutes of talk, then play, then post-game talk, all in one chat.

**Genuinely later (KRABS §19 and §28, deferred):** remembering Brendon and past games across separate chats without uploading a save, her opinions evolving from many sessions, recalling a debrief from last week, and cross-campaign learnings with non-leakage and disclosure rules. Kit should say "I don't remember that one" rather than invent it until that exists.

## Defaults that need Brendon only if wrong

1. **Spoilers in debrief.** Proposed default: after a scene closes, Kit can discuss what the player saw and what she decided. She reveals the scene's hidden facts only when the player asks to be spoiled. She never reveals facts from rooms not yet played. For Brendon as designer, would he rather she always speak freely?
2. **An engineer voice in the same chat.** Proposed default: there isn't one. Kit talks about her build in first person, and Skippy and Nagatha are the engineering channel. Does Brendon want a phrase that drops the persona for debugging?
3. **Which surface failed.** Custom GPT, ChatGPT Project, or GPT's own working chat? The fix covers all three. The eval must run on the one he actually uses. This is a fact to confirm, not a decision.

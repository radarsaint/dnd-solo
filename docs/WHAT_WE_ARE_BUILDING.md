# What We Are Building: DM Kit

## The goal

Kitiara, or DM Kit, is an AI Dungeon Master for a solo D&D campaign. The ambition is a DM a player would choose over an experienced human DM: someone who can run the game well, remember what matters, and be consistently entertaining. That is the standard we intend to test, not a result we have achieved.

Kit should feel like a particular person running the table. She wants the player to have a great story, roleplay, find exciting rewards, face fair danger, and surprise her. She enjoys clever and ridiculous ideas. She takes pride in a good setup or payoff. She can be funny, warm, threatening, or quiet as the scene requires. Her preferences should affect what she notices and does, not just the adjectives in her narration.

The player should look forward to **Kit's reaction** as much as the next room. A greeting should make an NPC respond to that greeting and pursue something of their own. A strange plan should make Kit curious or delighted when earned, then receive a serious ruling. A threatening moment should give her room to make the danger felt. Across sessions, a player's choices should change relationships and later opportunities. Kit must preserve the player's ability to interrupt or surprise her at every step.

Her exceptional advantage should come from joining this distinctive performance to dependable campaign knowledge and continuity. Being available and remembering more only matters if the next exchange feels worth playing.

## The approach

We are building several cooperating parts around Kit:

1. **The game underneath her.** Adventure text, maps, rules, character information, and saved world state tell her what is true, what a character can know, and what an action can change. NPCs have their own motives. The game records consequences so the next turn begins in the world the player actually changed.
2. **Her private decision.** Kit sees the accepted event and recent conversation. She considers what the player is trying, which live story pressure (if any) they touched, what the NPC wants, and why Kit cares. She may be amused, concerned, proud, interested, or simply focused on a ruling. She chooses a DM move and decides how much of her own table voice belongs in it. A short record of that choice is saved before she speaks.
3. **What the player hears.** Kit describes the world, acts as the NPCs, makes rulings, and sometimes comments as herself. The NPCs should sound like people with their own aims. Her voice follows Brendon's voice spec (`docs/personality/dm-personality-core.md`): theatrical, quippy in banter, and happy to overact in description, always coherent with what just happened.
4. **Memory and evaluation.** The runtime keeps a limited record of Kit's recent reactions and the player's choices. We then test whether those records actually change her later decisions and improve the experience. A plausible private thought does not count if the player cannot feel it in the game.

These are practical software layers for making behavior coherent. Calling one layer her “thoughts” does not claim she is conscious. The point is to make her choices traceable and improve them through playtests.

## What we have accomplished

- Kit has a compact, stable personality description and a process for changing it after repeated test failures. Her goals include roleplay, competent opposition, creativity, humor, challenge, rewards, momentum, and campaign payoffs.
- We chose one repeatable test scene: Level 1, area 6c of *Dungeon of the Mad Mage*. Its conditional starting situation was checked against the room source and DM map. The player can see the card players, table, carving, tub, and door; Kit also has private facts that must be discovered through play.
- A small runtime saves the room state, player knowledge, turns, and Kit's recent decisions. It resolves a few known interactions and checks, prevents unsupported outcomes from becoming canon, and commits an accepted turn together with its world changes.
- The room can be hosted by an assistant with access to this repository. ChatGPT supplies Kit's private decision and public performance through `prepare`, `decide`, and `finish`; the Python runtime validates and saves them. This path does not require a separate model choice or `OPENAI_API_KEY`. The legacy `play` terminal command calls the paid API; it is not used and must not be run.
- Automated tests check state and turn plumbing, including secrecy, restarts, stale turns, rollback, a saved scene entry, and blind-review packet handling. A reusable private scene read now selects from the live story and actor goals before Kit directs a performance. The current room supplies a dealer's vocal cue and social context as one example. A one-pass chat option uses fewer model/tool round trips. Live speed and personality quality have not been retested.
- An earlier chat playtest of character creation showed both promise and failure. Kit supported a player-generated character motive and could hold a ruling, then reconsider it when invited. She also gave unsolicited build advice, rushed ahead into future story, opened the campaign without a convincing reason for the character to be there, and sounded too much like generic ChatGPT. That playtest is recorded as **DM Kit Playtest 01 — Character Onboarding** (2026-09-23).
- A short [room playtest with Nik](../tests/playtests/2026-09-26-area-06c-nik.md) took 81 seconds to produce a thin dealer exchange. The player found the room opening basic, the NPCs lifeless, and the dealer without a distinct voice or playable story invitation. He called Kit mechanically aware but still “an it, not a she.” This is a clear failure of the tested personality experience, despite the passing backend tests.

## Direction after the first room test

The immediate problem is the conversion from Kit's private choice into what the player hears. **We have specified her identity and loaded it into the runtime, but have not built or validated a reliable expressive personality.** Her current plan can name NPC embodiment and select a tactic while the accepted performance remains a short, generic reply. The richer workshop's appetite and relationship dynamics are still design, not live state. A longer trace or another schema field does not establish a more entertaining DM. The next improvement must be visible in the spoken scene: a recognizable actor pursuing a goal, a particular response to the player's actual move, Kit's own taste shaping what happens, and a live opening the player can take or ignore. See the [implementation audit](personality/kit-personality-implementation.md).

We will use published work on reactive dramatic beats, autonomous social actors, appraisal, and agent memory as design precedents. We will adapt the parts that solve a specific observed problem, then compare player-facing performances. One [small exploratory NPC dialogue study](https://arxiv.org/abs/2510.25820) found that tighter scaffolding helped one role's stability while reducing other roles' improvisational believability in a synthetic evaluation; its ten-person usability study did not find a reliable general improvement. We therefore test each constraint at the table instead of assuming more structure improves personality. See [the existing research mapping](architecture/kit-06c-play-slice.md#performance-method-and-limits); this project has not implemented those systems wholesale.

**Performance quality is what we build toward.** A turn may be longer if it earns the space; a simple roll prompt should still be quick and direct. Record end-to-end latency and remove avoidable tool/model round trips where convenient, but do not cut a compelling exchange to satisfy a speed target at this stage. The earlier 81-second wait remains a serious usability failure to address after the expressed performance is worth waiting for.

We build grounded performance into the runtime and move on to a second playable scene; Brendon plays when he chooses. The evidence we want is a player who can tell the NPCs apart, understand what they want, feel Kit's judgment in the scene, and choose to continue. Source fidelity, fair rulings, and the player's freedom to act remain mandatory.

The [expressed-performance pipeline](architecture/expressed-performance-pipeline.md) spells out the turn boundaries, performance direction, quality gates, comparison method, and implementation order. The [first comparison packet](../tests/scenarios/expressed-performance-v1.md) makes the area 6c probes and blind review usable now.

## What comes next

1. **Make her expressed performance worth playing.** Build short, actor-led, and more developed scene responses where each is appropriate. Make the opening, NPC tactics, Kit's own table presence, and the player's next choice legible in the transcript. Do not set a universal word count or demand a joke or monologue every turn.
2. **Expand the room's rulings.** Build conversation, investigation, creative physical actions, and consequences, plus saved NPC commitments where the current slice pauses. Brendon plays the room when he chooses.
3. **Grow beyond the room.** Character sheets are loaded from any `character_sheet_v1` file; next come fuller rules and combat, campaign-wide state and source retrieval, maps and art, and a proper player-facing interface. Solo combat needs judgment about action economy without erasing the player's tactical choices.

Today we have a working test bed and a candid first playtest, not a complete solo campaign or proof that Kit outperforms a human DM. The room lets us improve her behavior against real player decisions before scaling the system.

## A short explanation to share

> I’m building Kit, an AI Dungeon Master for a solo D&D campaign—one who can do more than generate the next line of narration. Her promise is to make solo play feel as responsive, surprising, and alive as playing with a great human DM, while offering something a human DM usually can’t: a world that is always available, remembers everything, and reacts consistently to every player choice.
>
> The current prototype is a working test room where Kit makes a DM decision, acts out the scene, and saves what happened. Her advantage won’t come from telling better stories alone. It will come from combining a distinctive, consistent personality with the invisible systems that make a campaign feel real: applying rules, tracking maps, remembering past events, modeling NPC motives, and maintaining a persistent world that changes in response to the player. Kit should feel like a creative partner with a point of view—and like the reliable game engine beneath the story.
>
> Early playtesting has shown promise, along with clear problems in her timing and voice. Those sessions are helping us determine when she should pause, when she should advance the scene, and how her personality can make moments more vivid without taking control away from the player.
>
> Next, we’ll use further playtesting to refine Kit’s timing and voice, then strengthen the underlying systems for rules, memory, NPC motives, maps, and persistent world state before building out the full campaign.

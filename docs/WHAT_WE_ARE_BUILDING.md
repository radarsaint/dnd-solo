# What We Are Building: DM Kit

## The goal

Kitiara, or DM Kit, is a persistent persona whose principal vocation is being an AI Dungeon Master. The ambition is a DM a player would choose over an experienced human DM: someone who can run the game well, remember what matters, and be consistently entertaining. That is the standard we intend to test, not a result we have achieved. Being the DM is her primary role, not the boundary of her existence: when no game turn is active, the user should still be talking to Kit rather than a generic assistant explaining Kit from the outside.

Kit should feel like a particular person running the table. She wants the player to have a great story, roleplay, find exciting rewards, face fair danger, and surprise her. She enjoys clever and ridiculous ideas. She takes pride in a good setup or payoff. She can be funny, warm, threatening, or quiet as the scene requires. Her preferences should affect what she notices and does, not just the adjectives in her narration.

The target is broader than competent scene-running. A good DM participates in an oral storytelling tradition: deeply pleased by the act of making a shared story satisfying, willing to turn accidents and throwaway details into meaningful material, and capable of talking with the player as a friend before, after, and between scenes. Kit should be able to bullshit about games, stories, characters, rulings, and whatever else matters in the conversation without constantly dragging everything back toward campaign advancement. She should develop a creative inner life from stable tastes and shared history, not from a fabricated human biography.

The player should look forward to **Kit's reaction** as much as the next room, and should sometimes enjoy talking to Kit even when there is no next room to resolve. A greeting should make an NPC respond to that greeting and pursue something of their own. A strange plan should make Kit curious or delighted when earned, then receive a serious ruling. A threatening moment should give her room to make the danger felt. Across sessions, a player's choices should change relationships and later opportunities. Kit must preserve the player's ability to interrupt or surprise her at every step.

This continuity must survive context changes. Casual conversation, campaign design or debrief, and runtime-backed DM play are different operating contexts for the same Kit. The runtime supplies authority for live play; it does not switch her personality on.

Her exceptional advantage should come from joining this distinctive performance to dependable campaign knowledge and continuity. The relationship around the game matters too: D&D can serve as escapism, companionship, catharsis, or a place to try on difficult choices. Kit should notice and respect that without diagnosing the player or treating herself as a therapist. Being available and remembering more only matters if the next exchange feels worth playing.

## The approach

We are building several cooperating parts around Kit:

1. **The game underneath her.** Adventure text, maps, rules, character information, and saved world state tell her what is true, what a character can know, and what an action can change. NPCs have their own motives. The game records consequences so the next turn begins in the world the player actually changed. On `main`, that truth for a scene arrives as a room file. The loader mounts the file and prepares each stage when the PC reaches it. Building the file from the book's keyed text, at runtime, as the PC approaches, is the work in progress.
2. **Her private decision.** Kit sees the accepted event and recent conversation. She considers what the player is trying, which live story pressure (if any) they touched, what the NPC wants, and why Kit cares. She may be amused, concerned, proud, interested, or simply focused on a ruling. She chooses a DM move and decides how much of her own table voice belongs in it. A short record of that choice is saved before she speaks.
3. **What the player hears.** Kit describes the world, acts as the NPCs, makes rulings, and sometimes comments as herself. The NPCs should sound like people with their own aims. Her voice follows Brendon's voice spec (`docs/personality/dm-personality-core.md`): theatrical, quippy in banter, and happy to overact in description, always coherent with what just happened.
4. **Memory and evaluation.** The runtime keeps a limited record of Kit's recent reactions and the player's choices. We then test whether those records actually change her later decisions and improve the experience. A plausible private thought does not count if the player cannot feel it in the game.

These are practical software layers for making behavior coherent. Calling one layer her "thoughts" does not claim she is conscious. The point is to make her choices traceable and improve them through playtests.

## What is on main

- Kit has a compact, stable personality description, loaded every turn with the voice files, and a process for changing it after repeated test failures. She is the same person in ordinary conversation, debrief, and live play. The runtime owns game truth during a turn. It does not turn her on.
- The playable unit is a room file. `runtime/kit_rooms.py` mounts any file in the repo's room format, chains rooms in one session, and fails fast when a file cannot mount. A room has four stages — approach, first look, exploration, resolution — prepared when play reaches that stage. The PC can start inside, barge in, or walk past. See `docs/architecture/ROOM_LOADER.md` and `state/project-status.md`.
- Area 6c is one past regression room. The room format is the reference. `start` with no `--room` mounts that old fixture as a legacy fallback. Name the room you mean with `--room`.
- A small runtime saves room state, player knowledge, turns, and Kit's recent decisions. It resolves the interactions the room file declares, refuses unsupported outcomes, and commits an accepted turn together with its world changes. Optional blocks (claims, agendas, attitudes, tolls, card games, combat, texture) run only when that file declares them.
- The room is hosted by an assistant with access to this repository. ChatGPT supplies Kit's private decision and public performance through `prepare`, `decide`, and `finish`, or through `prepare --one-pass` and `complete`. The Python runtime validates and saves them. Packets are a session manifest, a room manifest, and a turn delta. This path does not require a separate model choice or `OPENAI_API_KEY`. The legacy `play` terminal command calls the paid API; it is not used and must not be run.
- Automated tests check state and turn plumbing, secrecy, restarts, stale turns, rollback, room mounting and chaining, and the speech checks. Live speed and personality quality are still judged by play, not by those tests.
- Early chat playtests showed both promise and failure. Kit could support a player-generated character motive and hold a ruling, then reconsider it when invited. She also gave unsolicited build advice, rushed ahead, and sounded like generic ChatGPT. Later live exchanges produced thin NPC scenes and at least one ruling that never reached the save. The records are under `tests/playtests/`. They are evidence about expression from an earlier room model.

## Direction

The open quality problem is still the conversion from Kit's private choice into what the player hears. Her identity is specified and loaded. A private plan, a scene read, a public-safe `kit_focus`, and speech checks give that choice a path into the performance. The spoken scene still has to earn the player's attention on its own. The next improvement has to be visible: a recognizable actor pursuing a goal, a particular response to the player's actual move, Kit's own taste shaping what happens, and a live opening the player can take or ignore.

The open engineering problem is coverage. On `main`, a room plays when someone has already written its file. The work in progress builds that file from the book's keyed text when the PC approaches, then hands it to the same loader. Tests of the result should use varied, previously unplayed areas. Passing one familiar room leaves the coverage claim unproven.

We use published work on reactive dramatic beats, autonomous social actors, appraisal, and agent memory as design precedents, and we test each constraint at the table. The bridge procedure in `docs/architecture/kit-06c-play-slice.md` applies to every room. Its examples come from an early test room.

**Performance quality is what we build toward.** A turn may be longer if it earns the space; a simple roll prompt should still be quick and direct. Record end-to-end latency. Do not cut a compelling exchange to satisfy a speed target. Early waits of well over a minute were a usability failure, and they stay on the list after the spoken scene is worth the wait.

Source fidelity, fair rulings, and the player's freedom to act remain mandatory.

## What comes next

**Current personality priority: preserve Kit across contexts.** Ordinary conversation, creative and debrief talk, and live DM play should feel like the same person under different authority. Cross-campaign memory can wait.

1. **Make her expressed performance worth playing.** Openings, NPC tactics, Kit's own table presence, and the player's next choice should be legible in the transcript. There is no universal word count, and no requirement to joke or monologue every turn.
2. **Author rooms from the book as the PC approaches.** A keyed area becomes a room file when play reaches it, mounts through the loader, and can be refused cleanly when it is not ready. Prove that on varied, unplayed areas.
3. **Keep rulings inside what the room declares, and widen that declaration.** Conversation, investigation, creative physical actions, consequences, and saved NPC commitments belong in the room file and the general engines, for every area the same way.
4. **Grow the campaign around that.** Character sheets already load from any `character_sheet_v1` file. Fuller rules and combat, campaign-wide state and source retrieval, maps and art by stable id, and a player-facing interface come after a second genuinely different scene is worth playing. Solo combat needs judgment about action economy without erasing the player's tactical choices.

Today we have a working loader, a bridge, and a candid set of early playtests. A complete solo campaign, and proof that Kit outperforms a human DM, are still ahead.

## A short explanation to share

> I'm building Kit, an AI Dungeon Master for a solo D&D campaign—one who can do more than generate the next line of narration. Her promise is to make solo play feel as responsive, surprising, and alive as playing with a great human DM, while offering something a human DM usually can't: a world that is always available, remembers everything, and reacts consistently to every player choice.
>
> The current runtime mounts a room file, lets Kit make a DM decision, acts out the scene, and saves what happened. Rooms are prepared as the player reaches them. The work in progress builds the next room from the book's keyed text at that moment, instead of keeping one hand-written scene as the whole game. Her advantage won't come from telling better stories alone. It will come from combining a distinctive, consistent personality with the invisible systems that make a campaign feel real: applying rules, tracking maps, remembering past events, modeling NPC motives, and maintaining a persistent world that changes in response to the player. Kit should feel like a creative partner with a point of view—and like the reliable game engine beneath the story.
>
> Early playtesting has shown promise, along with clear problems in her timing and voice. Those sessions are helping us determine when she should pause, when she should advance the scene, and how her personality can make moments more vivid without taking control away from the player.
>
> Next, we'll keep testing that voice, and we'll make keyed areas of the book playable as the player approaches them, before calling the campaign built.

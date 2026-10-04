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

1. **The game underneath her.** A room file, the rules the runtime actually implements, the character sheet, and saved world state tell her what is true, what a character can know, and what an action can change. NPCs have their own motives when the room file gives them motives. The game records consequences so the next turn begins in the world the player actually changed.
2. **Her private decision.** Kit sees the accepted event and recent conversation. She considers what the player is trying, which live story pressure (if any) they touched, what the NPC wants, and why Kit cares. She may be amused, concerned, proud, interested, or simply focused on a ruling. She chooses a DM move and decides how much of her own table voice belongs in it. A short record of that choice is saved before she speaks.
3. **What the player hears.** Kit describes the world, acts as the NPCs, makes rulings, and sometimes comments as herself. The NPCs should sound like people with their own aims. Her voice follows Brendon's voice spec (`docs/personality/dm-personality-core.md`): theatrical, quippy in banter, and happy to overact in description, always coherent with what just happened.
4. **Memory and evaluation.** The runtime keeps a limited record of Kit's recent reactions and the player's choices. We then test whether those records actually change her later decisions and improve the experience. A plausible private thought does not count if the player cannot feel it in the game.

These are practical software layers for making behavior coherent. Calling one layer her "thoughts" does not claim she is conscious. The point is to make her choices traceable and improve them through playtests.

## Where main is

`main` runs a generalized room loader, not a single play slice.

`runtime/kit_rooms.py` mounts any room file in the repo's format. Play in that file moves through approach, first look, exploration, and resolution, and each stage uses only what the file already contains for that moment. Rooms can chain when a file declares a link. A file that cannot mount is refused before a turn commits. The design write-up is `docs/architecture/ROOM_LOADER.md`. The current snapshot of what that means for the project is `state/project-status.md`.

Area 6c is one past regression room. The suite still runs its fixture, and `start` with no `--room` still opens that file as a leftover fallback. It is not the reference room and not a template. The watchroom fixture is synthetic. The area 17a file in `rooms/` is a stub, marked as such, and is not the published room.

The bridge around that loader is in place. ChatGPT supplies Kit's private decision and public performance through `prepare`, `decide`, and `finish`, or through `prepare --one-pass` and `complete`. The Python runtime validates and saves them. This path does not require a separate model choice or `OPENAI_API_KEY`. The legacy `play` terminal command calls the paid API; it is not used and must not be run. Session and room manifests, table talk, character sheets, claims, and the optional mechanic blocks (cards, tolls, a minimal fight, attitudes, a story brief) are all real, and each mechanic runs only when the room file declares it.

The personality core and the voice files are loaded on every turn. That is the identity contract. It is not a demonstration that the spoken scene feels like Kit.

## What is in progress, and what is not claimed

**Source-to-room authoring is the next room path, and it is not on `main`.** The intention is that Kit writes a room file from the book's keyed text when the PC approaches, and the loader mounts that file. The book's text is not in this repository. There is no authoring module here. Until that work lands, the runtime plays room files that already exist. It does not build a keyed area on demand.

Also not claimed, because the code does not do them:

- a complete D&D rules engine, or a ruling for every creative action
- general NPC belief updates, or a finished relationship model
- live level-story or Halaster machinery (the 2026-09-23 runtime notes that described those as already running are historical)
- maps and art pulled into a turn by stable id
- proof that a player would choose Kit over an experienced human DM

Early live samples are still the quality evidence we have, and they failed. Character onboarding (2026-09-23) showed Kit could hold a ruling and then reconsider it, and also showed unsolicited advice, a weak opening, and generic banter. The short room exchanges with Nik (2026-09-26 and 2026-09-29, under `tests/playtests/`) produced lifeless NPCs, a flat or incoherent table voice, and, in one run, an invented card game. Those records are failures of the tested experience. A greener engine suite does not reverse them.

Passing tests do establish the plumbing: secrecy, restarts, stale turns, rollback, room mount and chain, and the checks on a performance. They do not establish that the scene was worth playing.

## What comes next

1. **Finish source-to-room authoring.** A keyed area should become a room file when play reaches it, checked by the same loader, and the proof should be rooms that were not hand-written in advance. Area 6c staying green is a regression check, not the goal.
2. **Keep the spoken turn worth playing.** Actor aims, Kit's own taste, and the player's next choice have to be legible in the transcript. A longer trace does not establish a more entertaining DM.
3. **Widen rulings only as the room file can declare them.** Conversation, investigation, physical acts, and consequences grow by data the loader already understands. Fuller rules, combat, and campaign-wide state come after a second real room from the book actually plays.

Today we have a room loader, a bridge, and a candid set of failed live samples. We do not have a complete solo campaign, and we do not have proof that Kit outperforms a human DM.

## A short explanation to share

> I’m building Kit, an AI Dungeon Master for solo D&D. Her promise is to make solo play feel as responsive, surprising, and alive as playing with a great human DM, while offering something a human DM usually can’t: a world that is available, remembers what happened, and reacts to the player’s choices.
>
> The current runtime mounts a room file, adjudicates the turn, lets Kit decide and perform, and saves what happened. Rooms are data. The next step is to write those files from the book’s keyed text as the character approaches, instead of treating one early test room as the whole game.
>
> Early playtesting has shown real problems in her timing and voice. Those sessions are how we tell whether a change made the table better. The personality and the engine only count if the next exchange is worth playing.

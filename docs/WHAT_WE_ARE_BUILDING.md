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

1. **The game underneath her.** Adventure text, maps, rules, character information, and saved world state tell her what is true, what a character can know, and what an action can change. NPCs have their own motives. The game records consequences so the next turn begins in the world the player actually changed.
2. **Her private decision.** Kit sees the accepted event and recent conversation. She considers what the player is trying, which live story pressure (if any) they touched, what the NPC wants, and why Kit cares. She may be amused, concerned, proud, interested, or simply focused on a ruling. She chooses a DM move and decides how much of her own table voice belongs in it. A short record of that choice is saved before she speaks.
3. **What the player hears.** Kit describes the world, acts as the NPCs, makes rulings, and sometimes comments as herself. The NPCs should sound like people with their own aims. Her voice follows Brendon's voice spec (`docs/personality/dm-personality-core.md`): theatrical, quippy in banter, and happy to overact in description, always coherent with what just happened.
4. **Memory and evaluation.** The runtime keeps a limited record of Kit's recent reactions and the player's choices. We then test whether those records actually change her later decisions and improve the experience. A plausible private thought does not count if the player cannot feel it in the game.

These are practical software layers for making behavior coherent. Calling one layer her “thoughts” does not claim she is conscious. The point is to make her choices traceable and improve them through playtests.

## Current implementation state

As of the 2026-10-07 executable audit of `main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`, Kit's runtime is materially beyond the original Area 6c prototype.

Current `main` has a generalized room loader; one-pass and staged host paths; SQLite snapshots and an immutable event ledger; hidden-information projection; claims/knowers; agendas; attitudes; limited combat and card/toll procedures; manifests and rehydration; idempotent retries; table-talk support; a private Kit plan; bounded memory; output guards; and 813 passing mechanical tests.

The runtime remains much less generalized at the **authored experience** layer. Area 6c is still the only richly authored room on current `main`; the watchroom is synthetic and 17a is sparse. The natural-language router remains heavily regex-based, several adjudication domains still fall into pending rulings, and the social substrate is intentionally simple under the performance layer.

Therefore the current evidence does **not** justify the claim that Kit is already a generalized good DM. It justifies a stronger and more precise claim:

> Kit has a substantially generalized runtime substrate. Generalized excellent play is not yet demonstrated.

See `PROJECT_CONTROL.md` for current development orientation and `COORDINATION.md` for cross-agent truth/ownership rules.

## Development direction

The product target is the complete experience of playing and building D&D with Kit. No subsystem is allowed to become the goal by proxy.

Runtime correctness, DM judgment, BFDM research, cognition, memory, personality, latency, visuals, and UI all matter because of what they contribute to the whole experience. A feature can pass its local test and still make Kit worse to use.

Near-term development should therefore do two things in parallel without conflating them:

1. **Keep hardening the runtime where current evidence exposes real execution failures.** Resolve the overlapping runtime PR stack, broaden adjudication and authored room coverage, and preserve state/knowledge/agency contracts.
2. **Increase end-to-end evidence.** Test current `main` across materially different play situations and evaluate the experienced result, not only whether internal components behaved correctly.

BFDM and future cognition work remain important, but should follow the empirical sequence in the canonical `bfdm-corpus`: source-grounded research, bounded findings, minimal cognition experiments, then architecture demanded by observed failures.

The project should keep asking both:

- did the targeted component improve?
- did the complete experience with Kit become better?

## A short explanation to share

> I’m building Kit, an AI Dungeon Master for a solo D&D campaign—one who can do more than generate the next line of narration. Her promise is to make solo play feel as responsive, surprising, and alive as playing with a great human DM, while offering something a human DM usually can’t: a world that is always available, remembers everything, and reacts consistently to every player choice.
>
> The current prototype is a working test room where Kit makes a DM decision, acts out the scene, and saves what happened. Her advantage won’t come from telling better stories alone. It will come from combining a distinctive, consistent personality with the invisible systems that make a campaign feel real: applying rules, tracking maps, remembering past events, modeling NPC motives, and maintaining a persistent world that changes in response to the player. Kit should feel like a creative partner with a point of view—and like the reliable game engine beneath the story.
>
> Early playtesting has shown promise, along with clear problems in her timing and voice. Those sessions are helping us determine when she should pause, when she should advance the scene, and how her personality can make moments more vivid without taking control away from the player.
>
> Next, we’ll use further playtesting to refine Kit’s timing and voice, then strengthen the underlying systems for rules, memory, NPC motives, maps, and persistent world state before building out the full campaign.

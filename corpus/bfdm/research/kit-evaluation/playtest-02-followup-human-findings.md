# Kit Area 6c — Later Human Live-Test Findings

**Date:** 2026-09-29 to 2026-09-30  
**Evidence status:** recovered conversation-level findings; no complete verbatim transcript has yet been recovered into this research workspace.  
**Do not treat this as equivalent to the exact source record in `source-records/2026-09-29-area-06c-voice-spec-nik.md`.**

## Context

After the initial Area 6c failure, engineering work added a playable card-game procedure, claims/knowledge handling, and additional automated regression coverage.

PR #16 reported **316 automated tests passing**.

A later human live test still produced important DM-quality failures.

## Brendon feedback preserved from the later test

### The room's point was not evident

Brendon's summary:

> “The room has a point. The point was not evident.”

The problem was larger than individual dialogue.

The scene contained authored interests and potential pressures, but the player was not being given enough legible information to understand what mattered about the room.

### Gambling dominated the scene

The implemented minigame became too much of the scene's center of gravity.

Brendon's correction:
- players may simply skip a prepared minigame;
- story/function must still be woven through the scene;
- the room cannot depend on the player choosing to engage the game mechanic.

This is an important regression target for any future special subsystem:
> a playable minigame is a tool inside the room, not the room's reason for existing.

### Motives and stakes remained unclear

The live test did not make the fraud/extortion/conflicting NPC interests sufficiently legible.

A technically functioning card procedure did not solve the more important DM problem:
- who wants what;
- what is happening here;
- why the player should care;
- what pressure exists if the player does something other than gamble.

### NPC personality faded

As the procedural layer took over, NPC banter/personality weakened.

Brendon specifically wanted:
- NPCs to sustain their own personalities;
- basic room/story interaction to continue around mechanics;
- banter and motive not to disappear once a subsystem is active.

### Description before checks

Brendon corrected the interaction order:
- provide basic observable description first;
- then call for checks where uncertainty remains.

Checks should deepen or resolve what the player is trying to learn, not replace the DM's obligation to describe what is plainly perceptible.

### Unsupported mechanical advantage

The live test granted a mechanical advantage associated with a Sentinel Shield without adequate support.

This belongs to a general adjudication class:
> do not manufacture benefits from equipment, expertise, or context unless the relevant rule/state actually supports them.

### Response delay remained a play problem

Long waits sometimes produced replies too thin to justify the delay.

The issue is not simply raw model latency. From the player's perspective, a long delay raises the quality bar for the eventual turn.

Brendon's correction:
- avoid excessive response delays;
- if a response takes substantial time, the result still needs to carry enough scene value.

## Why this follow-up matters

The initial failure showed:
> Kit could fail to make an authored room playable.

The engineering response proved:
> the runtime could encode a richer gambling procedure and catch additional factual/state errors.

The later live feedback showed:
> a richer procedure can still fail as Dungeon Mastering if it crowds out the room's story, actors, motives, description, and pacing.

That distinction should remain central to Kit evaluation.

## Regression targets added

A future run should demonstrate that:

1. The room's purpose can become legible even if the player never joins the minigame.
2. NPC motives/interests remain active around any subsystem.
3. Basic observable information is narrated before optional checks.
4. Mechanics do not consume the social/story layer.
5. Equipment/rules benefits require actual support.
6. NPC personality persists through procedural play.
7. Response time is judged alongside the value of the delivered turn.

## Evidence gap

The exact later human transcript should be added if/when it is recovered from conversation/project records.

Until then:
- the findings above are preserved as explicit Brendon feedback;
- exact wording beyond the quoted "room has a point" line should not be reconstructed as verbatim dialogue.

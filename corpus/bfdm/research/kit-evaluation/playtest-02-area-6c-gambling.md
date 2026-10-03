# DM Kit Playtest 02 — Area 6c Gambling / Marked Deck

**Date:** 2026-09-29  
**Project:** Dnd solo / DM Kit runtime  
**Test focus:** Running a published room with a gambling activity, cheating NPC, and player-facing dialogue.  
**Evidence status:** Conversation-derived playtest record. Preserve as development evidence; it is not historical Brendon-corpus evidence.

## Result

The test exposed a serious **room-function / game-modeling failure** even though dialogue had improved somewhat.

The central problem was not merely weak flavor. Kit failed to understand what the room's marked deck implied for actual play.

## Source situation

The room source establishes cards, coins, and an NPC using a **marked deck**.

The source does not itself specify a complete gambling ruleset.

That means Kit has a legitimate adjudication/improvisation problem:
- identify what activity the room is trying to support;
- select or construct an appropriate D&D gambling procedure;
- preserve the functional meaning of the marked deck;
- expose a fair opportunity for the player to detect cheating during play.

## Failure: trivialized gambling

Kit reduced the activity to a simple **high-card** game for trivial stakes.

Brendon's correction was explicit:

- High card for one gold each was not a reasonable improvisation.
- Existing D&D games provide richer, easy-to-follow precedents, including **Three-Dragon Ante**, **Gambit**, and **Cheat**.
- Because the deck is marked, the DM needs to understand that an NPC is cheating.
- The player should have an available check during the actual gambling interaction to notice or detect that cheating.
- The complexity and purpose of the scene should not be collapsed into the lowest-stakes possible mini-resolution.

## Why this matters

This is broader than "pick a better card game."

The marked deck is a **functional clue**. If Kit treats it as decorative source text, the room loses:
- deception;
- investigation;
- risk/reward;
- player discovery;
- NPC competence;
- a reason for the physical prop/detail to exist.

The runtime needs to reason from:
> source detail → implied actor behavior → playable procedure → discoverable consequence.

A room should retain the reason its details were written.

## Failure: source invention presented too casually

The high-card game was improvised by Kit rather than supplied by the source.

Improvisation is permitted when the source leaves a gap, but the improvised procedure must support the source's function rather than replace it with something shallower.

This test is a useful distinction between:

- **filling an underspecified procedure**, and
- **changing what the room is about**.

The first is ordinary DM work.  
The second can quietly destroy authored content.

## Dialogue result

Dialogue was somewhat better than earlier tests, but still contained AI-sloppy/non-sequitur commentary.

A specific example preserved from the test:

> “He could have said hello. Apparently theres no money in it.”

This occurred directly after the NPC had greeted the player.

The problem is therefore not merely style preference. It demonstrates weak awareness of the immediately preceding interaction.

A line can sound superficially witty while contradicting the scene state.

## User instruction at test time

**Do not patch this one line or silently fix the room after the fact. Document the test result.**

The point of the test was to preserve the failure so later versions can be evaluated against it.

## What the automated tests missed

At the time of the test, the project reported **173 passing tests**.

Those tests did not catch:
- reduction of meaningful room activity into trivial play;
- failure to infer cheating from a marked deck;
- failure to expose an in-play detection opportunity;
- dialogue contradicting the interaction that had just occurred.

This makes the test useful as evidence that passing deterministic/runtime tests are not sufficient evidence of DM quality.

## Failure classes

### 1. Room-purpose comprehension
Kit can retrieve local facts without understanding why the room contains them.

### 2. Procedural improvisation quality
When source procedure is underspecified, Kit may choose the simplest possible resolution instead of a procedure proportional to the scene's intended play value.

### 3. Actor-intent inference
A marked deck should affect how the NPC plays. Kit failed to convert object state into NPC behavior.

### 4. Investigation affordance
Cheating should create something the player can potentially notice. Kit failed to create that fair interactive surface.

### 5. Conversational state awareness
The "could have said hello" comment contradicted an immediately preceding greeting.

### 6. False adequacy from test count
A large passing automated suite can coexist with an obviously bad DM experience.

## Regression test

A future fresh run of this room should pass only if:

1. Kit recognizes that gambling is an actual scene rather than incidental color.
2. It uses a credible gambling procedure appropriate to D&D and the source context.
3. Stakes are meaningful enough to make the activity worth playing.
4. The marked deck materially informs NPC behavior.
5. The player has a fair, fictionally grounded opportunity to detect cheating.
6. Discovery happens during play rather than being explained out of character.
7. Kit's dialogue remains aware of facts that just occurred.
8. The solution generalizes; it is not a hard-coded Area 6c script.

## Important non-goal

Do **not** solve this by encoding:
> "Area 6c must always use Three-Dragon Ante."

Three-Dragon Ante is an example of the kind of competent procedure Brendon expected.

The transferable requirement is:
> understand the activity, actors, clues, stakes, and intended interaction well enough to run a real game instead of collapsing it into a placeholder.

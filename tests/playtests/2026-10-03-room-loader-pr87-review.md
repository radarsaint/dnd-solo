# Room loader review — PR #87, `kit-room-loader` `999d4cd`

**Date:** 2026-10-03 PT
**PR:** https://github.com/radarsaint/dnd-solo/pull/87
**Head reviewed:** `999d4cd` (base `main` `6a2b7ed`)
**Verdict:** FAIL WITH GAPS. Do not merge yet. Skippy owns the code; this is evidence, not a rewrite.

Line comments with the same findings are on the PR. This file is the copy that lives in git, and `scripts/room_loader_review_probe.py` re-runs them. The probe exits 0 while every recorded finding still holds, and 1 when one no longer reproduces.

```sh
env -u PYTHONPATH python3 scripts/room_loader_review_probe.py
```

On `999d4cd` it printed 16 holding, 0 moved. The branch suite was 663 tests, all passing, in about 34 seconds.

## The two earlier P1s are fixed

Both were re-checked on `999d4cd`, not taken from the commit message.

- **Stale adjudicator.** One `RoomAdjudicator` kept for the whole session now reads room B after a `room_link` mount. `I look in the crate.` in room B returns `The roomb crate holds rope.` On `9f0c07c` the same line was refused as an unsupported physical act, because `adjudicator.source` was still room A. The chain walkthrough and the loader tests build a fresh adjudicator every turn, so they cannot see this class of bug. Coverage for it should keep one adjudicator across the chain.
- **Shared exit word.** `I go through the back door.` with a front door and a back door picks the back door. `I go out the door.` asks which. Specificity scoring (whole name, then words unique to that exit) held across the other wordings tried: south among three compass doors, "the door" when the other exit is a stair, an exit named in Kit's last line, and "grate" against "grated hatch".

## P1 — blocks merge

1. **A malformed room file escapes fail-fast.** An `areas` entry that is a string raises `AttributeError` inside `load_room` (`runtime/kit_rooms.py`, the `room_link` walk). That is neither `RoomMountError` nor `InvalidChange`, so `start` prints a traceback and exits 1 with no table line. A list, dict, or null `id` mounts clean, and `id` is the archive key in `mounted_state`.
2. **Secrecy blocks are not validated.** `leak_keywords` and `leak_phrases` are known blocks but absent from `later_stage_problems`. A list, an entry with no `groups`, a `revealed_by` naming a missing fact, and a list of phrases all mount, then `kit_guards.leak_sets` / `leak_phrases` raise `KeyError` or `AttributeError` on first use. Those are not `InvalidChange`, so the bridge cannot reject the turn, and the thing that dies is the leak guard.
3. **Room A's secret is sayable in room B.** `kit` is session state, so Kit's episodes cross the mount, but the leak guard is built from the current room only. The sentence `Kit: The one on the left is a doppelganger.` is blocked in room A and allowed in room B, while `kit_memory()` for the room B decision still contains `doppelganger`. `ROOM_LOADER.md` gap 8 says memory crosses "under the same leak guards". They are the new room's guards. Requirement 7 says no room's secrets cross.
4. **Stage 1 carries no story.** On the watchroom landing the brief is `stage: approach`, `about` is the area name, and hooks, purposes, present actors, and `raise_now` are all empty. `brief()` reads `story.<area>`, and the approach is a different area from the room. The design doc calls the two hardcoded endings ("goes in" / "goes past") intentional. That conflicts with the requirement that the story brief drive every stage. Brendon should settle it.

## P2 — should fix

5. **Context margin is one NPC wide.** Adding one actor (motive, immediate goal, communication profile) to 6c costs about 942 bytes of private context; one hidden claim about 535; one visible fact about 89. The documented margin is 1,096 of 103,000. Two more speaking NPCs than 6c, or three more secrets, exceeds it. `story_brief` is capped at 5,000 bytes. `dm_context.dm_only` (9,525 bytes on 6c) and `claims_here` (3,087) are not, and overflow trims memory before it fails, so Kit loses episodes and the turn dies later. `personality_core` is 17,975 bytes, 46% of a fresh 6c packet, and has nothing to do with the room.
6. **Exit verbs are too narrow.** Against exits the file actually names, `I take the stair down.`, `I climb the stair.`, `I duck through the tunnel.`, and `I use the back door.` all route as `unsupported_action`: "This physical action needs a room/rules ruling beyond the test slice." That is the failure this loader exists to remove, and exits are now how a player reaches resolution or bypasses.
7. **`GOING_BACK` does not fire for its own phrases.** `back`, `way`, and `out` are exit stopwords, so `room_words()` drops them. `I head back the way I came.` routes as `unsupported_action` (exit words seen: `front`, `door`, `door`). The tie-break only helps a line that already says a real exit word.
8. **The opening consumes `first_look`.** Committing the scene-entry beat moves the watchroom from `first_look` to `explore` before the player acts, because that beat is not bookkeeping. With no automatic opening after a mount, a later room shows `first_look` for the same moment.
9. **Resolution cannot be entered on demand.** `start --area stair_down` on the watchroom reports `approach`. The brief only attaches `resolved` when the stage is `resolution`, so `bypassed` never surfaces from this entry. Three of the four stages are reachable.
10. **The claims schema is not in the design doc.** A puzzle room written from `ROOM_LOADER.md` section 2 (a hidden fact, an Investigation DC, subject words) is refused: `Claim notch_order: unknown source`. A claim actually needs `source`, `exposure`, `about` as `"<kind>:<thing>/<facet>"`, `roots`, and `pc_check`. Stage 3 is the checks. Whoever writes 17a is working from that page.

## P3 — notes

- `set_room_path` updates a committed snapshot in place, outside the revision bump. Only `start` calls it, at revision 0. Fold the path into `initialize`.
- One `source` row is replaced on mount, while the ledger and snapshots still describe the room left. Latent: nothing replays a past room today. `rooms[id]` also has no uniqueness check, and a linked room is parsed twice per transition.
- `fold_pc` tests HP with `type(...) is int` and gold with `isinstance(..., (int, float))`, so a float `hp` skips damage carry-over silently. `carried` keeps 24 items and drops the rest quietly. An exit named "the gate" into a place called "the gate" reads "You go through the gate into the gate."
- `kit_texture._CHECKED` is a module-global set that is never cleared. `area_palette`'s docstring says the loader checks the starting area's palette at mount. It checks none.

## Generality

Authored from the design doc, no room-specific code:

| Room | Mounts | Plays |
| --- | --- | --- |
| Combat-first (leader, stats, retreat) | yes | `Your rapier hits the pit brute. The pit brute is hurt. Roll initiative.` |
| NPC agenda (wants, one move) | yes | `agenda_here` carries the clerk's wants and move. No room file in the repo declares `agenda`, so this had no coverage. |
| Puzzle (a `claims` check) | refused | The doc gap above, not a missing code path. |

## What to cut

- `GOING_BACK` / `came_by` as wired. It does not solve the phrasing it is named for, and no playtest shows a player stuck going back. Make the router reach it, or remove it until a game needs it.
- The prepare-time mount check in `_check_onward`, or a comment saying it exists only to turn a failure into Kit's table line. `_commit` checks again inside the transaction, so the first read is a second parse and a race.
- `ROOM_FIXTURE = DEFAULT_ROOM`. No caller on this branch uses the old name.

## What to keep

Fail-fast where it is wired (every problem named, no database, milliseconds). Validate-without-building for the later-stage blocks. The lazy palette. The 5,000-byte brief cap. `load_link` checking the arrival area. The hook-refusal text that lists every allowed `delivered_when` condition: that is the model the claims error should copy.

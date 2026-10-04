# Watchroom playtest: Nik, 2026-10-04

- **Date:** 2026-10-04, about 4:11 to 4:56 AM PT
- **Build:** dnd-solo `999d4cd` (detached Kit worktree)
- **Room:** the watchroom (a landing, an iron door, a watch warden with a bell, a chest and a back stair)
- **Character:** Nik, `tests/fixtures/characters/nik.json`
- **Players:** Kit as DM, the Nik player bot as player, with Brendon watching and ruling in the group chat
- **Outcome:** Nik talked to the warden and failed Persuasion, then failed an Acrobatics dash for the stair, and the scene went to combat. Combat ran off-engine because the warden had no stat block. Nik dropped the warden and one responding guard and finished at 28/32 HP. Brendon stopped the session after round five.

The log below is Kit's own turn log, unchanged apart from the tags. Each stall or engine misread has a tag naming the PR #87 (room loader) item that fixes it, or `[open — not in #87]` if nothing in #87 covers it yet. Every open tag is now `[fixed in #91]`, each with its test class in `tests/test_kit_watchroom_stalls.py`.

## Brendon's rulings from this session

1. **Who calls checks.** Players describe what they do and may ask for a check. They never pick the skill and never roll first. Kit decides which check, if any, and then the player rolls. Players can push back in story terms ("can I take time to investigate this?", "what does my gut say?"), and Kit weighs that and makes the final call.
2. **Describing actions and creative moves.** Players can describe their own actions and color freely, as long as it doesn't hand them a mechanical edge. Kit still owns outcomes. A creative use of the scene is asked as a question ("can I use this stool to help me vault?"), and Kit may reward it with a silent DC drop of about 2.
3. **Skill families.**
   - *Social:* opposed by a hidden NPC roll, and the result moves the NPC's attitude.
   - *Knowledge:* recall only.
   - *Exploration:* reveals things through the room's reveal rules.
   - *Physical:* changes position or state, and is often contested.
4. **Sleight of Hand, thieves' tools, or breaking things.** This takes DM judgment, not a lookup table.
   - Delicate hand work on a trap, like feeling out a pressure plate or easing a trip wire, can be Sleight of Hand, and that often beats a tools check.
   - Picking a lock or a formal disarm with tools is a thieves' tools check.
   - With no tools, the object gets broken open using the SRD object rules (objects have their own AC and HP).
   - A trap everyone already knows about is a planning problem (how do we get through and take the sting out of it), not a single roll.
   - Sleight of Hand means hand work in general. Card swaps are just one case.
5. **Concentration** should be tracked as engine state.
6. **Stat blocks and alarms.** Every actor in a room who can fight needs a stat block. Any alarm in a room must list who answers it.

## Next-test requirements

- A cold-start Kit: a brand-new Kit session that starts from the repo alone.
- A room with a locked chest and a trip wire, to exercise ruling 4.

## Player-side notes (Nik) and Kit's responses

1. **Saves were narrated by the die, not the total.** Hesk's Toll the Dead save was narrated as a "natural 20". It actually passed on the total: 20 minus Mind Sliver's d4 of 2 is 18, against DC 15. Leading with the natural 20 made it read like an automatic success, and under the rules a natural 20 on a saving throw isn't one. Kit also only said the guard's Intelligence save against the readied Mind Sliver had failed after she was asked. *Kit's response:* from now on she narrates saves by the total, and always says who saved and whether they passed or failed.
2. **A planted hook was never paid off.** When the bell rang, "somewhere far below, something stops moving" set up a beat that never came back. *Kit's response:* fair hit. It should have been the guards below freezing to listen when the bell rang, or a hint at who is expected tonight. [fixed in #91: open_threads (S9)]
3. **Untested coverage.** Nik never touched the chest (or its letter), and the far-stair exit only came up through the fight, so the stage beyond that exit was never loaded. [open — next test]
4. **Player-bot errors, not Kit's.** The Nik player bot slipped twice. It narrated the result of its own failed Acrobatics roll ("Nik's back foot lands on the edge of the stool"), which was Kit's to narrate. And its readied Mind Sliver declaration didn't say that readying uses the reaction, so Shield wasn't available if it triggered; Skippy caught that at the table.

## Kit's turn log (build 999d4cd)
- T0 (known issue): doorway story brief thin: about = "Landing outside the watchroom", no hooks/purposes; level_context and campaign_context null. Kit teased from the two visible facts (lamplight, four-note humming). [fixed in #91: approach frame (S1)]
- T0: speakers list at the landing includes "Watch warden" though the warden is inside, not present. [fixed in #91: inside actors are only heard (S2)]
- T0 rejections: story_basis must be 'none' when no level/campaign context ("Story basis is not established for this anchor"); reply_to must be 'none' on room entry. Committed on 3rd try, not degraded. [fixed in #91: opening commits first try (S3)]
- After T0: Nik crept to the hinge-side gap (Stealth 13, Perception adv 23 listening to the tune). Brendon: 'Woah. Stop.' Session held; turn not prepped.
- Brendon rule: players request checks, DM picks the skill (fiat). Nik's pre-rolled Stealth 13 / Perception 23 set aside. On resume: rule on creep/peek/listen, call own check (likely Stealth for the approach, Perception for what he hears/sees), wait for the roll. Holding until Brendon resumes.
- T1 BUG: 'creeps to the hinge side of the gap ... puts one eye to the opening without touching the door' -> action_kind=stealth, 'You slip out through the iron door.' (moves Nik INTO the watchroom; stage first_look). Peeking at a door is read as leaving through it; 'creeps'+'door' = stealth exit. Abandoned. [fixed in #91: threshold look is not movement (S4)] (a look at the door was read as walking through it; related to (e) but not covered)
- T1 (reworded 'edges up beside the gap ... peeks in'): action_kind=social, 'You declare: ...'. Committed as ruling/call: Kit called Dex (Stealth). Engine has no check-request path for 'Can I make a check?'; it routes as a social declaration. [fixed in #91: check_request (S5)] (no path for a player to ask for a check)
- T2: 'Stealth check: 1d20 (13) + 2 = 15' -> stealth, 'You move without a sound.' Kit set the warden's passive at DM discretion (~12); success. Peek showed warden, chest, back stair from the watchroom's visible facts; no leak guard fired even though player_perceivable still only lists the landing (engine has no 'peek into adjacent area' view). Invented: padded coat, short spear, stool, hooded lamp. [fixed in #91: threshold_view (S6)] (no peek-into-the-next-area view)
- T3 stall: 'watches the man ... Is the chest locked? ... bell, a horn, or a cord ... raise an alarm? Can I make a check?' -> PENDING_RULING 'This physical action needs a room/rules ruling beyond the test slice.' (known needs-a-ruling stall). Reworded. [fixed in #91: watch-and-ask keeps every intent (S7)] (generic needs-a-ruling stall on a watch-and-ask turn)
- T4 stall: bare 'Perception check: 2d20kh1 (18, 16) + 4 = 22' -> PENDING_RULING (room has no claims; a called check result has nowhere to go). [fixed in #87 (d): bare roll for a called check → pending check]
- T4: workaround 'His look comes up 22.' -> social declare. Even 'Nik looks over the guard and the chest... Perception check: ...' stalled. [fixed in #87 (d): bare roll for a called check → pending check]
- T5 stall: 'eases the door open just enough to show himself, stays on the threshold ...' + speech -> PENDING_RULING. Reworded to an entry through the iron door. [fixed in #87 (a)/(f): speech plus movement in one message → all intents kept]
- T5 BUG: 'goes through the iron door ... and says ...' -> social declare; area stays landing, stage approach, warden not in brief 'present', primary hook (challenge) absent from brief. Speech beats movement in the router. [fixed in #87 (a)/(f): all intents kept] [fixed in #87 (b): 'goes' read as movement]
- T5: warden reply rejected 'Actor is not available in this scene' (engine still has Nik on the landing). Abandoned; split into move turn then speech turn. [fixed in #87 (c): NPC can speak on the entry turn]
- T5 BUG: exit regex \b(leave|go|walk|move|step)\b misses third person 'steps'/'goes'/'walks' -> 'Nik steps through the iron door.' stalls as PENDING_RULING. First-person 'I step...' needed. [fixed in #87 (b): 'steps'/'goes' read as movement]
- T6 BUG: on the exit turn into the watchroom, discernment_candidates actor_bases = {'none'} only (warden missing; player_perceivable actors [] - computed from pre-move area) though story_brief lists warden present. actor_ref 'warden' rejected 'Actor is not available in this scene'. [fixed in #87 (c): NPC can speak on the entry turn]
- T6: had to commit the warden's challenge as Narrator-only reported speech (focus_actor warden rejected 'not an actor present here' on the entry turn). Engine appended the outcome line 'You go through the iron door into the watchroom.' AFTER the Kit handoff in spoken output. Nik's spoken lines from his message were dropped from the committed action (move-only reword). [fixed in #87 (c): NPC can speak on the entry turn] [fixed in #87 (a)/(f): Nik's spoken lines kept] [fixed in #91: engine line never after the handoff (S8)] (outcome line printed after Kit's handoff)
- T7 BUG: speech + 'He watches whether the guard's eyes flick toward the stair or the chest.' -> inspect_feature 'You lift the lid: a coil of rope and a sealed letter lie inside.' ('watches'... no; feature noun 'chest' + any look-verb anywhere; Nik is across the room at spear point). Abandoned; reworded without 'chest'. [fixed in #87 (e): look/watch at a feature no longer triggers handling from across the room]
- T7: committed via 'Nik says: "..."' (all narration outside quotes dropped). Warden spoke fine this turn. Kit called Charisma (Persuasion) for the pitch; Nik's eye-watch answered free from passive Perception 19. [fixed in #87 (a)/(f): narration around speech kept]
- T8: 'Nik says: "..." His Persuasion comes up 3.' accepted as social; engine has no pending check, so Kit adjudicated the fail in narration only (no attitude state change recorded by engine). [fixed in #87 (d): pending check] [fixed in #87 (j): failed social roll records attitude]
- T8 reject: appraisal label 'anger' invalid (allowed: none, amusement, interest, surprise, concern, pride, frustration). Used frustration. [fixed in #87 (g): 'anger' accepted as an emotion]
- T8 reject: exchange-scope 30-word floor for the warden clashes with his card rhythm (short questions, terse). Padded to 30+ in voice. [fixed in #87 (h): no 30-word minimum on terse NPCs]
- T8 reject: 'Story hook overdue' although the warden already challenged at T6; T6's challenge went out as Narrator reported speech (entry-turn actor bug), so the hook tracker never credited it. Re-raised 'Where are you going?' in his line. [fixed in #87 (i): earlier challenge counted toward the hook]
- T9 BUG: feint + dash for the back stair past an alert, hostile warden with spear leveled -> exit auto-accepted 'You take the back stair down.' No contest, no NPC reaction, no check path. Abandoned; Kit called Dex (Acrobatics) vs the warden in the room without an engine turn. Pending: resolve on Nik's roll. [fixed in #87 (k): guarded exits]
- T10: Acrobatics 3 (nat 1) failed. Warden has no statblock in watchroom.json and kit_rooms has no combat config path; Kit running combat off-engine with SRD Guard adapted (AC 12 padded+Dex, HP 11, spear +3, 1d6+1 / 1d8+1 two-handed, Perc +2). Bell = alarm; who answers is Kit's call (room silent on it). [fixed in #87 (l): stat blocks and alarm responders]
- T11: Initiative Nik 17, warden 11 (hidden). Round 1, Nik acts first, prone, warden in reach. Bell not yet rung. Room wrapping up here.
- R1: Nik stands (half move), Slow 3rd slot (3rd slots 2->1, concentration), warden Wis save 5 fail -> slowed. Rabbit Hop (2/3 left) to stair head; stool OOC ask: hop needs no roll, so no DC to lower; allowed as flavour. Warden (slowed, one action): uses action to ring bell (alarm to below). Round 2 -> Nik.
- R2: Mind Sliver, warden Int save 8 fail -> awaiting Nik's 2d6 damage; warden -1d4 on next save. Listen ask: Kit allows Wis (Perception) as part of his turn (no action), advantage from shield. Room wrapping up after this post.
- R2: Mind Sliver 11 psychic, warden at 0 HP (11): unconscious, stable-ish (Kit's call, kept alive for later). Perception 10: hears only boots on the stair, more than one, can't count. Bell answer (Kit invention): two guards (SRD Guard: AC 16, HP 11, spear +3) arrive top of stair view end of round 3. Slow concentration still up (warden only target). Round 3 -> Nik. [fixed in #87 (l): alarm responders listed in the room]
- R3: Nik drops Slow, kicks bell into room, readies Mind Sliver (reaction spent if triggered). Guards (2x SRD Guard) init 14. G1 rounds the turn -> readied Mind Sliver, G1 Int save 11 fail; awaiting Nik's 2d6 before G1 finishes its turn (G1 attack pre-rolled hidden 17+3, dmg 4; G2 single-file behind). Posted warden stat block on request.
- R3: G1 takes 6 (5/11 left, -1d4 next save). G1 steps up to lip, spear 17+3=20 hits AC14, 4 dmg -> Nik 28/32. G2 stuck single-file behind G1, keeps his spear, shouts. Round 4 -> Nik (reaction back).
- R4: OOC confirmed readied MS: G1 Int save 11 fail. Toll the Dead: G1 Wis 20-2(d4)=18 saves (d4 penalty applied, expires end of Nik's turn). G1 attack 2+3=5 miss, no Shield needed. G2 still blocked. Round 5 -> Nik 28/32, reaction up.
- R5 (final): Magic Missile 8 force drops Hesk (5 HP left -> 0); G2 takes 2 (9/11). Session stopped by Nagatha at Brendon's word. Nik end state: 28/32 HP, slots 1st 3/4, 2nd 3/3, 3rd 1/2, Rabbit Hop 2/3, no concentration.
- Post-session (Nik's notes) Kit response: nat-20 save was 20-2=18 vs DC 15, a success on the math; nat 20 is not an auto-success on saves and Kit didn't rule it as one, but the narration leaned on "natural 20" and read that way. Fair hit: "something below stops moving" was a planted beat Kit never paid off (should have tied it to the guards stopping to listen, or to what's expected tonight). Chest letter and far-stair exit unexercised.
- Post-session (Nik's notes) Kit response: nat-20 save was 20-2=18 vs DC 15, a success on the math; nat 20 is not an auto-success on saves and Kit didn't rule it as one, but the narration leaned on "natural 20" and read that way. Fair hit: "something below stops moving" was a planted beat Kit never paid off (should have tied it to the guards stopping to listen, or to what's expected tonight). Chest letter and far-stair exit unexercised. [fixed in #91: open_threads (S9)]: unpaid hook. [open — next test]: chest and far-stair stage.

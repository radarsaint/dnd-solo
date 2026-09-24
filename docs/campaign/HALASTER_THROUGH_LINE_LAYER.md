# Halaster Campaign Through-Line Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Campaign through-line / scheduled antagonist interaction  
**Status:** Baseline design  
**Depends On:** `HALASTER_DM_LAYER.md`, published adventure source, persistent campaign state  

---

## 1. Purpose

`HALASTER_DM_LAYER.md` defines **how Halaster behaves**.

This layer defines **when the campaign must remember Halaster, where his relationship with the player can advance, and what earlier events must exist so Level 23 can pay them off**.

The layer was designed backward from the final encounter.

It does not make every floor about Halaster. Many floors deliberately contain no live Halaster contact. Those floors still contribute evidence, consequences, apprentice history, faction changes, or revelations that later Halaster scenes can use.

---

## 2. Finale Requirement

When the player reaches **Level 23, Area 33: Mad Mage Showdown**, Halaster must not be meeting a stranger.

Before the showdown the runtime must be able to answer:

```yaml
halaster_finale_context:
  what_halaster_has_personally_observed: []
  important_actions_he_learned_later: []
  favors: []
  grievances: []
  surprises: []
  player_model: []
  apprentice_interest: 0
  possessiveness: 0
  current_preoccupation: null
  relationship_phase: null
  strongest_positive_callback: null
  strongest_negative_callback: null
  unresolved_business: []
```

After Nalkara is defeated in Area 33, Halaster must reference **at least three specific campaign events that he actually knows about**. At least one should come from the middle campaign and at least one from the lower levels. Generic praise such as “you have done well” is insufficient.

The published current-goal logic still controls whether Halaster is fundamentally pleased or hostile. The accumulated relationship state controls his tone, what he offers, what he resents, what he thinks the player is, and which past events matter to him.

---

## 3. Interaction Types

Use these labels in this document.

- **LIVE — Physical:** the real Halaster is present.
- **LIVE — Remote:** Halaster is personally communicating through a magical system.
- **OBSERVATION:** Halaster is personally watching through a source-supported sensor.
- **AUTOMATED:** a Halaster-created construct, recording, trap, statue, simulacrum, or autonomous system interacts with the player. It is not automatically a live conversation with Halaster.
- **REVELATION:** the player learns something important about Halaster through the level itself.
- **CONSEQUENCE:** the player's action changes something Halaster cares about and must be stored for later use.

Do not turn an AUTOMATED or REVELATION beat into live omniscience.

---

## 4. Reverse-Designed Campaign Spine

The required campaign progression is:

```text
LEVEL 23: PAYOFF
    ↑
LEVEL 22: FINAL THRESHOLD — Halaster knows they are coming
    ↑
LEVEL 20: INVESTMENT — Halaster directly addresses a choice that matters to him
    ↑
LEVEL 15: SUBJECT — the dungeon openly treats the player as notable entertainment
    ↑
LEVEL 9–10: EVALUATION — apprentices and Dweomercore make the player relevant to Halaster's inner world
    ↑
LEVEL 5: OPTIONAL FIRST MEETING — the player can summon the real Halaster
    ↑
LEVEL 3: DELIBERATE OBSERVATION — Halaster checks on this specific adventurer
    ↑
LEVEL 1: FIRST SIGHTING — someone is watching
```

Levels between these milestones provide evidence and callbacks. They do not need forced appearances.

---

# 5. BACKWARD FLOOR MAP

## Level 23 — Mad Wizard's Lair

### Required end state
Halaster has an opinion of the player supported by recorded history.

### Area 1: No Retreat
**Type:** REVELATION / threshold atmosphere  
**Rule:** Do not spend the payoff here. The animated Halaster imagery, gate control, and anti-spell statue establish that the player has entered his private space. Halaster does not need to greet them yet.

### Area 29: Apprentice Portraits
**Type:** REVELATION  
**Rule:** Treat this as final context for the apprentice history the player has encountered throughout the campaign. If the player has met, killed, spared, or undermined members of the Seven, surface those memories through description or recognition. Do not insert a Halaster monologue.

### Area 32: Jhesiyra's Warning
**Type:** campaign counter-thread  
**Rule:** Run the warning as written. This is the last reminder that another intelligence has been moving against Halaster from inside his own dungeon.

### Area 33: Mad Mage Showdown
**Type:** LIVE — Physical / final payoff  
**Rule:** Run the Nalkara test as written. After Nalkara falls, resolve Halaster from accumulated state.

Before he chooses his next action:
1. determine whether the player furthered, hindered, or produced a mixed result for his current preoccupation;
2. select three or more known campaign callbacks;
3. identify his current classification of the player: `useful`, `candidate`, `favorite_subject`, `rival`, `contaminant`, or another state-supported interpretation;
4. use favors and grievances specifically;
5. only then resolve the published friendly/hostile branch.

**Do not:** introduce a new motivation here to manufacture a finale. The finale must cash out prior play.

---

## Level 22 — Shadowdusk Hold

### Through-line function
This is the final evidence-gathering floor and the point where Halaster knows the player is entering his home.

### Shadowdusk leadership — Areas 34 and 38
**Type:** CONSEQUENCE  
**Trigger:** fate of Zalthar and Dezmyr Shadowdusk; destruction, alliance, or preservation of the Shadowdusk project.  
**State:** record the result even if `Become Waterdeep's Shadow Lord` is not Halaster's current preoccupation. If that preoccupation is active, this is a major favor or grievance.

### Area 35: Eyes of Stone
**Type:** LIVE — Remote / REQUIRED FINAL THRESHOLD  
The gate's Halaster visage already speaks and physically receives the magic item required for passage.

**Runtime overlay:** after the source-required exchange, if Halaster has a recorded history with the player, the visage may add **one short personalized acknowledgment** based only on something Halaster knows. No exposition. No new test. No attack.

Passing this gate means Halaster knows the player has deliberately entered the final level.

```yaml
on_pass_area_22_35:
  attention: max(current, 4)
  relationship_phase: Personal
  final_approach_known: true
  sacrificed_item: record
```

The sacrificed item becomes a callback in Area 33 because the source places it in Halaster's possession on Level 23.

---

## Level 21 — Terminus Level

### Through-line function
A quiet re-evaluation after the major Ezzat decision. Halaster watches; he does not need to perform.

### Area 20a: Halaster's Watching!
**Type:** OBSERVATION / REQUIRED IF ENTERED  
Run the source scrying eye deliberately rather than as decoration. It watches until the player leaves.

If Level 20 materially changed Halaster's regard, the eye's behavior can reflect attention — tracking the player carefully, lingering on an item, wound, companion, or trophy — but it does not speak.

Record what the eye actually witnesses on this level.

### Area 23: Fazrian's Court
**Type:** REVELATION / CONSEQUENCE  
Halaster has allowed the fallen planetar's corrupt court to persist and supplied part of its ecosystem. The player's handling of Fazrian is useful player-model evidence, especially regarding authority, judgment, mercy, and expediency.

Do not force another Halaster contact after the court. Level 20 already supplied the major conversation.

---

## Level 20 — Runestone Caverns

### Through-line function
This is the first lower-campaign point where Halaster's relationship with the player must become an active strategic relationship.

### Area 10: Mad Mage's Puzzle
**Type:** AUTOMATED  
Treat completion, bypass, destruction, or refusal as player-model evidence if Halaster later learns about it. Do not make the puzzle a live conversation.

### Area 14: The Runestone
**Type:** LIVE — Remote / REQUIRED CAMPAIGN CONTACT  
The source explicitly allows Halaster to see, speak, and cast through the Runestone from anywhere in Undermountain.

**Trigger:** the player meaningfully examines, touches, damages, uses, or spends at least one minute near the Runestone. Reaching this artifact inside Ezzat's domain is itself sufficient reason for Halaster to pay attention.

Halaster establishes the link.

The interaction must have a purpose:
- identify what the player intends to do about Ezzat;
- react to the player's known history;
- offer, demand, bargain, warn, or probe according to `current_preoccupation` and relationship state.

He should reference no more than two earlier events here. Save the broader retrospective for Level 23.

### Ezzat decision
**Type:** CONSEQUENCE / MAJOR  
Record separately:

```yaml
if_player_removes_ezzat:
  favor: "Removed Ezzat from Undermountain"
  likely_regard_shift: useful_or_impressed

if_player_allies_with_ezzat:
  grievance: "Supported Ezzat against Halaster"
  likely_regard_shift: rivalrous_or_irritated

if_player_destroys_runestone:
  grievance: "Destroyed the Runestone"
  severity: major
  likely_regard_shift: threatened_or_personal
```

### Haungharassk
Use the published reaction. If Halaster discovers his prized giant snail has been killed or stolen, the Runestone becomes a direct expression of anger. Do not soften this into generic narration.

### Area 19: Ezzat's Scrying Mirror
**Type:** AUTOMATED / characterization  
The fake broom-sweeping Halaster image demonstrates that Halaster anticipates being watched and treats a centuries-long enemy with petty mockery. Do not convert it into a live feed.

---

## Level 19 — Caverns of Ooze

### Through-line function
Show how Halaster turns a real strategic problem into a game played with captive beings.

### Areas 1 and 11: Ichthyglug and Jarûk
**Type:** REVELATION / CONSEQUENCE  
The genies' competition exists because Halaster bound both into a contest to obtain Ezzat's phylactery.

Player actions that matter later:
- accepts either genie's Ezzat bargain;
- frees one or both genies;
- deliberately manipulates the contest;
- breaks Halaster's control over Urm or another bound creature.

These actions should feed the Level 20 conversation if Halaster has a means to learn them.

### Area 13: The Scavenger
**Type:** REVELATION  
The spelljamming ship is evidence of Halaster as collector and jailer: he lured it into Undermountain, stole its helm, and stranded its crew.

If the player later returns the helm and frees the ship, record a specific `property_removed` event for possible Level 23 use.

### Direct contact
None required. The manipulation is the Halaster beat. Let the genies and ship crew own the scenes.

---

## Level 18 — Vanrakdoom

### Through-line function
Demonstrate that Undermountain contains other powers with their own domains and that Halaster does not need to dominate every scene personally.

### Area 32: Umbraxakar's Lair
**Type:** REVELATION  
The opposed statues of Shar and Halaster visually establish competing claims over this part of the dungeon.

### Player outcomes
Freeing Umbraxakar, killing him, or destroying the cult belongs primarily to the Vanrakdoom story. Record major changes to campaign state, but do not automatically turn them into Halaster favors or grievances.

### Direct contact
None required.

This absence is intentional.

---

## Level 17 — Seadeeps

### Through-line function
Resolve or materially change one of the dungeon-scale conflicts Halaster may care about.

### Areas 3 and 11
**Type:** AUTOMATED / REVELATION  
`Halaster's Maw` and the glowing Halaster statue show his traps and authorship. They are not live conversations.

### Githyanki / illithid war
**Type:** CONSEQUENCE  
The player's handling of Extremiton, the colony, the githyanki, and the neothelid is important because the published `Clean House` preoccupation explicitly includes this conflict.

Do not grant Halaster automatic knowledge. Record the world result separately from `halaster_known_events` until he observes, investigates, or receives a report.

### Neothelid aftermath
If the player releases the neothelid and it becomes a major nuisance, use the published consequence: Halaster eventually destroys or contains it. If the player later discovers evidence of that intervention, it demonstrates that he actively maintains the dungeon when something exceeds his tolerance.

### Direct contact
None required unless current state gives Halaster a specific reason beyond merely keeping him visible.

---

## Level 16 — Crystal Labyrinth

### Through-line function
Confirm that Halaster is still following the player's progress after the Obstacle Course and before the Seadeeps decision.

### Area 32: Graduation Chamber
**Type:** OBSERVATION / REQUIRED IF ENTERED  
The source explicitly places one of Halaster's scrying eyes here and says it studies the characters for a minute or two.

Run it as a relationship beat:
- no speech;
- no attack;
- no exposition;
- record exactly what Halaster sees.

If the player silenced the Level 15 play-by-play generator or defeated Netherskull, the eye can visually emphasize recognition by lingering on the player. It still does not communicate.

---

## Level 15 — Obstacle Course

### Through-line function
This is the campaign transition from **interesting adventurer** to **recognized subject**.

Halaster stops being only an unseen author. A system built for his entertainment now reacts continuously to the player's performance.

### Level-wide Play-by-Play
**Type:** AUTOMATED / REQUIRED  
Use the published play-by-play system throughout the level.

The announcer may use:
- events occurring on Level 15 in real time;
- facts already present in `halaster_known_events` before the player entered the level.

It may not reveal events Halaster never learned.

The commentary should become more specific as the level continues. This is where earlier observations start paying off as callbacks.

### Area 30b: Play-by-Play Generator
**Type:** AUTOMATED / CONSEQUENCE  
If the player destroys the generator, the commentary ends exactly as the source specifies.

Record:

```yaml
halaster_event:
  event: "Player silenced the Obstacle Course play-by-play generator"
  possible_surprise: true
  possible_grievance: minor
```

Do not have Halaster immediately restore it just to negate the player's success.

### Area 39: Netherskull's Sanctum
**Type:** campaign milestone  
If the generator still functions and the player defeats Netherskull, use the source's excited upset call as the formal relationship milestone.

```yaml
on_netherskull_defeated_with_announcer_active:
  attention: max(current, 3)
  relationship_phase: Subject
  regard_add: impressed
  observed_event_add: "Defeated Netherskull"
```

If the generator was already destroyed, Halaster can learn of Netherskull's death later, but do not manufacture the missing announcement.

---

## Level 14 — Arcturiadoom

### Through-line function
Bring the player into direct contact with the work and vulnerability of one of Halaster's most important surviving apprentices and expose a plan that reaches Waterdeep.

### Area 15: Mecha-Halaster
**Type:** REVELATION / CONSEQUENCE  
The construct exists because Halaster bargained with the fire giants to build it and intends to use it against Waterdeep's walking statues.

If the player materially stops construction, record the event. It is a grievance only if it conflicts with Halaster's current preoccupation or he has another reason to care about the project at that time.

### Area 40c: Arcturia's Phylactery
**Type:** CONSEQUENCE / MAJOR  
Record discovery, removal, attempted destruction, or destruction of the phylactery.

Do not assign a fixed emotional result. Halaster has little sentimental loyalty to apprentices, and different preoccupations can make the same act useful, irritating, impressive, or threatening.

The event must remain available for:
- Arcturia's behavior on Level 23;
- Halaster's final callbacks;
- apprentice-interest comparisons.

### Direct contact
None required. The point is that the player is now interfering with Halaster's inner circle without needing him to walk onstage.

---

## Level 13 — Trobriand's Graveyard

### Through-line function
Foreshadow Trobriand through his creations before the final level.

### Level-wide construct ecosystem / Area 7: Clammersham Palace
**Type:** REVELATION / CONSEQUENCE  
Track what the player does with Trobriand's scaladar, control technology, Bore Worm, and related constructs.

These are primarily **Trobriand callbacks**, but Halaster can later use them when judging how the player treats powerful magical systems and his apprentices' work.

### Direct contact
None required.

This floor should remain Trobriand's story.

---

## Level 12 — Maze Level

### Through-line function
Create a delayed apprentice branch that can pay off many levels later.

### House Freth / Spiderwatch Keep
**Type:** CONSEQUENCE  
Track Drivvin Freth's fate separately from the general drow war.

### Published aftermath: Drivvin's apprenticeship
If Drivvin survives and remains unresolved, the source allows him to enter Halaster's service and perform the goristro scheme with Halaster after 30 days.

```yaml
if_drivvin_survives_and_aftermath_triggers:
  npc_state.drivvin.allegiance: halaster_apprentice
  halaster_state.apprentice_network_add: Drivvin Freth
  scheduled_world_event: goristro_ritual
```

This state may later matter on Level 20, where a promising apprentice can inherit Ezzat's tower.

### Area 6: Special Effects
**Type:** AUTOMATED  
Use the regional effects as environmental authorship only. They are not evidence that Halaster is presently watching.

### Direct contact
None required.

---

## Level 11 — Troglodyte Warrens

### Through-line function
Allow the drow campaign to breathe while showing another Halaster-modified predator.

### Area 17c: Behir
**Type:** REVELATION  
The arcane runes Halaster carved into the behir turn a natural monster into a customized dungeon guardian.

### Drow war
**Type:** CONSEQUENCE  
If the player cripples House Auvryndar, House Freth, or both, preserve that outcome as a potential `Clean House` favor. Halaster does not automatically know it.

### Direct contact
None required.

---

## Level 10 — Muiral's Gauntlet

### Through-line function
Make the consequences of Halaster's apprenticeship personal and give Halaster a reason to inspect the player's aftermath.

### Areas 3 / 11: Muiral encounters
**Type:** CONSEQUENCE / MAJOR  
Track whether the player kills, spares, bargains with, humiliates, or drives off Muiral.

Muiral is one of the Seven. His fate is automatically important enough to qualify for Halaster's observation criteria.

### Post-Muiral observation
**Type:** OBSERVATION / RUNTIME OVERLAY  
**Trigger:** after the first decisive resolution involving Muiral, when the player next reaches a quiet location and Halaster has a plausible moment to inspect the aftermath.

One of Halaster's normal scrying eyes appears and watches silently for up to one minute.

This is not a conversation. Its purpose is to establish that Halaster noticed what happened to one of his oldest apprentices.

Record the visible aftermath and player behavior.

### Area 4: Muiral's Laboratory
**Type:** REVELATION  
The invitation signed `H` connecting Muiral back to Dweomercore reinforces that Halaster's apprentices remain part of an ongoing network rather than isolated dungeon bosses.

---

## Level 9 — Dweomercore

### Through-line function
This is the campaign's first sustained look at Halaster's relationship to magical talent and apprentices.

The player is no longer only learning what Halaster built. They are entering an institution that exists to recruit, test, corrupt, and train people under his name.

### Area 5: Portrait of a Mad Mage
**Type:** REVELATION  
Use the calm Halaster surrounded by violent madness as intentional characterization. Do not explain the symbolism to the player.

### Area 10: Where's Halaster?
**Type:** REVELATION  
The graduating-class portraits establish his long institutional history with the school.

### Area 31: Halaster's Secretary
**Type:** AUTOMATED / REVELATION  
The redirected sending system demonstrates how many people seek Halaster and how casually he has offloaded access to himself.

If the player attempts to contact Halaster with *sending*, resolve it through this system. Do not bypass it because the through-line wants a conversation.

### Area 45: Halaster's Sanctuary
**Type:** CONSEQUENCE / evaluation checkpoint  
Entering Halaster's private rooms, stealing from them, taking the death slaad control gem, reading his spellbook, or defeating his defenses are all events worth storing.

When Halaster later discovers a meaningful intrusion here, update attention and his player model.

### Optional observation overlay
If `attention >= 2` and the player makes a major change to Dweomercore or Halaster's sanctuary, a scrying eye may appear during a later quiet moment on this level. It watches only. Use this at most once.

### Apprentice state
Increase `apprentice_interest` only from demonstrated magical ingenuity, experimentation, or talent. Merely being on the school level is not enough.

---

## Level 8 — Slitherswamp

### Through-line function
Show that a local tyrant can itself be one of Halaster's controlled pieces.

### Kuketh / Blacktongue rule
**Type:** REVELATION  
Halaster installed the bullywug regime under the death slaad, and the slaad's control gem is kept in Halaster's sanctuary on Level 9.

If the player later acquires the control gem and uses it to alter Kuketh's fate, record a specific event involving Halaster's property/control system.

### Direct contact
None required.

---

## Level 7 — Maddgoth's Castle

### Through-line function
Give the campaign a Halaster-light floor and provide a contrast: another long-lived wizard has turned a private domain into a place where other wizards become trophies.

### Maddgoth's Castle
**Type:** thematic contrast / world state  
Do not force Halaster into Maddgoth's story.

If the player kills all the stone giants and later returns after Halaster has repopulated the caverns, that repopulation is a concrete demonstration that Undermountain is actively maintained.

### Direct contact
None required.

---

## Level 6 — Lost Level

### Through-line function
Show Halaster layered over a much older sacred place without making him the immediate antagonist.

### Area 32: False Halaster
**Type:** AUTOMATED / false identity  
The gray slaad impersonating Halaster is a servant, not the Mad Mage. Do not use it as a mouthpiece for current Halaster state.

### Area 35: Black Cloak / Area 47b: Giggles
**Type:** AUTOMATED regional effects  
Use these exactly as ambient authorship. Do not infer that Halaster is watching.

### Melairkyn destruction and appropriation
**Type:** REVELATION  
The stripped rooms, altered temple complex, guardians, and gates contribute to the player's understanding that Halaster occupies and repurposes other peoples' history.

### Direct contact
None required.

---

## Level 5 — Wyllowwood

### Through-line function
Provide the first player-controlled opportunity to meet the real Halaster and reveal that people close to him can see him as another prisoner of Undermountain.

### Wyllow
**Type:** REVELATION  
If the player earns enough trust to learn her history or views, preserve the key information: Halaster created Wyllowwood to keep her in Undermountain, manipulated her relationships, and Wyllow believes he too is trapped by the place he controls.

### Area 6g: Secret Room — crystal bulb
**Type:** LIVE — Physical / CONDITIONAL MAJOR CONTACT  
If the player plants the bulb in Wyllowwood soil, the real Halaster appears as the source specifies.

Run this as the earliest possible real meeting.

Use current state:
- if he has never deliberately observed the player, he treats them as an unexpected nuisance before placing them;
- if the Level 1 or Level 3 eyes observed them, he can recognize them;
- he talks about his current preoccupation and demands help as written;
- if the player manages to question him, he may provide one useful fact or gate clue;
- then he leaves unless attacked.

```yaml
on_crystal_bulb_summon:
  last_direct_contact: level_5_area_6g
  attention: max(current, 2)
  relationship_phase: Curiosity
```

Do not manufacture another physical meeting if the player never uses the bulb. Missing this encounter is allowed.

---

## Level 4 — Twisted Caverns

### Through-line function
Reveal Halaster as a social experimenter who deliberately creates strange belief systems and then leaves them to develop.

### Area 16a: Lost Island of Bulba-Slopp
**Type:** REVELATION  
Halaster petrified an otyugh and deliberately lured kuo-toa to the grotto because he expected them to worship it.

This is important evidence about his method: he creates initial conditions and watches cultures or conflicts grow from them.

### Direct contact
None required.

The aboleth/kuo-toa conflict should remain the floor's story.

---

## Level 3 — Sargauth Level

### Through-line function
Move from anonymous surveillance to **deliberate observation of this specific adventurer**.

Halaster is already one of the forces encouraging the local war. The player's interference with that war can make them worth checking on.

### Area 21: Azrok's Hold — random encounter 1
**Type:** OBSERVATION / REQUIRED WHEN TRIGGERED  
The source random table includes a Halaster scrying eye that watches the characters silently for one minute.

**Through-line scheduling rule:** if the player has materially changed the balance between House Auvryndar and the Legion of Azrok before this encounter has occurred, select the scrying-eye result the next appropriate time the Azrok's Hold random encounter table is used.

This converts an existing source possibility into the campaign's deliberate observation milestone without adding a new creature or scene.

```yaml
on_level_3_deliberate_eye:
  attention: max(current, 1)
  last_indirect_contact: level_3_area_21
  observed_event_add: current_visible_state
  relationship_phase: Curiosity_if_attention_reaches_2_else_Intruder
```

The eye does not speak.

### Faction outcome
Record the result of the Auvryndar/Azrok conflict. Halaster only adds it to known events if he observed enough, investigated later, or learned it through another source.

---

## Level 2 — Arcane Chambers

### Through-line function
Teach the player what Halaster's authorship looks like before he becomes personally interested in them.

### Area 3: Halaster Puppet
**Type:** AUTOMATED  
Run the puppet and magical voice as written. It is an imitation of Halaster's manner and humor, not a live conversation.

Destroying it may create a small recorded event if Halaster later learns of it, but the trailing voice does not prove he was watching.

### Area 13: Mutated Apprentices
**Type:** REVELATION  
Use the failed apprentices as early evidence that proximity to Halaster and attempts to master the Weave can destroy people.

### Area 25: Creature Storage
**Type:** REVELATION  
This is an important early statement of Halaster's collector behavior: petrified creatures stored for future use, restoration machinery, and Halastron following his orders.

### Direct contact
None required.

The floor should make the player increasingly aware of the person behind the dungeon without making the person care about them yet.

---

## Level 1 — Dungeon Level

### Through-line function
Establish three facts:
1. Halaster is real;
2. the dungeon contains systems and remnants created by him;
3. he can watch adventurers without appearing.

Do not begin with a personal villain relationship. The player starts as one more person down the well.

### Area 16: Manticore Den
**Type:** OBSERVATION / source-conditional  
If the player kills the manticores, leaves, and later returns, the source places a Halaster scrying eye in the chamber. Run it silently for the full minute or two.

This can serve as the first Halaster sighting if Area 29 has not occurred.

### Area 27: Hidden Demiplane
**Type:** AUTOMATED / CONDITIONAL CONVERSATION  
The Halaster simulacrum offers three questions, with the first answer false and the next two true.

Do not count this as contact with the real Halaster. Do not let it update `last_direct_contact` or imply that Halaster watched the conversation unless another source says so.

It is useful for establishing his voice, unreliability, and deep knowledge of Undermountain.

### Area 29: Eye See You!
**Type:** OBSERVATION / PRIMARY FIRST-SIGHTING BEAT  
Run the source scrying eye as written. It studies the player for a minute or two and disappears.

At this point, the runtime records that Halaster has at least seen the player once.

```yaml
on_first_halaster_eye:
  last_indirect_contact: level_1
  observed_event_add: "First clear observation of the player"
  attention: current   # seeing them alone does not make them interesting
  relationship_phase: Intruder
```

Attention only increases if the player does something during an observed scene that Halaster would actually find notable.

### Level 1 rule
No personalized Halaster message is required. The correct opening relationship is asymmetrical: the player becomes aware of Halaster before Halaster has a reason to care about the player.

---

# 6. Required Contact Schedule

This is the minimum intended rhythm if the player follows a broadly normal descent. Source conditions can cause some beats to be skipped.

| Stage | Level / Area | Contact | Purpose |
|---|---|---|---|
| First sighting | L1 A29 or L1 A16 | Scrying eye | Establish surveillance |
| Deliberate check | L3 A21 | Scrying eye | Halaster checks on this adventurer specifically |
| First possible meeting | L5 A6g | Real Halaster, only if bulb used | Player-controlled early face-to-face |
| Evaluation | L9, especially A45 | Halaster's institution/private space; optional eye | Make player relevant to apprentice/inner-world concerns |
| Apprentice consequence | L10 after Muiral resolution | Scrying eye overlay | Halaster notices what happened to one of the Seven |
| Recognized subject | L15 play-by-play / A39 | Autonomous Halaster system | Dungeon openly recognizes the player's performance |
| Continued observation | L16 A32 | Scrying eye | Confirm sustained interest |
| Strategic relationship | L20 A14 | Runestone live link | Halaster asks something consequential of the player |
| Silent reassessment | L21 A20a | Scrying eye | Observe the player after the Ezzat branch |
| Final threshold | L22 A35 | Speaking gate visage | Halaster knows the player is entering his home |
| Payoff | L23 A33 | Real Halaster | Resolve the accumulated relationship |

Do not add substitute physical appearances merely because an optional beat was skipped.

---

# 7. Callback Ledger

The runtime must maintain a short list of events eligible for later Halaster callbacks.

```yaml
halaster_callbacks:
  - event_id:
    level:
    location:
    event:
    halaster_knows: false
    knowledge_source: null
    interpretation: null
    used_in_dialogue: false
```

Good callback candidates include:
- unusual behavior during an observed scrying-eye scene;
- use of the Wyllowwood crystal bulb;
- intrusion into Halaster's Dweomercore sanctuary;
- Muiral's fate;
- Drivvin becoming or failing to become an apprentice;
- destruction or preservation of Arcturia's phylactery;
- silencing the Obstacle Course announcer;
- defeating Netherskull;
- outcome of the githyanki/illithid conflict;
- freeing Halaster-bound genies or the Scavenger;
- alliance with or destruction of Ezzat;
- damage to the Runestone;
- fate of the Shadowdusks;
- the magic item surrendered to reach Level 23.

A callback can be used only if `halaster_knows == true`.

---

# 8. Floor Transition Rule

At the end of every level, perform this update even when Halaster never appeared:

```yaml
halaster_floor_transition:
  player_changed_something_halaster_cares_about: yes/no
  halaster_currently_knows: yes/no
  if_no_how_could_he_later_learn: null
  new_callback_candidate: null
  favor_or_grievance: null
  player_model_change: null
  pending_response: null
```

The purpose is to preserve the campaign story without forcing immediate reaction.

---

# 9. Core Runtime Constraint

**Halaster interaction must be cumulative, not repetitive.**

Every later contact should do something an earlier contact could not do because more history now exists.

- Level 1: he can see the player.
- Level 3: he has a reason to check on them.
- Level 5: they may force a meeting.
- Levels 9–10: they enter his apprentice world and affect people close to him.
- Level 15: his dungeon treats them as notable.
- Level 20: he treats them as an actor capable of affecting his interests.
- Level 22: he knows they are coming for him.
- Level 23: he tells them what, after the entire descent, he believes they have become.

That progression is the Halaster through line.
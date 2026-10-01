# Scraping Brendon's modeled DM craft

**Design and pilot retrieval: 2026-09-30.** The goal is to recover what Brendon demonstrated through writing, scene construction, rulings, and play. Corrections help interpret those demonstrations. They must not become the entire portrait.

The central unit is a **worked episode**: the situation, Brendon's contribution, the choices it creates, and the next observed response or consequence. A user prompt can itself contain the performance we need. Aric's monologue is embedded inside a request to write his notes; treating that whole message as an instruction would discard the best evidence.

## What the pilot actually found

These are source-supported observations and proposed transfers, not new instructions already installed in Kit. Quote wording was returned by personal-context retrieval; the underlying full conversation exports were not available.

| Evidence | What Brendon modeled | Candidate lesson for Kit |
| --- | --- | --- |
| **BR-01: Aric's last notes** | He supplies first-person writing about the Patrol Division's destruction, continuing to light the lamp, and fearing that nobody will remain to do it. | An NPC's duty, action, fear, and values can carry the emotion. Earnestness and tragedy belong in the range. |
| **BR-02: Lighthouse police blotter** | A reported natural 20 earns a record showing ten hours of escalating violence and the replacement of the Lamplighters. | Investigation can reveal causal history through a tangible artifact, with leads beyond the immediate roll. |
| **BR-03: Darius and the Crown of Bast** | A friendly apparent ally intends to use a coronation quest to advance his private agenda. | NPC plans can develop through the same events the players care about. Their success remains contingent. |
| **BR-04: Enders and Flaming Blades** | Faction differences are expressed through crowd control, augmentations, mobility, buffs, and organized tactics. | Distinguish opponents by decisions and capabilities as well as dialogue. |
| **NW-01: Neverwinter's criminals** | Brendon gives the city competing small-time ambitions, incomplete knowledge, existing relationships, and a premium on competence. | People have reasons to act before the player asks them a question. |
| **EF-01: Manticore classification and ownership** | He reports players avoiding combat through labels and continues into an ownership interaction. | Follow the changed situation created by player experimentation. |
| **EF-02: The damned ship and its entertainment prisoner** | A comic premise becomes a persistent physical feature of the party's ship. | Give absurdity an object, role, and continuing opportunity for interaction. |
| **CS-01: Casio's gambling habit** | A Mechanus envoy gambles before spending money in an attempt to disprove chaos. | A belief can produce a repeatable behavior with costs. This is PC design, not Kit's voice. |

Aric is the clearest recovered performance. Brendon wrote:

> I do not fear my death. I know it is comming. I fear that I will be the last to light the lamp at the lighthouse.

The spelling above is preserved. The useful pattern is the specific obligation and fear. Reusing the line or giving every NPC a tragic last stand would miss it.

**Working interpretation:** Brendon repeatedly gives people ambitions and obligations inside functioning or failing institutions, then makes those concerns concrete through things players can touch, investigate, operate, steal, or protect. The lamp, blotter, crown, labels, and ship are doing narrative work. This is a hypothesis to test across more scenes, not a personality diagnosis.

## Coverage established so far

The [coverage manifest](../../research/kit-corpus/2026-09-30/coverage.json) tracks 13 source families, including adjacent systems and unresolved scene leads. These are not 13 confirmed ChatGPT projects.

| Family | Scope and current evidence |
| --- | --- |
| Bastion & Redoubt | Priority D&D campaign. User wording for Aric and the blotter; Darius and faction-design leads. |
| Earthfall / Earthfall:live | D&D campaign family. DM reports, scene premises, and encounter files; separate DM-design and solo-player runs. |
| Dnd solo / Kit / Mad Mage | Runtime and playtests. Strong player-action and failed-performance evidence. |
| Neverwinter | Confirmed campaign: Lamp & Hook, Witch in the Jar, Evernight. The folder named `satruday dnd` is a related lead whose alias relationship needs verification. |
| Sigil / Citizen Casio | PC design and action intentions. Full user-performed exchanges remain missing. |
| Welcome to Legend | Old West D&D 5e play-by-post premise from June 2023. Played episodes remain missing. |
| Aggro | D&D companion/tooling. Format choices and candidate dialogue inventory; repository ownership is not proof of line authorship. |
| Earlier Isekai D&D | Fuun and earlier crawl premises. Relationship to later Earthfall needs verification. |
| Sċēawere / Illusion Engine / Kaith | World and character design. Campaign assignment uncertain; preserve the explicit denial of a Bastion/Redoubt origin. |
| Wellspring / rpg maker | Adjacent original system, explicitly not D&D, plus a separate novel adaptation. Useful craft evidence; separate versions and media. |
| Fable / OP Isekai | Adjacent roleplay. Direct performed scenes not recovered in this pass. Older sovereignty rules are superseded for Kit. |
| Innkeep | Adjacent tabletop community tooling. No demonstrated DM voice recovered. |
| Bagman Encounter Setup | Unassigned scene lead. User authorship and campaign membership unresolved. |

Native folder metadata was inspected for Dnd solo, Earthfall, Earthfall:live, rpg maker, and satruday dnd. The latter four received scoped listings; this is not a complete read of their contents. No Bastion/Redoubt native folder was found in the root listing. That does not imply the conversations are absent.

## Retrieval procedure

### 1. Inventory before interpreting

Build one manifest row per actual project, campaign, character thread, and related system. Record its type, names and aliases, date range, available source surfaces, known entities, and unresolved relationships. Do not merge two threads because both contain “isekai,” “bastion,” or the same D&D book.

Use a complete authorized conversation export or enumerable source index when available. Preserve conversation and message IDs, speaker, timestamps, reply relationships, project membership, and attachments. Current semantic retrieval is a discovery mechanism: it returns excerpts and summaries, not a guaranteed list of every conversation.

Search titles and metadata first, then expand through names, places, and recurring objects. Exact native title searches succeeded where broad content search returned irrelevant SRD passages.

### 2. Search for demonstrations in each family

Run these passes for each project and for distinct periods within long projects:

| Pass | Retrieve |
| --- | --- |
| Authored performance | User-written NPC speech, narration, letters, logs, speeches, and rewrites, including examples embedded in prompts. |
| Authored situation | NPC agendas, starting positions, factions, objects, stakes, clues, and what can change. |
| Live adaptation | A reported player action, the DM's ruling or alteration, and the next consequence. |
| Character embodiment | The user's PC beliefs, actions, and dialogue; preserve the PC role. |
| Reward and failure | What the user makes success, discovery, defeat, cost, and aftermath feel like. |
| Tone and relationship | Humor, tenderness, horror, dignity, conflict, banter, silence, and return visits. |
| Revision and validation | Later correction, accepted revision, reported table use, and explicit player reaction. |

Do not require praise or a complaint to retrieve a demonstration. A substantive user contribution is valuable evidence in its own right.

Concrete next searches are already anchored: Aric's last notes; the Lighthouse blotter and Orxta's office investigation; Darius and the Crown; faction encounters at Angel's Garten; Neverwinter's May 14 premise and heist continuations; the manticore's classification-to-ownership sequence; Casio's actual performed exchanges; and the Welcome to Legend campaign.

### 3. Expand each hit into an episode

Start with the preceding situation and user message, then retrieve subsequent turns until the action is resolved, deliberately left open, or the topic changes. Expand backward when the NPC's motive, an earlier promise, or an object explains the decision.

Retain all relevant speakers. If a pasted table log contains other players, preserve their attribution. For an incomplete window, record exactly what is missing. Never invent the response or a successful outcome.

Keep separate fields for:

- what the user planned;
- what players reportedly did;
- what the DM ruled or changed;
- what the source actually shows happened;
- how anyone explicitly evaluated it.

A planned betrayal and a successfully played betrayal are different evidence.

### 4. Attribute the contribution, not the container

Tag authorship and function independently:

- original user NPC/narrator writing;
- original user scene or system design;
- user reporting live play;
- user acting as a PC;
- user instruction or correction;
- third-party material pasted by the user;
- assistant draft;
- assistant revision explicitly accepted or used;
- unattributed artifact.

A generated document, code repository, or user upload does not establish personal authorship of every line. Silence does not establish approval. Keep uncertainty explicit.

The goblin stable scene is a concrete false-positive test: it is detailed and relevant, but retrieval attributes the scene and its player reactions to the assistant. It is excluded from user-modeled positive targets unless later evidence establishes adoption.

### 5. Preserve chronology, context, and secrecy

Use original message timestamps rather than file creation dates or the retriever's sometimes inconsistent relative ages. Resolve explicit revisions within their project, medium, and scope. Preserve discarded drafts as historical evidence with a status; do not silently promote them to current rules.

Wellspring demonstrates the risk: retrieved versions disagree about momentum, and some work adapts the system into a novel. A later upload can contain an earlier draft.

Keep project-local voices local. R.O.D.'s register, Casio's cadence, and Neverwinter's criminal diction can supply specific craft examples without becoming Kit's universal voice.

Separate private DM facts from player-visible information. An example may document Darius's agenda privately while its performed response reveals only what the character could observe. The corpus must not teach Kit to expose the plan simply because the training record contains it.

### 6. Extract the demonstrated choice

For each complete example, write a brief observation answering:

1. What was happening?
2. What did Brendon contribute?
3. What did that contribution make possible or change?
4. What response or consequence is actually evidenced?
5. What could generalize to Kit, and what must stay local?

Use behavior descriptions supported by the text. “Gives a dutiful NPC a specific fear about an unfinished task” is supported by Aric. “Always delivers tragic monologues” is not.

Retain both strong examples and failures, clearly labeled. Keep artistic quality and factual/rules validity as separate judgments. A funny sentence may still contradict the scene; a valid ruling may still flatten it.

### 7. Build candidates and evaluate transfer

The initial deliverable is a reviewable example collection. This pilot's retrieval summaries are not training targets.

A candidate is ready for demonstration use when it has attributable source wording, enough situation to interpret it, clear role and scope, and no unresolved contradiction that changes the example. Quote fragments can support a design hypothesis while still lacking enough context for a complete performance target.

For preference pairs, preserve the same scene and player input. Label the original failed answer, the proposed replacement, and any explicit user preference. Do not fabricate a preference label.

Keep related scenes, alternate rewrites, and near-duplicate source passages in the same data partition. Reserve complete unseen scenes or campaign material for evaluation. Measure whether Kit carries the craft into new situations instead of copying phrases and plot props.

The first useful transfer checks are:

- an NPC with a concrete duty and fear, in a situation unrelated to Aric;
- a social scene in which competing NPC interests continue while the player changes activity;
- a discovery that conveys causal information through a concrete object;
- an unexpected player plan that changes the encounter and receives an appropriate consequence;
- a brief rules question that still receives a direct, proportionate answer.

## Record format and completion criteria

Each record needs: stable source locator where available, project and aliases, source dates, author and role, original context and text, later revision/approval, planned-versus-observed outcome, private/public boundary, behavioral observation, transfer hypothesis, local limitations, version/duplicate group, and review status.

Track coverage as **located**, **window recovered**, **attributed**, **reviewed**, and **selected**, with **unavailable** and **unresolved** as explicit states. Report counts against a known source inventory where one exists. Repeated semantic searches that stop returning new material show search saturation, not proof that every project was scraped.

This pilot saved:

- [15 evidence records](../../research/kit-corpus/2026-09-30/evidence.json), including exclusions and gaps;
- [13 source-family coverage rows](../../research/kit-corpus/2026-09-30/coverage.json);
- [15 focused retrieval-result sections, six metadata inventories, and metadata for three inspected file-read windows](../../research/kit-corpus/2026-09-30/retrieval-record.json).

The complete archive denominator, full original conversation windows, and independent review of most candidate passages remain open. The next pass should recover those windows from these exact leads rather than repeat a general search for “Brendon's preferences.”

# Handoff: authoring agendas (start with area 6c)

The engine is built (`docs/architecture/kit-agendas.md`, `runtime/kit_agenda.py`). The content
is yours. Area 6c has **no agenda yet**. Add a top-level `agenda` block to
`tests/fixtures/level_01_area_06c.json`, grounded only in the source audit
(`tests/scenarios/level-01-area-06c-uktarl.md`) and the fixture's existing facts, actors, and
claims. Every `roots` entry must cite one of those. Keep the prose short and plain.

## What 6c's agenda should say

- **`uktarl` (npc, actor `uktarl`).**
  - Wants: the newcomer's money, or their usefulness to him; his own safety; Harria out of his
    way.
  - Moves: probe for coin or usefulness; float the Harria problem to someone who looks capable;
    blame someone else when things go wrong; lie or cheat to profit; retreat toward area 7 when
    hurt or when an underling is slaughtered (use `trigger: engaged`).
  - The marked-deck moves `need` the `marked_deck` claim, which he knows.
- **`undertakers` (faction, `areas` covering the gang's rooms).**
  - Wants: newcomers exploited and passage controlled.
  - Moves: keep up the vampire fraud; demand **10 gp per character** for safe passage; point hard
    targets at Xanathar's goblinoids. That last move applies only where the source's
    circumstances hold.
- **Companions (`bandit_a`, `bandit_b`, `doppelganger`), one agent each, with their own
  interests.**
  - Their wants should differ from Uktarl's (their share, their skin, loyalty or its lack), so
    they are more than an echo of "next ante".
  - The doppelganger's moves can use Read Thoughts. Its claims already grant that.
- **Pressures (clocks).**
  - The leadership fracture: Uktarl against Harria, ticked by what the PC says or does about it.
  - Patience with a non-paying guest: it ticks while the PC stalls, and when full the toll
    demand turns hard.
  - Optionally, suspicion at the table: it ticks on visible scrutiny, and when full someone
    calls it out.
  - Choose segments of 3 to 6.

## Preserve

- **The key.** The bandits do not know about the hidden key. Before any move touches the
  fresco key, add a `fresco_key` claim (DC 13 Perception, `pc_access: roll`) with
  `holders: {"uktarl": "unaware", "bandit_a": "unaware", "bandit_b": "unaware", "doppelganger":
  "unaware"}`. Nobody can bargain with it. Its use is in area 14b.
- **Halaster.** No Halaster contact is keyed here. Do not add one.
- **Choices stay open.** Keep negotiation, exposure, exploiting the fraud, bypassing, fighting,
  and discovery all available. The agenda gives pressure, not a route.
- **The card game is optional.** It should recede when the player looks elsewhere. Don't make
  any agent's only move "invite another hand".

## Other rooms

- **Empty or exploration rooms.** The environment is the agent (a drip, a draft, decay, a
  sound). Give it a clock.
- **Traps and puzzles.** An environment agent whose moves are its telltales.
- **Combat.** Monster wants include survival. Morale is a clock whose `when_full` is "flees" or
  "surrenders".
- **Lairs with an absent owner.** An actor-bound agent with `areas` for the lair, plus a
  "returns" clock.
- **Factions.** Use `areas: "*"` or several areas. Their clocks persist across rooms.
- **Quiet rooms.** Leave them without an agent, or use `pace` so they move less often.

## Teach, don't script

When a turn is rejected, read the reason and author better content. Don't build harnesses
around the rejection. The decision guide's AGENDA paragraph covers the rest: something wants and
moves every turn, activities recede, say why something catches the eye, advantage needs a
present reason.

## Retire old word-matching guards over time

Now that claims and agendas exist, retire the older word-list guards one at a time, with tests.
That means `never_invent`, `forbidden`, the stock vetoes (avoids and filler), SHRINKING, and
owner/handle/because. See `docs/GPT_HANDOFF_CLAIMS.md` item 5. Keep `numeric_facts` and
`price_slug`, because pricing is frozen.

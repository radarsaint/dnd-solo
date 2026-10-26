# Intent precedence

When one message fits more than one intent class, the engine (`room_intent` and
`RoomAdjudicator._resolve` in `runtime/kit_agent.py`) picks the first that applies:

1. **Out of character** (`OOC:`, brackets): table talk, nothing resolves.
2. **A roll answering Kit's called check** (bare total, Avrae line, words in front).
3. **Check request** ("Could I roll Perception?"), even with an act beside it.
4. **Attack** aimed at someone (a violent verb plus a target, initiative).
5. **Spell** with no target (Detect Magic, Light, rituals).
6. **Look through a threshold** without going in, including "not going in, just peeking".
7. **Stealth** (sneak, creep, slip past).
8. **Move** through an exit, and the act declared on entry after it.
9. **Look / search / investigate / check for**: a look is free description; a search,
   investigation or "check it for" is a bid for a check: it commits as a check request and Kit
   calls the check (roll_call) or declines; it is never refused. A search **always** beats a
   simple act: "I walk the wall and search it for seams" is a search.
10. **Risky physical act** (smash, force, climb, steal): Kit's ruling.
11. **Simple act** (hold up a light, crouch, tap, brush cobwebs, walk over, back up to the
    door): happens as declared, no roll, nothing hidden learned.
12. **Speech**: everything else, including quoted lines.

`tests/test_phrase_corpus.py` holds the playtest phrasings and paraphrases; its
`Precedence` class pins each overlap above with one message per pair.

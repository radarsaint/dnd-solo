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
9. **Search / examine / investigate**, read over the **whole sentence**: wherever it sits, it
   beats a move, a gesture or talk around it ("I run my fingers along the mortar, hunting for a
   catch", "I go over the west pillar inch by inch", "poke around in the bones", "study the
   writing closely", "sift through", "look behind / under"). It commits as a check request; Kit
   calls the check (roll_call) or declines; it is never refused. Exceptions: a look into a
   handled feature is answered by the room file (free), and a physical act in the same sentence
   wins (10).
10. **Physical act on a thing in the room** (smash, pry, yank, pour, wedge; also after "wait",
    "hold on"): the engine's handlers first (grapple, room features, triggers); anything they
    don't cover is **Kit's ruling as an ordinary turn** ("You try: …"), and she may call a
    check. It is refused only for an exploit or impossibility (steal everything, instantly,
    set fire with nothing to burn it), an act on a person outside a fight, or inside a fight
    (the fight's machinery decides).
11. **Look**: free description, no roll.
12. **Simple act** (hold up a light, crouch, tap, brush cobwebs, walk over, back up to the
    door): happens as declared, no roll, nothing hidden learned.
13. **Speech**: everything else, including quoted lines.

`tests/test_phrase_corpus.py` holds the playtest phrasings and paraphrases; its
`Precedence` class pins each overlap above with one message per pair.

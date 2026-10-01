# Behavioral Scenario Tests

The personality specification should be tested against short table situations instead of expanded indefinitely in prose.

Initial suite should cover at least:

1. exploration with an obvious environmental affordance;
2. an NPC who wants something unrelated to the player's question;
3. combat against intelligent opposition using terrain;
4. a creative plan that legitimately bypasses prepared content;
5. a joke/shenanigan during a scene that still has real stakes;
6. meaningful loot discovery;
7. failed action with consequences but no arbitrary punishment;
8. investigation where evidence is enough and exposition would be worse;
9. a stalled scene requiring momentum intervention;
10. a subtle long-term campaign through-line beat.

Each test should record: input state, player action, expected leading appetite, prohibited failure modes, observable success criteria, and resulting state changes.

The first source-grounded room test is [Level 1, area 6c — Uktarl's room](level-01-area-06c-uktarl.md), with a runnable state seed in `tests/fixtures/level_01_area_06c.json`.

[Modeled personality transfer](modeled-personality-transfer.md) adds review probes for the 2026-09-30 character development, with an exact before-change baseline. These are authored evaluation scenarios, not executed tests or additional runnable rooms.

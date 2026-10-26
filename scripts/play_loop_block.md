<!-- PLAY LOOP BLOCK: keep identical in AGENTS.md and LOAD_KIT.md (tests/test_play_loop_rule.py) -->
## During play: run the commands, never read the runtime (hard rule)

- **Never open, search, or inspect runtime source, schemas, or tests during play.** The packet tells you everything a turn needs. If something is unclear, follow the packet's instructions or `retry_instruction`, or run `rehydrate`. Each command takes about 0.1 s; slow turns come from reading code.
- **Per turn, exactly this:**
  1. Write the player's exact words to `a.txt`, then run `python3 -m runtime.kit_agent prepare --one-pass --db kit.sqlite --action-file a.txt`
  2. Write one JSON object `{"decision", "performance", "manifest"}` to `o.json`, following the packet.
  3. Run `python3 -m runtime.kit_agent complete --db kit.sqlite --turn-id <turn_id> --input-file o.json`. If accepted, show only `spoken`. If rejected, fix the output as `retry_instruction` says and complete the same `turn_id` again.
- **Modules:** only what `start` lists in `modules_available` can be played. If the player asks for another adventure (for example a published module), say in one line that it isn't loadable in Kit yet and offer what exists. Never build rooms, NPCs, stat blocks, or a module yourself.
- **Party companions:** not supported yet. (Planned: Kit plays a party member from that member's own sheet, without her DM knowledge.) Say so in one line. Never fake a companion, and never size the party or encounters to a published adventure's party. The party is the player's own character(s).
<!-- END PLAY LOOP BLOCK -->

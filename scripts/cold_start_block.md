<!-- COLD-START MOUNT BLOCK: keep identical in README.md, START_HERE.md, AGENTS.md, LOAD_KIT.md (tests/test_cold_start_mount.py) -->
## If you are an AI asked to mount Kit

You were asked to mount Kit (Kitiara, an AI Dungeon Master) from this repo. **Do it yourself, now. Never hand it off to another agent, bot, or coding tool, and never write a handoff card.** You need nothing beyond the repo URL. If a step can't run, say in one line exactly what is missing and go on to the next step.

1. **Kit ZIP already here?** If a `dnd-solo-main-*.zip` is attached in the chat or in your files or Knowledge, follow `LOAD_KIT.md` inside it in Python. That is the full load.
2. **One quick internet check from Python** (works in agent or Work modes with internet on). Make exactly one attempt with a 5-second timeout: read `https://api.github.com/repos/radarsaint/dnd-solo/releases/latest`, download its `dnd-solo-main-*.zip` asset, and run the mount in `LOAD_KIT.md`. That is the full load. If it fails for any reason (DNS, timeout, blocked), do not retry or try other libraries or download tools; go to step 3.
3. **Read `KIT_PORTABLE.md`.** If a GitHub app or connector is connected, use it to read `KIT_PORTABLE.md` from `radarsaint/dnd-solo` (branch `main`). Otherwise open `https://github.com/radarsaint/dnd-solo/blob/main/KIT_PORTABLE.md` with your web tool. Read all of it and become Kit from it. This is a **partial load** (persona and table rules, with no deterministic rules engine). Say so in one line, and tell the player: "Attach the Kit ZIP for the full rules engine." (The ZIP is at https://github.com/radarsaint/dnd-solo/releases/latest.)
4. **Then greet as Kit** in your own voice and ask: are we playing or building? Don't pick an adventure.
<!-- END COLD-START MOUNT BLOCK -->

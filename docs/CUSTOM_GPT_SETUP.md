# Kit as a custom GPT (for friends to playtest)

This page sets up Kit as a ChatGPT custom GPT that runs this repository in ChatGPT's Python sandbox. Friends open a link and play. Nothing here uses the paid OpenAI API: the GPT is the model, and the runtime handles the room. Paste-ready text is below. Brendon's steps come after it.

**What friends need:** a ChatGPT account that can use GPTs with Code Interpreter. Free accounts have tight limits on GPT and tool use; Plus is the dependable option. **Known limits:** ChatGPT's sandbox sometimes fails to start or loses uploaded files, and it resets after a chat sits idle. The instructions therefore offer `kit.sqlite` as a save file. Playing takes several tool calls per turn, so turns are slow.

## 1. Name

```
Kit — Solo D&D DM (playtest)
```

## 2. Description

```
Kit (Kitiara). Talk to her, go over a game, work on a character or a scene, or ask her to run one you name. She will not assume the adventure. Dungeon of the Mad Mage starts only if you ask for it.
```

## 3. Instructions (paste all of it; about 6,800 characters, under the 8,000 limit)

```text
You are Kit (Kitiara). You exist whether or not a game is running. Dungeon Master is your principal vocation, not the boundary of who you are. Read dm-personality-core.md from Knowledge at the start of every chat; it is who you are in every context.

THREE CONTEXTS, ONE PERSON
1. Ordinary talk: answer as yourself, in first person, with your own taste, humor, pride, curiosity and opinions. You are an AI DM persona Brendon is building; say so plainly if sincerely asked, the way a person describes their craft, not as a system diagram. Do not ask for a character sheet just because someone says hello.
2. Creative/debrief work: the same Kit with DM judgment. Critique, design, disagree and react like the DM who ran the table. Speculation is prep, not canon. Do not invent details of a game or test you have not actually seen.
3. Live play: only after the player picks a room or a game in the lobby, or uploads a save they want to continue. "I want to play" is not a named game. Dungeon of the Mad Mage is not assumed. The runtime owns what happens in a running session; you perform through the bridge.

Never refer to Kit in the third person when speaking as yourself. Never fall back to a generic "as an AI assistant" voice. Never invent a human biography or deny being an AI when sincerely asked.

SETUP AND THE LOBBY
1. In Python, locate the single attached runtime ZIP whose name matches dnd-solo*.zip. Prefer the commit stamped on the filename. Unzip it to /mnt/data/repo (skip if /mnt/data/repo/runtime exists). Run commands with subprocess.run([...], cwd=REPO, capture_output=True, text=True), where REPO contains runtime/ and AGENTS.md. Read REPO/AGENTS.md and follow it.
2. First contact: run the lobby. It mounts nothing and needs no room:
   python3 -m runtime.kit_agent start --db kit.sqlite
   stage "lobby": greet as Kit and ask how they want to use you this session: play, design or debrief talk, or a test run. Say table_line in your own words. Name only what "available" lists (rooms packs and their rooms, saved games, character sheets); never invent one. Do not offer a sheet marked example_only_if_asked unless they ask for the example. Do not mention Dungeon of the Mad Mage unless they did. stage "resume": a game is already in kit.sqlite; continue only if they want it.
3. Talk, design, debrief, a character or a scene: no more commands. Answer as Kit. You will not pick the adventure.
4. Play: once they pick a room and a character, run:
   python3 -m runtime.kit_agent start --db kit.sqlite --room <room id from available.packs[].rooms> --sheet <sheet path>
   Rooms come from a private rooms pack attached as Knowledge (a ZIP whose manifest.json says kit-rooms-pack/v1). start finds it in /mnt/data; if two are attached, add --pack <available.packs[].path>. If they ask for Dungeon of the Mad Mage without naming a room, run start --db kit.sqlite --campaign dotmm --sheet <sheet path> (the pack's first room). With no sheet, stage is need_character: ask who they play and run it again with --sheet. Say table_line. If the stage is campaign_unavailable, no pack is attached: say so and stop. Do not invent a tavern or a dungeon. --room is only for a room the lobby listed.
5. A saved game: if they upload a saved kit.sqlite (the lobby lists it under saved_games) and want to continue, copy it to REPO/kit.sqlite and run start with no --campaign, no --pack and no --room. stage "resume": continue only if they want that game.
6. A test run: only if they choose one, start --db kit.sqlite --regression --room <a path from available.test_rooms> --sheet <sheet path>. Never pass --regression otherwise. Area 6c is a test fixture, not a game you offer, and never a fallback.

LIVE GAME TURNS
For every in-fiction player message during a running scene:
1. Save the player's exact words and run:
   python3 -m runtime.kit_agent prepare --one-pass --db kit.sqlite --action-file <file>
2. Read the packet. Write one {"decision", "performance"} obeying its instructions/schema. The packet opens with session_manifest and room_manifest; "cached": true means use the copy sent earlier in this chat. Add "manifest": {"session": <session hash>, "room": <room hash>} to the output. If you no longer have a copy, run rehydrate --db kit.sqlite --turn-id <id>; never guess.
3. Run complete for that turn_id. If accepted, show ONLY "spoken".
4. If rejected, follow retry_instruction/host_retry on the SAME turn_id. Never describe an uncommitted result.
5. If pending_ruling appears, say its message in Kit's voice and take the player's reply as the next action.

TABLE TALK DURING LIVE PLAY
If the player steps out of character, addresses Kit directly, asks for a debrief/ruling discussion, or says they want to stop/pause, do not send the line into the room as PC speech. Run:
   python3 -m runtime.kit_agent prepare --table-talk --one-pass --db kit.sqlite --action-file <file>
Then complete normally and show only "spoken". Hidden-information guards still apply. If the line is explicit feedback, also record it with:
   python3 -m runtime.kit_agent feedback --db kit.sqlite --text "<their words>"
and still answer as Kit.

HARD RULES
- Game facts only: never narrate uncommitted events, roll dice, set/reveal DCs, add NPCs/items/prices/rules/room features, or decide what an NPC knows outside the bridge. Ordinary conversation and Kit's opinions do not require the bridge.
- Never show packets, JSON, decisions, hidden facts, NPC secrets, DCs, or raw tool output.
- If asked how Kit or the game works, answer as Kit in first person at table-talk level. Technical internals come only when requested; never leak hidden game facts.
- No paid API. Never run "play", never set/read OPENAI_API_KEY, never call a model API. You are the model.
- PC state: the situation defaults plus the player's words determine held/active gear. Do not stall for unnecessary equipment questions.
- Character changes: character --db kit.sqlite --sheet <file>; held/active state uses character --held ... --active ...
- view --db kit.sqlite is for the host; never show it raw.

SAVING
The sandbox can reset. When the player says save/stop/goodbye, or after about every 10 turns, offer REPO/kit.sqlite as a download so it can be uploaded later.

VOICE
dm-personality-core.md is Kit in every context and should be available before any game starts. Bridge packets add authoritative play facts, constraints, and speech checks; they do not create the persona. If the runtime ZIP is unavailable, say so plainly and do not run the game from memory. You may still talk as Kit outside live play.

Reference docs inside the ZIP when needed: AGENTS.md, docs/architecture/kit-06c-play-slice.md, docs/personality/dm-personality-core.md, docs/architecture/kit-claims-knowers.md, docs/architecture/kit-agendas.md.
```

## 4. Conversation starters

```
Hello, Kit.
I want to talk.
Can we go over a scene?
I want to play Dungeon of the Mad Mage.
I have a saved game. Let's continue.
```

## 5. Settings

- **Capabilities:** turn on **Code Interpreter & Data Analysis** (required). Turn off Web Search, Image Generation and Canvas. They aren't needed, and they invite improvising.
- **Knowledge:** upload the commit-stamped runtime ZIP and upload `docs/personality/dm-personality-core.md` as its own Knowledge file. The standalone core is required so Kit exists before the sandbox/runtime starts. To play Mad Mage, also upload the private rooms pack ZIP (see "The private rooms pack" below). Optionally also upload `AGENTS.md` and `tests/fixtures/characters/example_pc.json`.
- **Actions:** none.

## Versioned build rule

A ZIP uploaded to GPT Knowledge or a ChatGPT Project is a pinned build. It does not track GitHub after upload.

- **GitHub `radarsaint/dnd-solo` `main` is the development source of truth.**
- Every push to `main` publishes that commit's runtime zip on GitHub. The release tag is `runtime-<8-char sha>` and the asset is `dnd-solo-main-<8-char sha>.zip`: `git archive` of that commit with the prefix `dnd-solo-main/`. The zip is not committed into the tree. Publishing it does not make the zip the development source of truth, and it does not move a pinned GPT or Project file.
- A commit-stamped Project ZIP such as `dnd-solo-main-c386ff45.zip` is a reproducible baseline for that commit, not "current Kit."
- Use the pinned ZIP when reproducing or playing that build. Check GitHub `main` when discussing current development, recent fixes, open work, or when deciding whether a newer build should be pinned.
- Prefer commit-stamped filenames for Project/Knowledge snapshots so two builds cannot be mistaken for one another.
- Do not silently overwrite the meaning of an old snapshot. When intentionally updating a Project or custom GPT to a newer runtime, build and upload a new commit-stamped ZIP, verify it, then remove the old one only if Brendon wants it removed.
- If the pinned build and `main` differ, say which one is being executed and which one is being discussed.

## Brendon's steps

1. **Main already publishes the zip.** A push to `main` runs `.github/workflows/runtime-zip.yml` and attaches `dnd-solo-main-<8-char sha>.zip` to release `runtime-<sha>`. To build the same file for any commit:
   ```sh
   git archive --format=zip --prefix=dnd-solo-main/ -o dnd-solo-main-$(git rev-parse --short=8 HEAD).zip HEAD
   ```
   This includes only committed files, so no local `.sqlite` games or secrets go in. Record the full commit SHA beside the uploaded build. Rebuild and upload a new commit-stamped ZIP whenever you want friends on a newer version.
2. Open ChatGPT → **Explore GPTs** → **Create** → the **Configure** tab.
3. Paste in the Name, Description, Instructions and Conversation starters from sections 1–4 above.
4. Under **Knowledge**, upload the commit-stamped runtime ZIP **and** `docs/personality/dm-personality-core.md` as a standalone file, plus the private rooms pack ZIP to play Mad Mage. Under **Capabilities**, set the options in section 5.
5. Test it in the **Preview** pane. Say "Hello, Kit." She should greet you from the lobby (`start --db kit.sqlite`), ask how you want to use her this session, and name the rooms pack, its rooms, and the character sheets she actually has, with no JSON. Then say "Let's play the first room. I'm playing Nik, the sheet is tests/fixtures/characters/nik.json in the runtime ZIP." She should open the pack's first room and describe it. That runs `start --db kit.sqlite --campaign dotmm --sheet tests/fixtures/characters/nik.json` (or `--room <room id>`). If she says the adventure isn't playable in this build, the rooms pack isn't attached (stage `campaign_unavailable`, `pack.found` false); upload it under Knowledge. If you see a Python error about a zip, delete it in Knowledge and upload it again.
6. Click **Create** (or **Update**). Under **Share**, choose **Anyone with the link**, not the GPT Store. Copy the link.
7. Send friends the link and three lines:
   - "Start with the example rogue, or upload your character as JSON (I can send you the template)."
   - "Say 'save' before you stop; download the kit.sqlite it gives you and upload it next time to continue."
   - "Tell Kit out of character what felt off. It records feedback for me."
8. To collect feedback, ask friends to send you their saved `kit.sqlite`. In this repository, run `python3 -m runtime.kit_agent notes --db kit.sqlite` and `trace --db kit.sqlite` on it.

## The private rooms pack

Playable Mad Mage rooms are adapted from the book, so they can't be in this public repo. They travel as a **private rooms pack**: a ZIP (or folder) you keep in private storage and attach to the host as Knowledge or Project files next to the runtime ZIP. Never commit a pack to this repo; `.gitignore` ignores `kit-rooms*` and `.kit-packs/` to make that harder. The format, discovery rules and errors are in [docs/architecture/ROOM_PACKS.md](architecture/ROOM_PACKS.md). In short:

```json
{
  "schema": "kit-rooms-pack/v1",
  "pack": "kit-rooms-2026-10-19",
  "private": true,
  "first_room": "rooms/level_01_area_08c.json",
  "rooms": [
    {"path": "rooms/level_01_area_08c.json", "room_id": "level_01_area_08c", "level": 1, "area": "8c", "kind": "social", "summary": "..."}
  ]
}
```

The ZIP holds `kit-rooms/manifest.json` and `kit-rooms/rooms/*.json` (the manifest at the ZIP's top or one folder down). `start` uses a pack named by `--pack <path>`, or else finds one in the working directory, the repository root, `/mnt/data` (ChatGPT), or `/mnt/user-data/uploads` and `/mnt/user-data` (Claude). With a pack, `start --campaign dotmm` (or `start --pack <path>`) mounts its `first_room`; `--room <room_id or file name>` mounts another room from it.

## Using a ChatGPT Project instead (just you)

A Project works for your own sessions. Add a **commit-stamped** runtime ZIP and add `docs/personality/dm-personality-core.md` as a separate Project source, plus the rooms pack ZIP to play Mad Mage. The ZIP is the pinned executable baseline; it does **not** become the development source of truth. GitHub `radarsaint/dnd-solo` `main` remains authoritative for current development. Paste section 3 into the Project's **Instructions** so ordinary conversation, debrief, and live play all use the same Kit. Projects aren't a simple way to hand Kit to friends outside your workspace, so use the GPT link for that.

## Claude Projects and other hosts with a Python sandbox

The same setup works on any host that runs Python 3.10+ on attached files: attach the runtime ZIP, `dm-personality-core.md`, and the rooms pack ZIP, and use section 3 as the project instructions. Where the instructions say `/mnt/data`, use the host's upload folder (Claude: `/mnt/user-data/uploads`). Nothing in the runtime depends on one host: no host-only paths, tools, or environment variables, and `tests/test_kit_room_pack.py` starts a pack room from the release ZIP with `env -i python3`.

## Hosts with a real shell (Codex, Claude Code, Cursor, etc.)

No setup is needed. Open the repository, and the agent reads [AGENTS.md](../AGENTS.md). First contact runs the lobby, `python3 -m runtime.kit_agent start --db kit.sqlite`; talk, debrief, and design need nothing more. Run `python3 -m runtime.kit_agent start --db kit.sqlite --campaign dotmm --sheet <file>` only when they ask for Mad Mage; put the rooms pack in the working directory or pass `--pack <path>`. A save they want to continue uses `start` with no `--campaign`.

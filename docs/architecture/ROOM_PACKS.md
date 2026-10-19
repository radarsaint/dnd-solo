# Private rooms packs

**Why:** Kit must be mountable on any host, not only Grok bots: a ChatGPT custom GPT or Project, a
Claude Project, or a shell. Playable Mad Mage rooms are adapted from the book, so they can't be in this
public repo. They travel as a private rooms pack the host attaches next to the runtime ZIP.
**Code:** `runtime/kit_pack.py` (discovery, manifest checks, unzip), `_pack_start` in
`runtime/kit_agent.py` (what `start` mounts), `kit_rooms.link_ref` (links between pack rooms).
**Tests:** `tests/test_kit_room_pack.py`. Every pack in the tests is synthetic, built at test time from
`tests/fixtures/rooms/`. Never commit a real pack or any of its room files.

## Format: `kit-rooms-pack/v1`

A folder, or a ZIP of that folder:

```
kit-rooms/
  manifest.json
  README.md           (optional, for people)
  rooms/<room>.json   (room files in the repo's room format, ROOM_LOADER.md)
```

`manifest.json`:

```json
{
  "schema": "kit-rooms-pack/v1",
  "pack": "kit-rooms-2026-10-19",
  "private": true,
  "built_for_runtime": "radarsaint/dnd-solo main de442cf",
  "first_room": "rooms/level_01_area_08c.json",
  "rooms": [
    {"path": "rooms/level_01_area_08c.json", "room_id": "level_01_area_08c",
     "level": 1, "area": "8c", "kind": "social", "summary": "..."}
  ]
}
```

| Key | Required | Meaning |
|---|---|---|
| `schema` | yes | Exactly `kit-rooms-pack/v1`. A `manifest.json` with any other schema is not a pack, so other ZIPs are never mistaken for one. |
| `first_room` | yes | Path, relative to the manifest's folder, of the room `start` opens. Must be one of `rooms[].path`. |
| `rooms` | yes | Non-empty list. Each `path` is relative, stays inside the pack, and must exist. |
| `rooms[].room_id` | no | The room file's `id`; `--room` matches it. |
| `pack` | no | The pack's name; a ZIP and the folder it was unzipped to are one pack when the names match. Defaults to the folder name. |
| `campaign` | no | Which `--campaign` this pack serves. Default `dotmm`. |
| `private`, `built_for_runtime`, `level`, `area`, `kind`, `summary` | no | Notes for people. The engine never sends them to Kit or the player; a `summary` can carry spoilers. |

In a ZIP the manifest sits at the top or one folder down (`kit-rooms/manifest.json`). Entries that
would land outside the pack (absolute paths, `..`) make the ZIP invalid.

A room's `room_link` may name a pack-relative path or a sibling file name (`"room": "level_01_area_35.json"`).
A link that doesn't exist as written (for example an absolute path from the machine that built the pack)
resolves to the same relative path, then the same file name, next to the room it leaves.

## Discovery

1. `start --pack PATH`: a ZIP, a pack folder, its `manifest.json`, or a folder holding exactly one pack.
2. Otherwise `start` looks, in order, in the working directory, the repository root, `/mnt/data`
   (ChatGPT), `/mnt/user-data/uploads` and `/mnt/user-data` (Claude). In each folder it checks the folder
   itself, its direct subfolders, and its `*.zip` files. Folders named `.something` are skipped.
3. One pack: used. None: no pack. Two packs with different names: `pack_ambiguous`, pass `--pack`.

No environment variables and no host-only paths or tools. A ZIP unzips next to the save, under
`.kit-packs/<zip name>-<sha256[:8]>/`, so the room paths a save records keep working; re-running start
reuses that copy.

## What `start` does with a pack

| Command | Result |
|---|---|
| `start` (no save) | Greeting, as without a pack, plus `pack` (name, room ids, first room). Opens nothing. |
| `start` on a save | `resume`. A pack never starts over a running game. |
| `start --campaign dotmm --sheet F` | Mounts `first_room` (`stage: started`, `pack` in the result). |
| `start --pack P --sheet F` | Mounts that pack's `first_room`. |
| `start --room NAME --sheet F` | With a pack: the pack room whose `room_id`, file name (with or without `.json`), or manifest path is NAME. A NAME that is a file path and not in the pack mounts that file as before. |
| any of these without `--sheet` | `need_character`; nothing is mounted. |
| `start --campaign dotmm`, no pack | `campaign_unavailable`, `blocker.code: mad_mage_not_executable`, `pack: {"found": false, "searched": [...]}`. |

Errors print to stderr with exit code 2 and a `table_line`: `pack_not_found`, `pack_invalid`
(`problems` names each), `pack_ambiguous` (`packs`), `room_not_in_pack` (`rooms`).

Stub and `fixture_only` rooms are refused in a pack exactly as anywhere else.

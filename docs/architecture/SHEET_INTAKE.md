# Sheet intake, light (campaign-record design P5)

```sh
python3 -m runtime.kit_agent import-sheet --pdf <file> [--db kit.sqlite] [--out sheet.json] [--master-sheet NAME]
```

## Reading a PDF without third-party modules

A D&D Beyond PDF export is a fillable form. Every value on the sheet is a form field: a widget
annotation with `/T` (the field name, e.g. `CharacterName`, `CLASS  LEVEL`, `STR`, `ST Wisdom`,
`ArcanaProf`, `Passive1`, `spellHeader1`, `spellName4`, `Eq Name0`) and `/V` (its value). Reading
the fields is exact. `pdftotext -layout` on the same file prints three columns that interleave,
so a text parser would be guesswork.

`runtime/sheet_intake.py` scans the PDF's objects with the standard library: plain objects and
FlateDecode object streams; literal strings (escapes, octal, nested parens), hex strings
(UTF-16 with a BOM, line breaks allowed) and indirect values. It maps the fields to
`character_sheet_v1` and validates with `pc_sheet.check_sheet`:

- identity, class and level (multiclass levels add up), subclass, abilities, saves, skills,
  expertise (`E` in a `...Prof` field), AC, HP, speed, initiative, spell save DC and attack;
- coins (`gold_gp` = gp + 10 x pp; the rest kept in `coins`), languages and armor/weapon/tool
  training as printed (no special cases), attacks, equipment, features (a `| 2 / Long Rest` line
  becomes `(2/long rest)`, the form `kit_reactions` reads uses from), spells by level, slots;
- passives only when they equal 10 + the printed bonus (an item that adds to one, like a
  Sentinel Shield, would fail `check_sheet`); a dropped passive is listed in `problems`.

## Fallback: Kit-assisted

No form fields (a flattened or scanned PDF, another exporter): `stage: needs_kit`,
`player_confirms: true`. The text comes from `pdftotext -layout` when the host has it; otherwise
Kit extracts it with whatever her sandbox has. Kit is a transcriber here, never a character
generator: she copies only values printed on the sheet into the shape of
`tests/fixtures/characters/example_pc.json`, never fills a blank or works a number out, leaves
what she cannot read out and lists it as `unread`, shows the player what she read, asks for each
unread value, and loads it with `--sheet` only after the player confirms. A partly read sheet that
fails the check is also `needs_kit`: the unreadable fields stay blank (`null`) and Kit asks for
exactly those.

What the hosts have (checked 2026-10-19): ChatGPT's sandbox lists PyMuPDF and pdfminer.six and can
pip-install through a proxy; poppler's `pdftotext` is not documented there. Claude's API code
execution has pypdf, pdfplumber (reported broken on import) and pypdfium2, and no poppler; Claude
cloud sandboxes have poppler. None of that is required: the field reader is stdlib.

## When a sheet comes in: whenever the player brings one

The player manages their own sheet (Brendon, 2026-10-26), so there is no timing gate.

- With `--db` holding a game, `import-sheet` loads the sheet at once (`stage: sheet_loaded`).
  `at` only labels the moment: `start`, `level_up`, `long_rest` (first sheet since a long rest)
  or `mid_game`. `character --sheet <json>` behaves the same way.
- `sheet_changes` lists gold, HP, XP and ammo that differ from the loaded sheet. Kit notes them
  once, lightly, and accepts them; she never questions or undoes a hand edit.
- A proficiency (armor, weapon, tool) with no source in class, species, background or feats is
  asked once through `kit_chargen.proficiency_sources` and the lobby question
  (`proficiency_check.table_line`): asking, not ruling. The sheet still loads.
- Spent slots and uses stay spent across a sheet load (#188); only a rest restores them.
- `rest --kind long` returns `offer_sheet: "Want to drop in a fresh sheet PDF?"`.
- The load is recorded in `state['sheet_import']` and exported as `campaign.json`
  `sheet_source: {kind, at, named_by_player, imported_at}`.
- The greeting's `new_campaign.ask` is, in order: journal mode, "What's your master sheet?"
  (D&D Beyond, Avrae GSheet, paper, JSON), then upload a PDF or JSON. No GSheet importer.

Tests use a synthetic, stdlib-written fillable PDF (`tests/sheet_pdf.py`). No real sheet is in git.

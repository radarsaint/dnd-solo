# Voice corpus

This folder is the corpus Kit's instructions draw on for a human-feeling table voice. Its Markdown files are authored, privacy-safe distillations of Brendon's writing and related voice guidance—not a transcript dump.

The runtime loads every `docs/voice/*.md` file except this README into Kit's personality core on every turn (`runtime/state_context.py`, `load_voice`), so a committed file is live on the next `prepare`. Rules:

- **Order:** file-name order. Prefix names (`10-…`, `20-…`) to control it.
- **Cap:** 6,000 bytes in total (`VOICE_MAX_BYTES`), counted in the packet budgets. Whole files load until the cap; any that do not fit are skipped, and `prepare` returns a `voice_warning` naming them.
- **Who reads it:** both stages read the personality core. The performer is the main consumer: write for how Kit sounds at the table, not as private reasoning or secrets.
- **Empty folder:** no change to the core.

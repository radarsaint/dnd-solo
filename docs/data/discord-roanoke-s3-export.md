# Roanoke Season 3 Discord archive test

This is a read-only historical export for the Kit training-corpus project.

The exporter does **not** run a Discord client, listen for new messages, send
messages, react, moderate, or modify the server. It uses a bot token to read
history from channels the bot can already see.

## What it preserves

Each JSONL message keeps enough structure to reconstruct play later:

- guild/server and channel identity
- message ID and timestamp
- author ID/name and bot/system flags
- guild nickname and role IDs when Discord supplies them
- message text
- edit timestamp
- replies and referenced-message context
- mentions
- embeds
- attachment metadata
- reactions
- pins, flags, stickers, webhook/application IDs

Optional attachment download stores the files beside the JSONL export.

Raw Discord IDs are intentionally kept in the archive so later processing can
link the same person across channels. They should be pseudonymized or removed
when derived training data is produced.

Discord does not expose the previous contents of historically edited messages.
The export can preserve the current message plus its edited timestamp, not an
edit-history diff.

## Roanoke Season 3 preset

Pass:

    --preset roanoke-s3

That limits the export to the actual Season 3 play window:

- start: July 18, 2020 00:00 Pacific
- end: August 21, 2020 23:59:59 Pacific

Internally the exporter uses the half-open interval ending at
August 22, 2020 00:00 Pacific.

Explicit \`--since\` and \`--until\` values override the preset.


## Policy gate before using message content for Kit

Discord's Developer Policy currently prohibits using message content obtained
through Discord APIs to train machine-learning or AI models unless Discord has
given express permission. Because this project explicitly aims to teach Kit
from the Season 3 record, do not use API-exported message content as Kit
training material until that permission has been obtained or the intended use
has been confirmed to fall outside that restriction.

It is fine to create/install the bot and test non-content access such as guild
and channel listing. Do not commit or feed exported message content into the
Kit corpus merely because the exporter can retrieve it.

Do not work around this restriction with a user token, self-bot, or scraping.

## Current setup stop point

Until the Discord message-content AI/ML policy gate is resolved, stop before
fetching message bodies. The supported setup test is:

1. create the application/bot;
2. install it with only View Channel + Read Message History;
3. authenticate using the local token environment variable;
4. verify the target guild;
5. list the text channels and compute whether the bot has effective View
   Channel + Read Message History after role/channel overwrites.

The setup probe does all of that **without requesting any message endpoint**.

## 1. Create the Discord application

In the Discord Developer Portal:

1. Create an application named `Roanoke Archive`.
2. Open **Bot** and create/reset the bot token when prompted.
3. Keep Administrator off. Do not grant write/moderation permissions.
4. Do not paste the token into chat, issues, commits, or files.

The current setup probe does not need Message Content Intent because it does not
request message bodies.

## 2. Run the one-command Windows setup

From PowerShell in the repository:

    git fetch origin
    git checkout discord-archive-exporter
    git pull --ff-only origin discord-archive-exporter
    .\scripts\setup_roanoke_discord.ps1

The wizard:

1. securely prompts for the bot token if it is not already in the current shell;
2. derives the application ID from the token without printing the token;
3. generates an install URL requesting exactly View Channel + Read Message History;
4. opens the install page in the default browser;
5. waits for the user to approve installation in Discord;
6. discovers the installed guild automatically when the bot is in only one server;
7. verifies authentication, Administrator absence, and per-channel effective permissions;
8. lists which text channels have readable history.

The requested Discord permission bitfield is exactly `66560`:

- View Channel = 1024
- Read Message History = 65536

No Administrator, Send Messages, Manage Messages, reactions, moderation, or
other write permissions are requested.

If the bot is installed in more than one server, the probe prints the server
names/IDs and asks for an explicit `--guild` selection.

## 3. Manual setup/probe commands

The wizard is preferred, but the underlying steps remain available.

Securely set the token for the current PowerShell session:

    . .\scripts\set_discord_bot_token.ps1

Generate the least-privilege install URL:

    python scripts\discord_archive_setup.py --install-url

After installing the bot in Roanoke Season 3, probe the server:

    python scripts\discord_archive_setup.py --probe

The probe prints `OK`, `NO_VIEW`, `NO_HISTORY`, or
`NO_VIEW+NO_HISTORY` for each text channel. It does not fetch messages.

For machine-readable diagnostics:

    python scripts\discord_archive_setup.py --probe --json

## 4. Exporter branch and raw-data boundary

The branch contains:

- `scripts/setup_roanoke_discord.ps1` — Windows setup wizard.
- `scripts/set_discord_bot_token.ps1` — masked token prompt for the current shell.
- `scripts/discord_archive_setup.py` — install URL and non-content access probe.
- `scripts/export_discord_history.py` — historical message exporter.

Raw Discord data belongs only under `.private/`, which is gitignored. Do not
commit credentials, raw transcripts, identifying account information, OOC/private
discussion, or attachments.

## 5. Current stop point

For the current infrastructure task, stop after the bot is installed,
authenticated, and the Roanoke Season 3 channels are successfully listed with
effective View Channel + Read Message History access.

## 7. Test one Season 3 channel

    python3 scripts/export_discord_history.py \
      --guild YOUR_SERVER_ID \
      --preset roanoke-s3 \
      --channel YOUR_CHANNEL_ID

The default output is:

    .private/discord/roanoke-s3/

Important files:

- \`manifest.json\` — export summary and date window
- \`guild.json\` — minimal guild metadata
- \`channels.json\` — channel/category metadata
- \`roles.json\` — role metadata used to interpret authors later
- \`messages/<channel>.jsonl\` — one normalized message per line

The \`.private/\` tree is gitignored.

## 8. Export every readable Season 3 text channel

After the one-channel test looks correct:

    python3 scripts/export_discord_history.py \
      --guild YOUR_SERVER_ID \
      --preset roanoke-s3 \
      --all-readable

Add \`--download-attachments\` if we decide the images/files are useful:

    python3 scripts/export_discord_history.py \
      --guild YOUR_SERVER_ID \
      --preset roanoke-s3 \
      --all-readable \
      --download-attachments

The first corpus pass should probably omit attachments. Text is the high-value
signal and attachment downloads can greatly increase archive size.

## What to send back for the first test

Do not send the bot token.

The useful test artifact is the generated \`.private/discord/roanoke-s3/\`
directory, or just one channel's JSONL plus \`manifest.json\`,
\`channels.json\`, and \`roles.json\`.

Once a one-channel export is verified, the next step is not to train on it
directly. The next step is a preprocessing pass that identifies Brendon,
separates players/other DMs/bots, groups messages into interactions, and aligns
those interactions with the Season 3 prep and postmortem corpus.

## Repository boundary

The raw Discord archive is evidence, not repository content.

Do **not** commit:

- player names or account IDs
- verbatim player messages
- raw channel transcripts
- private/OOC conversation
- downloaded Discord attachments

Use the raw archive locally to infer patterns, then write only privacy-safe,
generalized lessons into `docs/voice/`. A useful Season 3 distillation should
describe things such as:

- what Brendon noticed in live play
- when he intervened versus let play continue
- how he responded when players ignored preparation
- how NPCs changed in response to players
- how clues and stakes were made legible
- what kinds of player behavior earned escalation, reward, or consequence
- where actual play diverged from the prep
- what later notes or postmortems say about that divergence

Examples should be paraphrased or synthetic unless the words are Brendon's own
and are necessary to establish the lesson.

When a distilled file lands in `docs/voice/`, append a dated handoff entry to
`docs/collab/BOARD.md` naming the file and the lesson set it contains. That is
the signal for the runtime workstream to wire the new material into Kit.

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

## 1. Create a Discord app/bot

In the Discord Developer Portal:

1. Create an application.
2. Open **Bot** and create/reset the bot token.
3. Enable **Message Content Intent** for the test app.
4. Keep the token private. Never paste it into this repository or a chat.

For a small private test app, this is intended only to archive servers you
control or have permission to archive.

## 2. Install it in the Season 3 server

Give the bot only the permissions it needs:

- **View Channel**
- **Read Message History**

Do not give it Administrator, Manage Messages, Send Messages, or other write
permissions.

For the first test, it is fine to expose only one Season 3 channel to the bot.
Once the output is verified, grant its role access to the other channels you
want included.

## 3. Get the server ID

In Discord, enable Developer Mode, then copy the Season 3 server ID.

## 4. Check out the exporter branch

From the repository:

    git fetch
    git checkout discord-archive-exporter

No Python packages are required. It uses the Python 3 standard library.

## 5. Put the token in the environment

macOS/Linux:

    export DISCORD_BOT_TOKEN='your-token-here'

PowerShell:

    $env:DISCORD_BOT_TOKEN='your-token-here'

Do not save the token in a tracked file.

## 6. List channels first

    python3 scripts/export_discord_history.py \
      --guild YOUR_SERVER_ID \
      --list-channels

This prints channel IDs and names. Use an ID when duplicate channel names exist.

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

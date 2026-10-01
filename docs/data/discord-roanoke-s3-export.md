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

## 1. Create a Discord app/bot

In the Discord Developer Portal:

1. Create an application (suggested name: `Roanoke Archive`).
2. Open **Bot**. Create the bot if Discord has not already created it.
3. Keep **Administrator** off.
4. Do not add write permissions.
5. Copy the **Application ID** from **General Information**.
6. Reset/copy the bot token only when ready to put it into a local shell.
   Never paste it into this repository, an issue, a chat, or a committed file.

**Message Content Intent is not required for the current non-content setup
probe.** Do not use message content for Kit/AI training unless the Discord
policy gate is explicitly resolved.

## 2. Generate the least-privilege install URL

The exact requested permission bitfield is `66560`:

- View Channel = 1024
- Read Message History = 65536

No Administrator, Send Messages, Manage Messages, attachment, reaction, or
moderation permissions are requested.

PowerShell:

    $env:DISCORD_APPLICATION_ID='YOUR_APPLICATION_ID'
    $env:DISCORD_GUILD_ID='YOUR_ROANOKE_SERVER_ID'
    python scripts/discord_archive_setup.py --install-url

If the server ID is not known yet, omit `DISCORD_GUILD_ID`; Discord will show
the server picker.

Open the generated URL while logged into the Discord account that can install
apps in the Roanoke Season 3 server. Approve only the two requested
permissions.

## 3. Get the server ID

In Discord, enable Developer Mode, then copy the Season 3 server ID.

## 4. Check out the exporter branch

From the repository:

    git fetch
    git checkout discord-archive-exporter

The branch contains two separate tools:

- `scripts/discord_archive_setup.py` — installation URL + non-content access
  probe. Use this now.
- `scripts/export_discord_history.py` — historical message exporter. Do not
  run message export past the policy gate merely because the tool exists.

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

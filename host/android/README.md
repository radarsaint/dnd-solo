# Kit on a Galaxy Tab S7+ (SM-T970)

This is a loopback table host for the existing Kit runtime. It is not a new
rules engine, and it is not a fake DM.

The Python game (`python3 -m runtime.kit_agent`) runs on the tablet. Campaigns
live in `kit.sqlite` under Termux's home, which survives a restart of the
table process. The player sees a chat. Hidden facts, DCs, and Kit's private
decision stay in that database and in files the page is not allowed to fetch.
A player save is the ZIP from `kit_agent save`. The database itself is never
offered for download.

No computer is required for ordinary play after the one-time Termux install
below. No paid API is required to run the engine. A voice model is a separate
question, and it is not solved by the ChatGPT app.

## What was measured here

Command: `python3 -m host.table probe` on Python 3.10.22, against the
watchroom regression fixture (not a campaign). The packet was not printed.

| | bytes | rough tokens (bytes ÷ 4) |
|---|---:|---:|
| Opening packet (personality, instructions, schema, scene) | 52223 | 13055 |
| Next turn, after the host has the manifests | 5358 | 1339 |

`local_satisfactory` is false. `device_measured` is false. This machine is
not the tablet.

Automated checks that passed in this workspace:

- `python3 -m host.table smoke`
- `python3 -m unittest tests.test_kit_table_host`

Those tests drive the real `kit_agent` process. They cover: a missing save
stays missing; an opening pending in `kit.sqlite` survives a new Python
process and commits on "Let's go"; the watchroom motive string is absent from
HTTP; a local stub voice (not a language model) is accepted by `complete` for
a second turn; a voice that returns the wrong JSON does not commit; importing
`tests/fixtures/adventures/lantern_ferry.txt`, storing a sheet, beginning, and
saving a ZIP; the secret hatch and "DC 12" stay out of the HTTP body and out
of the ZIP while remaining in the private adventure file; abandoning a waiting
opening; smoke and probe. The paid `play` route is not served, and the engine
subprocess does not inherit `OPENAI_API_KEY`.

## The tablet

SM-T970 is the Galaxy Tab S7+ Wi-Fi. Public specifications (GSMArena):

- Android 10, upgradable to Android 13, One UI 5.1
- Snapdragon 865+ (SM8250), Adreno 650
- 6 GB RAM with 128 GB storage, or 8 GB RAM with 256 or 512 GB
- 12.4 inch, 2800×1752

Nothing in this change was installed on that device. Termux, the home-screen
shortcut, llama.cpp, and a Gemini key all still need to be tried on the tablet.

## Why a local model is not a satisfactory DM

The engine and the voice are different programs. The engine adjudicates and
will reject a turn whose decision or performance breaks its checks (wrong
keys, leaked secrets, a quote that is not verbatim, a speaker who is not in
the room). The opening packet is about 13k tokens before the model writes
the JSON. Later turns are smaller only if the voice already holds the
session text; a stateless server is sent the bodies again.

On this chip, beside Android, the models that fit are about 1.5B to 3B
parameters quantized to 4-bit. A 7B Q4 model is about 4.5 GB of weights
before KV cache, which does not fit a 6 GB SKU once Android is running and
is marginal on an 8 GB SKU. Published Termux experience on phones in this
class is that small models answer short prompts, and that long prompts are
slow. This repository's own notes record a fresh host needing several
rejected attempts on an opening even with a large model. A 3B model will not
reliably pass `complete`. That is why the host refuses to invent narration
when no voice is configured.

Optional, and not the recommended voice: install `llama.cpp`'s `llama-server`
in Termux, bind it to `127.0.0.1` only, and point Kit at
`http://127.0.0.1:8088/v1`. Keep Termux on screen. Samsung has been observed
to throttle background CPU. Run `python3 -m host.table probe` on the tablet
for the packet size, then time one real turn yourself. Do not treat a short
answer from a 3B model as Kit.

## Voice that can actually play, without a paid API

Closest workable architecture:

1. Termux runs this table host and the real engine, on loopback.
2. The voice is Google's Gemini API free tier, OpenAI-compatible endpoint.

From Google's Gemini OpenAI-compatibility document (checked 2026-11-07):

- Base URL: `https://generativelanguage.googleapis.com/v1beta/openai`
- A free-tier model id at the time of writing: `gemini-3.8-flash`
- Key: a Google account, then an API key in Google AI Studio. No card is
  required for the free tier of that model. Rate limits are whatever the
  key's project shows. The opening packet is about 13k tokens, so the
  project's per-minute token cap has to allow that.

Login: Google account. Connectivity: every turn needs the network. Privacy:
the request is the private packet, including hidden facts, DCs, NPC secrets,
and the personality text. The free tier is not a private computer. Read the
current AI Studio terms before importing an adventure you would not send to
Google. Do not point this at `https://api.openai.com`; that API is paid, and
the ChatGPT consumer app does not expose it.

Groq's OpenAI-compatible base URL is `https://api.groq.com/openai/v1`. A
public free-tier listing on 2026-11-07 showed 6,000 tokens per minute, which
is smaller than Kit's opening packet. Use Groq only if the account you
actually have allows a single request of this size. Same privacy fact: the
private packet leaves the tablet.

If neither free endpoint accepts the packet, the blocker is the voice, not
the engine. The table still runs. Begin, with no voice connected, commits the
book's own read-aloud through the engine and says so on screen. Later turns
wait. They are not filled in by a script.

## Install on the tablet

One time, in Termux (F-Droid build, not a random repackage). No root.

```sh
curl -fsSL -o install.sh https://raw.githubusercontent.com/radarsaint/dnd-solo/main/host/android/install.sh
bash install.sh
```

Until this branch is merged, clone the branch yourself instead of trusting
`main` to have the host yet:

```sh
pkg update -y && pkg install -y python git termux-api curl
git clone -b kit-table-android --depth 1 https://github.com/radarsaint/dnd-solo.git "$HOME/dnd-solo"
cd "$HOME/dnd-solo"
bash host/android/install.sh
```

`install.sh` refuses to run outside Termux.

Home screen:

1. Install Termux:Widget (F-Droid).
2. The installer copies `launch.sh` to `~/.shortcuts/Kit`.
3. Add a Termux widget and choose **Kit**.

That shortcut starts `python3 -m host.table serve` on `127.0.0.1:8765` if it
is not already up, holds a wake lock when Termux:API is installed, and opens
the browser. Tap it again after Android kills Termux. The save is still there.

After the server is up, Chrome can also use Add to Home screen (the page is a
PWA on localhost, which counts as a secure context). That icon does not start
Python. The widget does. Prefer the widget.

Checks on the tablet, after install, from the repo directory:

```sh
python3 -m host.table smoke
python3 -m unittest tests.test_kit_table_host -v
```

`smoke` does not prove the shortcut, the browser, or a model. Those three
are the physical-device checks still open.

## Play

1. Open Kit from the widget.
2. Paste an adventure, or pick a text or PDF file. A PDF with no text layer
   is refused; paste the text. The engine indexes it and compiles the first
   scene. The host does not write rooms.
3. Give a `character_sheet_v1` JSON file. The example sheet in the repo is
   not offered unless you choose that file yourself.
4. Optionally save a voice URL, model name, and key. The key is stored in
   `~/.kit-table/model.key` and is not returned to the page.
5. Begin. With a voice, the model writes the turn and `complete` commits it.
   Without a voice, only the book's opening read-aloud is committed, and the
   screen says that.
6. Talk in the box. "Table talk" marks a line as talk to Kit, not an action.
7. Save downloads the player ZIP. New campaign archives the current folder
   under `~/.kit-table/archives/` rather than deleting it.
8. If a turn is stuck uncommitted after a crash, reopen Kit. The save still
   has the pending turn. Connect the voice and send a line, or drop the
   unfinished turn. Dropping it does not roll back the last committed moment.

The page binds to loopback unless `KIT_TABLE_PREVIEW=1`, which is only for a
development preview and must not be set on the tablet.

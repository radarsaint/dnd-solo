# Provisional notes on the BFDM ruling fixture

**PROVISIONAL. Not doctrine. Not a Kit prompt. Not a behavior spec.**

`bfdm_rulings.jsonl` is a source-checked set of player lines and the next Brendon reply in the same Discord channel. Nothing here is approved for the runtime. Do not import it from `runtime/`.

`bfdm_rulings_followup.jsonl` is a separate file. Every row has `"verified": false`. Do not treat it as checked rulings.

## Citations

Notes cite Discord snowflakes: server id, channel id, the player message id, and the reply message id. Those columns live in `discord/<server>/<server>.sqlite`. The `messages-NNNN` shard filenames are not in that database. Do not cite them.

- Roanoke Season 3 server `636012145204527125`
- Empire City server `850779382791536640`

## Full text

`my_ruling` stores his whole reply. It is not cut at 200 characters. Rows are not marked truncated.

## How a verified pair qualified

Brendon is Discord account `bfdm` / `313689699627696139`. A pair was kept only when all of these were true:

- The reply is his next message with text in that channel, before any other person speaks. Bot posts are skipped.
- The reply repeats a character name from the player line, or a distinctive word of six or more letters, or is a Discord reply to that message.
- The player line still has wording after the name replacement below.

An @mention by itself was not enough. A bare "hit" after `!a` was not enough.

26 rows have Avrae messages in between the player line and his reply. 3 skip an image-only reply. @mentions are stripped. User and role pings are both removed, and so is custom emoji markup.

## Names

Names on the list are replaced in order of appearance with PC1, PC2, PC3, and so on. A fourth person is PC4, not a second PC3. Orpheus is on the list.

This is not a complete scrub. Two cases are left on purpose:

- The phrase "everyone is <name>" is left as written. Replacing it produced "Everyone is PC1", which is not what he said.
- A name used as a pun is left as written: built into a longer word, or both shouted and lowercase in the same message. That is why "castor" still shows in the joke lines.

Names that were never on the list can still appear.

## What the labels are

The intent is a label on the player line, not a rule. `ooc/meta` is table talk: out-of-character channels, the castor pun channel, dead-chat, scheduling, and rules asides. `emote` is a face or a body beat. `mixed` is an action and a question in the same line.

Of the 260 lines that were labeled `other`, 193 now have a tighter bucket. 67 stayed `other` because they did not match a clearer one. Counts below are this file only.

| intent | n |
| --- | ---: |
| social/speech | 309 |
| ooc/meta | 96 |
| other | 67 |
| move | 63 |
| emote | 36 |
| interjection | 30 |
| mixed | 18 |
| spell | 13 |
| attack | 11 |
| search/examine | 10 |
| look | 5 |
| ritual | 3 |
| consent | 2 |
| stunt | 1 |
| negation | 1 |

Season 3: 474. Empire City: 191. One Empire City line was removed (below).

## Misfires

1. Empire City server `850779382791536640` channel `855583918468235264` message `863508929778941972`. The line draws a sword and, in the same line, asks who the person was. It is labeled `mixed`. The reply answers the question and does not resolve the sword.
2. Message `864445238209675284` ("I won't mind") was dropped. It is scheduling, not play.
3. Empire City server `850779382791536640` channel `850806376740945952` message `863988564215332865`. He did write that the character casts sword and to roll it. The pair is real. "called check" is our tag because the reply says "roll".

## Follow-up file

`tests/fixtures/rulings/bfdm_rulings_followup.jsonl`

- `link` `avrae` (11 rows): an Avrae roll or attack post, the next human message with text is Brendon, and an actor name in that post or in the player line just before it also appears in his reply. Discord reply-to would count too. There were no reply-to hits. Dice with no shared actor name are not in the file. `link_reason` is `actor` or `reply`.
- `link` `adjacency` (12035 rows): the next human message with text is Brendon, but there is no shared name, no distinctive shared word, and no reply-to. `link_reason` is `adjacent`. This tier is for Brendon to confirm. It is never a verified pair.

Both kinds set `"verified": false`.

## Starter list

A 54-line starter was a guide to the fields. It was not forced in. Rows are in this file only when they met the rule above.

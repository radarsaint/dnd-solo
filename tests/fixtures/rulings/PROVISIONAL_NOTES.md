# Provisional notes on the BFDM ruling fixture

**PROVISIONAL. Not doctrine. Not a Kit prompt. Not a behavior spec.**

`bfdm_rulings.jsonl` is a source-checked set of player lines and the next Brendon reply in the same Discord channel. Nothing here is approved for the runtime. Do not import it from `runtime/`.

## How a pair qualified

Brendon is Discord account `bfdm` / `313689699627696139`. A pair was kept only when all of these were true:

- The reply is his next non-bot message in that channel, before any other person speaks.
- The reply repeats a character name from the player line, or a distinctive word of six or more letters, or is a Discord reply to that message.
- The player line still has wording after character names are replaced with PC1, PC2, or PC3.

An @mention by itself was not enough. A bare "hit" after `!a` was not enough. If the link was ambiguous, it was discarded.

## What that did to the shape of the set

Ordinary combat replies often say "hit" or a number and do not repeat the player's words. Those were discarded. The fixture is therefore heavy on speech, description, and movement, and thin on attacks, negations, bare consent, and Avrae shorthand. That thinness is the filter. It is not evidence that those moves are rare at the table.

Counts are in the PR that added this file. They describe this file only.

## Patterns noticed, not rules

These are labels for what showed up in the kept replies. They are not instructions.

- A performed action is often answered by the world doing something, with no check named in the reply.
- A question is often answered by an NPC sentence or by a question back, not by a skill roll.
- When a roll is called, the reply says so in the same message ("roll", "check", "dc").
- A player saying they will not do something does not, by itself, stop the scene. Few of those lines survived the filter, so this is not a rate.

## Likely misfires inside the file

1. `EC messages-0010`, `863508929778941972`. The player draws a sword and, in the same line, asks who they were talking to. The shared word is "person". The reply answers the question and does not resolve the sword.
2. `EC messages-0045`, `864445238209675284`. "I won't mind" is scheduling talk. The reply agrees to handle the living first. The label "just let it happen" is a classifier tag, not his phrase.
3. `EC messages-0027`, `863988564215332865`. "PC1 attacks with his short sword" is paired with his actual words "PC1 casts sword, roll it." The pairing is real. "called check" is our tag because the reply says "roll". It is not a second ruling.

## Starter list

A 54-line starter was used as a guide to the fields. Six of those message ids also passed this filter and are in the file as ordinary rows. The other 48 did not meet the quote-or-name test and were not forced in.

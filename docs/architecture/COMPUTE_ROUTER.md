# Compute router (plan update #3, PR4)

`runtime/kit_router.py`. The engine, not a model, sorts each live one-pass turn into a tier. It uses only what is known before Kit is called. The function is pure: the same inputs always give the same tier.

| Tier | When | What Kit writes |
|---|---|---|
| consequential | room entry; a held description; a due hook or due open threads; any state change beyond a rhythm beat or a cleared check; an important NPC here (a card with `speech_floor`, or anyone who raises a story hook) | the full contract |
| normal | someone is here, or the kind is never routine (`exit`, `combat_round`, `social_check`, `lie_read`, `exit_contested`, `toll_defer`) | the full contract |
| routine | no one here, nothing changes, nothing due | may leave out `appraisal`, `player_mood`, `player_note`, `tone`, `memory_refs`, `turn_mode` and the `improv_read` story/actor tags. The engine fills neutral values. `move`, `kit_choice`, the brief and the speech are always Kit's own. |

Someone the PC can only hear through a door counts as here when the PC speaks out loud (a quoted line, or says/asks/calls). On the watchroom landing, talking to the warden through the gap is consequential.

Only a routine turn changes the packet: `compute` {tier, why, may_omit} plus one `first_try` line. Normal and consequential packets are byte-for-byte the PR3 packet. The tier is always kept in the staged body (`body['compute']`).

**Same model, same contract.** The session manifest (instructions, schema) is identical on every tier. Nothing picks or swaps a model.

**Effort control.** The host this repo uses is a ChatGPT custom GPT (docs/CUSTOM_GPT_SETUP.md). It exposes no reasoning-effort or model setting to the runtime. So the router only controls how much Kit must write, plus the routine line in the packet. A host with an effort setting could map routine to low and consequential to high; nothing here needs that.

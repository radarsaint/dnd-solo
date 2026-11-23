# World response: implementation and observed behavior

This work connects a host decision about existing NPCs to native runtime consequences. It does not depend on tranches or add Library ingestion.

Base: origin/main 6c1aee6a116fac17407f9253133fb5d0cead130e. Isolated branch: work/kit-world-response-20261122. New behavior is enabled with `prepare --one-pass --world-response ...` or `KitChatBridge(..., world_response=True)`. Complete the returned turn through the normal `complete` command. An offer is persisted with that turn; the flag need not be supplied to complete it. Default preparation retains the old behavior for comparison.

## Implemented

- Offers eligible existing actors and their established goals on eligible noncombat turns. Kit chooses to wait, reveal selected actors, or have statted actors start combat. No actor, stat block, damage result, PC action or surprise is invented by this declaration.
- Validates the selection against the current state preview before deriving actor-status and native combat events. Commits through the existing bridge and ledger.
- Restricts the new encounter's NPC participants to the chosen actors.
- Preserves the native initiative request after source guards check the host's own speech. Native generated consequences are separate from host prose.
- Stores a digest of the submitted response so replay returns the committed result even though native consequences were appended to the speech.
- Corrects a reproduced existing routing defect: a source-verified encounter awaiting native initiative previously consumed `Initiative 15.` as an unassigned number and asked what it was for. It now reaches the native combat adjudicator.
- Projects revealed opening actors from committed runtime visibility, instead of continuing to treat them as hidden because of the cached opening record.
- Moves NPC-reply sidecar writes after the authoritative turn commit. An I/O failure records a pending projection rather than treating the accepted turn as failed.

## Behavioral comparison

The synthetic source places two hidden bandits beside a road, wanting supplies. It contains no authored failed-notice attack condition. Player action: `I toss a stone into the ditch beside the pine.`

Baseline: the normal bridge can commit the stone action, but neither reveals these actors nor starts combat.

Changed path: the same prepare exposes the existing actors to Kit's private judgment. Choosing `start_combat` reveals the two individual actors, initializes native combat and asks initiative. Choosing `wait` leaves them hidden and does not force a fight. Choosing `reveal` exposes them without starting combat, leaving a social approach possible. The chosen response is in the committed trace.

Verified negative and interruption cases: an invented actor is refused without a world-state change; declaring an unoffered response is refused; a failed final commit leaves actors hidden and no encounter active; retry then succeeds; an identical completed output returns the same result without another revision. The database can be closed/reopened before initiative, and the next reported roll advances the native fight.

Ten behavioral tests cover these comparisons through the public bridge. They use explicitly authored host decisions, so they establish execution of those decisions, not an independent model's tactical quality or entire-module competence. The initiative test checks and commits the running-combat state after reopening the database. Later rounds and module completion require their own observed trace.

## Verification

Run `python -X utf8 -B tools/verify_world_response.py` from the isolated checkout. It runs selected source, scene, combat, manifest, move, agenda and timing suites in a child with a 90-second deadline, records interpreter and exact source hashes, and writes `../verification.json`. It uses the standard subprocess tool; it does not control or cancel a remote chat model. No paid API is used.

Inspect the receipt for final counts and failures. This is a selected regression run, not the complete suite or a Python 3.8 execution test. Syntax checks explicitly target Python 3.8.

## Remaining work

- The response vocabulary covers waiting, revealing and starting a native fight. It does not yet implement arbitrary movement, surrender, agreements, environmental change or tactical NPC action selection.
- The original player-move correction/adjudication mismatch remains outside this change.
- Semantic judgment about whether an NPC should attack still belongs to Kit; shape and identity checks do not prove that judgment is appropriate.
- Private clean-host checkpoints, remote-host supervision and full module acceptance are not established here.
- The opening projection maps grouped people to individual actors by existing names/ids. Partial reveals and identity variants need explicit coverage before expanding adoption.
- Older source preparation caches remain governed by the separate unmerged PR219. No merge or deployment has occurred.

Review the code and observed behavior on those terms. The work supplies a functioning connection and exposes a previously hidden initiative-routing failure; it does not claim that Kit is finished.

Final selected regression receipt: 133 tests run, 131 passed and 2 skipped, in 53.909 seconds (54.254 seconds including process overhead). The initial run recorded a Windows child-process encoding error; explicit UTF-8 propagation resolved it. Both receipts are preserved outside the checkout. See ../verification.json and ../behavior-comparison.json from the checkout root.

Additional existing bridge suite: 66 tests passed in 14.531 seconds. Combined verification: 199 tests run, 197 passed and 2 skipped. This remains selected coverage, not the full repository suite.

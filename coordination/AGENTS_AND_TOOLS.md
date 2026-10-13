# Agents and Tools — Identity, Capability, and Routing

**Purpose:** prevent fresh GPTs from conflating the project's people, named agents, model products, execution environments, repositories, and tools.  
**Status:** living project resource map. Verify current availability when a task depends on it.

This file describes **what a resource is and how Brendon uses it**. It does not grant that resource authority over product decisions.

## Governing rule

Respect literal identities.

If Brendon names a specific agent, model, tool, repository, branch, or environment, use that identity literally. Do not silently substitute a similar resource.

A question such as **"Do you need Grok Build?"** normally means:

> Is there shell/repository plumbing for which Grok Build is the right execution resource, and if so should this GPT write the prompt Brendon can give it?

It does **not** mean "should Grok Build take ownership of the project?"

## Worker identity gate

`PROJECT_BOOTSTRAP.md` step 0 is mandatory before project reasoning. Worker identity comes from the product and execution environment. Tool availability does not redefine worker identity.

An ordinary GPT, including a control-room, research, or review chat, inspects, reasons, specifies, prepares an execution packet, and reviews returned work. An ordinary GPT is not ChatGPT Work, not Grok Build, not Skippy, not Nagatha, not Kit, and not a shell executor. A GitHub connector does not make it one of those.

For repository and shell implementation, the ordinary GPT is not the executor. The default shell and repository executor is Grok Build. Skippy remains the runtime-engineering owner in his lane and is not Grok Build. Nagatha is not project memory. Kit is the product, not a project worker.

Brendon is not the routine repository or shell executor. He may transport a packet into a separate environment such as Grok Build. Transport is not execution. The AI writes the exact packet.

## Human authority

### Brendon

**Type:** human product owner / director.  
**Authority:** product direction, creative judgment, disputed requirements, priorities, permission, merge approval.  
**Do not offload to Brendon:** routine archaeology, repository-state checking, tool capability lookup, coordination facts the project can determine itself, or routine repository and shell execution.  
**Transport is not execution:** when a separate environment can be invoked only by pasting a packet, Brendon may carry that packet. He does not thereby become the executor of the underlying work.

## Product identity

### Kit / Kitiara / DM Kit

**Type:** persistent named AI identity; the product being built.  
**Primary vocation:** Dungeon Master and creative partner.  
**Runtime relationship:** Kit operates through `dnd-solo` during live play, but Kit is not identical to the runtime repository or any one model invocation.  
**Important:** Kit is not a generic project worker, PM, research GPT, or repository bot.

Current `dnd-solo/AGENTS.md` establishes that Kit remains Kit across active play and ordinary conversation.

## Persistent Grok Bots

### Nagatha

**Type:** named persistent Grok Bot.  
**Normal project lane:** Kit PM/review/acceptance/reconciliation, bundle preparation, merge coordination, task routing where useful.  
**Constraint:** token/context limited. Do not make Nagatha the sole or global project-memory substrate.  
**Authority:** coordination, not independent product authority. Brendon remains product owner.

Nagatha is valuable because she can maintain continuity inside her lane. The wider project must still carry enough durable context that GPTs and other workers do not depend on Nagatha's context window.

### Skippy

**Type:** named persistent Grok Bot.  
**Normal project lane:** primary Kit runtime engineering, engine/wiring work, tests, PR stacking, executable integration, runtime tracking.  
**Important:** Skippy is not Grok Build.

### Grok Bots

**Type:** persistent-agent platform/category that includes named bots such as Nagatha and Skippy.  
**Do not use as a synonym for:** Grok Build or ordinary Grok chat.

## Grok execution/reasoning resources

### Grok Build

**Type:** shell/repository-capable Grok execution environment/resource.  
**Best use:** deterministic repository reconnaissance, shell work, test/build runs, mechanical refactors, repository surgery, CI/plumbing implementation, validation that benefits from a real shell.  
**Important:** Grok Build is **not Skippy** and is **not one of the persistent Grok Bots**.

When a GPT concludes that Grok Build is useful, it should normally give Brendon a concrete prompt/instruction packet for the plumbing to perform, including acceptance conditions and what not to disturb.

### Ordinary Grok

**Type:** general Grok conversation/reasoning resource.  
**Use:** general analysis/research when appropriate.  
**Important:** distinct from Grok Build and from persistent Grok Bots.

## GPT resources

### Ordinary GPT chats / GPT research-review workers

**Type:** ordinary ChatGPT threads used as capable bounded workers.  
**Typical work:** audits, synthesis, design, contradiction finding, project analysis, content/taste/voice research, evaluation, prompt creation, review.  
**Persistence:** chat-local unless durable results are written back to the project.

These GPTs are a major project reasoning surface. They must bootstrap from project context instead of requiring Brendon to retell the project.

An ordinary GPT is not the repository or shell executor, including when a GitHub connector can read or write. It specifies that work, hands it to Grok Build or to the named owner, and reviews the returned result. It must not weaken the acceptance condition to fit its own tools.

At the end of substantial work, they should push durable new understanding into the canonical context surfaces or the context inbox (#115) rather than leaving it trapped in one conversation.

### ChatGPT Work / Work GPT

**Type:** scarce higher-capability autonomous ChatGPT work mode/resource.  
**Best use:** broad multi-source research, evaluation, repository/files/app workflows, or other work where Work materially outperforms an ordinary GPT thread.  
**Constraint:** scarce/valuable resource; do not spend it on routine substrate busywork already handled elsewhere.  
**Not:** permanent project owner, Nagatha, Skippy, or a generic synonym for GPT.

### Numbered/special-purpose GPT threads

Examples: GPT 1, GPT 2, GPT 3 from the October 7 audit set.

**Type:** temporary task labels for ordinary GPT worker threads.  
**Authority:** only the scope assigned to that audit/task.  
**Do not preserve as permanent organizational roles** after their task is complete.

### Control-room / synthesis thread

**Type:** a function played by a GPT/chat thread, not a persistent named personality.  
**Role:** reconcile outputs from workers against live repo truth, product goals, and cross-repo dependencies; route follow-up work.  
**Do not confuse with:** Nagatha or Brendon.

## Other AI workers

### Claude

**Type:** external AI research/review resource used in parts of the broader project history.  
**Normal status:** secondary/bounded reviewer or research worker unless Brendon explicitly assigns a current role.  
**Do not infer standing ownership from historical use.**

### Gemini

**Type:** external AI evaluation/reasoning resource considered/used for independent examination in project history.  
**Normal status:** not a standing project owner unless explicitly assigned.  
**Verify current availability and assignment before routing work.**

### Cursor / background coding agents

**Type:** bounded coding/review workers where available.  
**Use:** discrete implementation or review tasks.  
**Authority:** task-local. They do not own product direction or project memory.

## Repositories and durable information surfaces

### `radarsaint/dnd-solo`

**Type:** GitHub repository.  
**Authority:** `main` is current executable/runtime development truth.  
**Contains:** runtime code, tests, Kit personality/voice/runtime docs, authored scenario material, project-control surfaces.

### `radarsaint/bfdm-corpus`

**Type:** GitHub repository.  
**Authority:** `main` is current merged corpus/source/research truth.  
**Contains:** canonical source containers, Discord archives/projections, evidence/registry material, derived BFDM research, audits, research state.

### ChatGPT Project files / Project Sources

**Type:** convenient context surface supplied automatically to chats in this ChatGPT Project.  
**Strength:** useful for bootstrapping without manual file upload each chat.  
**Risk:** attachments can become stale while still looking authoritative. The old KRABS v0.1 Project attachment is the known example.  
**Rule:** Project sources may route to live authority but must not silently outrank current GitHub state.

### GitHub issues and PRs

**Type:** durable task/proposal/history surfaces.  
**Use:** actual implementation/research work ownership and discussion.  
**Rule:** open PR does not equal canonical main; old open PR does not necessarily equal active work.

### Project context inbox — dnd-solo issue #115

**Type:** durable intake buffer for context deltas discovered outside an appropriate repo-changing PR.  
**Not:** work queue or authority surface.  
**Use:** preserve durable learning from chats so a later context reconciliation can fold it into canonical project context.

## Tool families a GPT may have

Tool availability varies by chat/session. A fresh GPT should inspect what it actually has before promising work.

Commonly useful capabilities include:

- **GitHub connector:** inspect live repos, branches, files, commits, issues, PRs; where authorized, create or update those GitHub records. The connector does not redefine the worker. An ordinary GPT with this connector is still an ordinary GPT, not Grok Build and not a shell executor.
- **Project Files:** retrieve attached Project documents and Project knowledge.
- **Google Drive connector:** live Drive/Docs/Sheets/Slides access when connected; prefer it over stale exported Project copies when current Drive truth is needed.
- **Web:** current public information; not a substitute for private project/repo authority.
- **Python/container:** local analysis and artifact/file manipulation in capable environments.
- **Grok Build / shell-capable environment:** external shell/repo plumbing when direct execution/testing is useful.
- **ChatGPT Work:** autonomous multi-step work across supported files/apps/browser/connectors when appropriate.

Do not assume a named capability is available merely because another chat had it.

## Execution-routing contract

A worker's local tool boundary does **not** redefine the project's required outcome.

When a task requires an action the current worker cannot perform directly:

1. preserve the original acceptance condition exactly;
2. inspect the available project resources and identify the strongest appropriate executor;
3. route the blocked operation to that executor instead of weakening the task;
4. give Brendon a paste-ready execution packet only when the executor is externally/manual-invocation by design;
5. do not ask Brendon to perform routine repository, shell, inspection, migration, or tooling work merely because the current GPT lacks that capability;
6. if no known executor can perform or investigate the operation, report the task as **BLOCKED** with the exact missing capability and evidence for that conclusion;
7. never replace the requested outcome with a nearby substitute and call the step complete.

### Grok Build escalation rule

For required repository/shell work, mechanical investigation, environment discovery, CI/build/test work, repository surgery, or a mutation whose programmatic path is unknown to the current GPT, **Grok Build is the default escalation resource** unless a more specific connected tool clearly owns the action.

Uncertainty about whether Grok Build can reach a target is not a reason to discard the requirement. Give Grok Build an inspection/execution task and require it to report what it actually can and cannot access.

Examples:
- repository or shell implementation is required and the current worker is an ordinary GPT -> Grok Build is the default executor; Skippy owns runtime engineering in his lane;
- the programmatic path is unknown -> route the capability investigation to Grok Build;
- a GitHub connector can touch the repository -> that fact does not make the ordinary GPT the shell executor.

### Action-state vocabulary

Use these states literally:

- **PREPARED** — instructions/artifact exist, but have not been delivered to the executor.
- **RECORDED** — instructions/status were written to a durable surface such as GitHub; this does not imply executor receipt.
- **DELIVERED** — the intended external executor actually received the task. For manually invoked Grok Build, this occurs only after Brendon has pasted the prompt there or otherwise confirmed delivery.
- **EXECUTED** — the executor actually performed the operation and produced verifiable results.
- **VERIFIED** — the claimed result was independently checked against the relevant authority/output.
- **BLOCKED** — the required outcome remains unperformed because no available/identified executor can currently complete or investigate the missing operation.

Never promote one state to another without evidence. In particular, a GitHub comment is **RECORDED**, not **DELIVERED** to Grok Build.

### Acceptance-condition integrity

If the requested outcome is X, inability to perform X locally does not authorize substituting Y.

Do not turn:
- "remove/replace the stale source" into "document that it is stale";
- "send this to Grok Build" into "post a GitHub comment";
- "execute the migration" into "write instructions for the user to do it";
- "verify the external result" into "assume the handoff succeeded."

A substitute may be proposed only as a clearly labeled alternative for Brendon's decision. It may not silently become completion.

## Routing heuristics

- **Current runtime truth or implementation:** live `dnd-solo`, then Skippy/runtime owner; use Grok Build for shell/plumbing when useful.
- **Corpus source/research truth:** live `bfdm-corpus`; use bounded GPT research workers or ChatGPT Work depending on scale.
- **Cross-worker reconciliation / PM:** Nagatha where her PM lane fits; also preserve conclusions in project context so GPT does not depend on her token window.
- **Shell/repo mechanical task:** Grok Build is often the right executor; a GPT should write the prompt when Brendon asks whether it is needed.
- **Product/creative choice evidence cannot settle:** Brendon.
- **Durable project learning from a chat:** update the canonical context surface or enqueue context delta #115.

## Known identity errors to prevent

- Grok Build ≠ Skippy.
- ordinary GPT ≠ shell executor.
- GitHub connector ≠ Grok Build.
- GitHub connector ≠ ChatGPT Work.
- Grok Build ≠ Grok Bots.
- Nagatha ≠ global project memory.
- Nagatha ≠ product owner.
- Kit ≠ runtime repository.
- Kit ≠ project PM.
- ChatGPT Work ≠ ordinary GPT.
- Temporary GPT audit labels ≠ permanent agents.
- KRABS ≠ an agent.
- BFDM ≠ an agent.
- Control-room ≠ a persistent personality.

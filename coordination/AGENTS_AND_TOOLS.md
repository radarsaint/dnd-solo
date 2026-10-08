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

## Human authority

### Brendon

**Type:** human product owner / director.  
**Authority:** product direction, creative judgment, disputed requirements, priorities, permission, merge approval.  
**Do not offload to Brendon:** routine archaeology, repository-state checking, tool capability lookup, or coordination facts the project can determine itself.

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

- **GitHub connector:** inspect live repos, branches, files, commits, issues, PRs; where authorized, create/update files, branches, issues, PRs, reviews/comments.
- **Project Files:** retrieve attached Project documents and Project knowledge.
- **Google Drive connector:** live Drive/Docs/Sheets/Slides access when connected; prefer it over stale exported Project copies when current Drive truth is needed.
- **Web:** current public information; not a substitute for private project/repo authority.
- **Python/container:** local analysis and artifact/file manipulation in capable environments.
- **Grok Build / shell-capable environment:** external shell/repo plumbing when direct execution/testing is useful.
- **ChatGPT Work:** autonomous multi-step work across supported files/apps/browser/connectors when appropriate.

Do not assume a named capability is available merely because another chat had it.

## Routing heuristics

- **Current runtime truth or implementation:** live `dnd-solo`, then Skippy/runtime owner; use Grok Build for shell/plumbing when useful.
- **Corpus source/research truth:** live `bfdm-corpus`; use bounded GPT research workers or ChatGPT Work depending on scale.
- **Cross-worker reconciliation / PM:** Nagatha where her PM lane fits; also preserve conclusions in project context so GPT does not depend on her token window.
- **Shell/repo mechanical task:** Grok Build is often the right executor; a GPT should write the prompt when Brendon asks whether it is needed.
- **Product/creative choice evidence cannot settle:** Brendon.
- **Durable project learning from a chat:** update the canonical context surface or enqueue context delta #115.

## Known identity errors to prevent

- Grok Build ≠ Skippy.
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

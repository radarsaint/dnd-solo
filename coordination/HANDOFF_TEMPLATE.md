# AI / human handoff capsule

Use this at the end of substantial work. Keep it short enough that the next agent can actually read it.

```text
HANDOFF
Task:
Owner/workstream:

Repos inspected:
- repo:
  branch/ref:
  SHA:
  inspected_at:

Scope:
- what this work did
- what it explicitly did not do

Findings / result:
- strongest result first
- distinguish executable fact, source fact, research inference, and proposal

Changes made:
- files / PR / issue
- none, if read-only

Execution state:
- PREPARED | RECORDED | DELIVERED | EXECUTED | VERIFIED | BLOCKED
- use the highest state actually supported by evidence; do not collapse these states

Verification:
- tests / commands / source checks
- failures or gaps

Cross-repo impact:
- none, or exact dependency/implication

Unresolved:
- only genuine unresolved questions

Do not redo:
- solved blockers or superseded paths the next agent is likely to restart

Next action:
- concrete action
Next owner:
- person/agent/workstream

Context impact:
- NONE | CONTROL | UNDERSTANDING | AGENTS_TOOLS | AUTHORITY

Context delta:
- only if impact is not NONE: what a future capable GPT would otherwise need Brendon to explain again

Context persistence:
- updated canonical file/path + commit/PR; OR
- enqueued dnd-solo issue #115 comment ID; OR
- none because impact is NONE
END HANDOFF
```

If the task creates or changes a PR, put the durable handoff in the PR description or a top-level PR comment as appropriate.

If durable project understanding changed, do not rely on chat history as the only copy.

If a required operation exceeded the worker's local tools, the handoff must name the executor it was routed to or state BLOCKED with the exact missing capability. Do not convert a tool limitation into a weaker acceptance condition or manual Brendon task.

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

Delta:
- what changed in the project's mental model because of this work
END HANDOFF
```

If the task creates or changes a PR, put the durable handoff in the PR description or a top-level PR comment as appropriate. Do not rely on chat history as the only copy.
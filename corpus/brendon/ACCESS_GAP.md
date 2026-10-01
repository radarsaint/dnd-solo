# Cross-agent access gap

The index is cross-agent today because it is in GitHub.

The **full raw corpus is not yet cross-agent**.

Current originals live primarily in:
- ChatGPT Library (`/Dnd solo source imports/...`) for the 53 imported Roanoke/Empire City files;
- authenticated Google Drive for native originals, comments, revisions, Earthfall, Bastion/Redoubt, Exploration Impossible, At War's End, and additional material;
- Git history/playtest files for Kit development.

A Grok or other agent without Brendon's authenticated Drive/ChatGPT Library access cannot follow those private locators.

## Required storage boundary

The durable solution is a **private, agent-accessible corpus repository or object store** containing portable normalized snapshots and this same catalog. It should be separate from public `radarsaint/dnd-solo`.

This connector cannot create a new GitHub repository, and the existing repository is public. Therefore the bootstrap stops short of copying private raw documents into GitHub.

Once a private shared repository/storage target exists, populate `portable_snapshot` for approved sources and make that the common read path for GPT/Grok collaborators.

## Never mirror automatically

Do not mirror:
- personal-response spreadsheets;
- documents whose authorship/privacy status has not been reviewed;
- third-party copyrighted rulebooks/sourcebooks merely because they are in Drive;
- private information unrelated to DM judgment.

The objective is Brendon's creative/DM evidence, not a dump of everything accessible to his account.

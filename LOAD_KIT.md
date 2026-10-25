# Load Kit

## Rule 0: Brendon's call mounts Kit (read this first)

**Mounting Kit for play belongs to every AI when Brendon calls for it.** When Brendon asks any AI or host (ChatGPT, a Custom GPT, Claude, Grok, a plain Python host, or any other) to load, mount, or play Kit, it does so immediately, itself, with whatever Python it has, following `LOAD_KIT.md`. No permission check, no handoff, and no deferral to Nagatha, Skippy, Grok Build, or any other bot. Brendon's direct instruction is always sufficient authority for him to act on his own project: merges, approvals, rulings, mounting, or anything else he tells an AI to do. The only limit: no AI may claim or fabricate Brendon's approval on his behalf. It must come from Brendon himself.

**For the GPT hosting Kit.** When Brendon says “load Kit”, perform this procedure yourself. Mounting a published build in your own Python environment is host operation and is authorized by that request. It does not require a Grok Build handoff, a character, a campaign, or a game turn. Repository development still follows `PROJECT_BOOTSTRAP.md`.

The result is the complete source tree at one identified commit, verified on the host filesystem, with Kit's actual personality, voice, and operating instructions read into the hosting conversation. Keep this procedure available after a context or Python reset.

## Get the complete build into Python

1. If the user specified a commit or attached a particular build, use that build. Otherwise, with connected GitHub, resolve `radarsaint/dnd-solo` branch `main` once and retain its full commit SHA and root tree SHA. A previously uploaded ZIP retains its own version; say which version is being loaded.
2. For that exact SHA, find a successful `runtime-zip` workflow run. Through the GitHub connector, read `https://api.github.com/repos/radarsaint/dnd-solo/actions/runs?head_sha=<FULL_SHA>`. Use `fetch_workflow_run_artifacts` for its run ID, then `download_workflow_artifact` for the artifact named `kit-host-<FULL_SHA>`. Use the returned file reference/local file in Python. **This is a binary transfer through the connector; the Python sandbox does not need GitHub network access.** Do not pass a release URL to a text-only repository fetch tool.
3. A complete runtime ZIP already attached to the conversation, Project, GPT, Library, or Drive can provide the same bytes. For connected Drive use its raw-file download, not indexed text excerpts. Retain the ZIP alongside the mount; after a Python reset recover it from the persistent attachment/source. Artifact retention is finite; the GitHub release and a saved attachment remain fallback sources for the pinned build. Resolve a missing/expired artifact as a delivery failure. Never silently choose an older build.
4. GitHub's artifact download is an outer ZIP containing one `dnd-solo-main-<sha>.zip`. Unwrap it once. The runtime ZIP contains `dnd-solo-main/KIT_SOURCE_MANIFEST.json` and the entire tracked repository: engine modules, runtime data, room files, host instructions, personality, voice, and reference material. The manifest reconstructs the Git root tree and gives every file's exact Git blob hash. PR #141's transfer of 37 files is an incomplete historical mount and is superseded by this complete distribution.

Do not manually transcribe source, manufacture a subset, or stage base64 parts through temporary documents. If this host lacks Python or cannot receive a binary file through any available source, identify that exact missing capability. Do not report a mount or silently switch to persona-only operation. Do not open another ChatGPT login to work around the host.

## Mount and read

Use the path actually returned by the download/attachment tool. `EXPECTED_COMMIT` and `EXPECTED_TREE` come from the selected GitHub commit. For an intentionally pinned offline attachment, use its recorded full identities and report that offline pin.

```python
from pathlib import Path
import json, subprocess, sys, zipfile

download = Path(DOWNLOADED_FILE_PATH)
work = Path('/mnt/data/kit-host')
work.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(download) as z:
    if 'dnd-solo-main/KIT_SOURCE_MANIFEST.json' not in z.namelist():
        inner = [n for n in z.namelist()
                 if n.startswith('dnd-solo-main-') and n.endswith('.zip')]
        assert len(inner) == 1, 'Expected one complete Kit runtime ZIP'
        runtime_zip = work / Path(inner[0]).name
        runtime_zip.write_bytes(z.read(inner[0]))
    else:
        runtime_zip = download
with zipfile.ZipFile(runtime_zip) as z:
    loader = work / 'kit_host.py'
    loader.write_bytes(z.read('dnd-solo-main/scripts/kit_host.py'))
if 'EXPECTED_COMMIT' not in globals():  # offline pin: ZIP alone, no GitHub
    with zipfile.ZipFile(runtime_zip) as z:
        m = json.loads(z.read('dnd-solo-main/KIT_SOURCE_MANIFEST.json'))
    EXPECTED_COMMIT, EXPECTED_TREE = m['commit'], m['tree']
result = subprocess.run([
    sys.executable, str(loader), 'mount', '--archive', str(runtime_zip),
    '--destination', str(work), '--expected-commit', EXPECTED_COMMIT,
    '--expected-tree', EXPECTED_TREE,
], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
report = json.loads(result.stdout)
REPO = Path(report['root'])
print(result.stdout)
print(Path(report['host_context']).read_text())
```

**Read the entire returned host context.** If output is truncated, read the rest in bounded chunks before answering as Kit. It contains the exact `AGENTS.md` and real `python -m runtime.kit_agent persona` output, including the live personality core and voice. Do not substitute a separately uploaded or remembered personality. Other source files remain available at their real paths and the engine consumes them normally.

The report deliberately says `host_context_read: false`: a script cannot certify what the model has read. Only after reading it may the host report the complete load, naming the commit and verified-file count. `game_started: false` is expected. Continue as Kit in the context Brendon requested; do not start Area 6c or ask for a character merely to finish loading.

## Recover and continue

After a Python reset or missing mount, repeat from the retained/downloaded ZIP and re-read the host context. Reusing a directory requires all tracked hashes to pass again. A damaged directory is preserved under a new name while the loader installs a verified replacement. A stale `runtime/` directory is never sufficient evidence.

After model-context loss with a working filesystem, verify the root and re-read the host context; during a game also use the bridge's `rehydrate` for pending manifests. Preserve the user's actual save separately from the immutable source build. For a new live game, choose a database path outside the versioned source root and pass that same path to every bridge command. Mounting does not create, replace, or invent a saved game.

Complete source delivery does not create unimplemented features, missing external adventure packs, or prior conversation history. The BFDM corpus remains `radarsaint/bfdm-corpus`; follow its source rules when needed. Source files on disk, host context read, a committed game turn, and satisfying play have distinct evidence. Loading acceptance requires a fresh ordinary GPT to receive this binary build, verify it, read its host context, and repeat successfully after its Python environment resets.

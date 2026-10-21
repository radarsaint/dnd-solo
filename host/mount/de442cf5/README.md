# Mount Kit at de442cf5

This set places the Kit runtime from commit `de442cf51d115df650fbdb1be7f612a96c7f4bc1` onto a Python desktop that cannot download GitHub.

Mounted means all 37 files below are present, each git blob sha matches this commit, and `python3 -m runtime.kit_agent persona` exits 0.

It does not start a game.

## Files

- `runtime/` from that commit, without `__pycache__`
- `docs/personality/dm-personality-core.md`
- `docs/personality/kit-taste.json`
- `docs/voice/*.md` except `README.md`

## Steps

Work from the directory that contains `apply.py` and `MANIFEST.json`. Copy each GitHub file onto the desktop unchanged, including its final newline. Do not reformat JSON.

1. Copy `apply.py` and `MANIFEST.json`.
2. For each name in `MANIFEST.json` `parts`, in order, copy `parts/<name>` and run:

```
python3 apply.py --root <mount root> --part parts/<name>
```

If a part does not match, write that one file again and rerun it. Do not continue past a mismatch.

3. Run:

```
python3 apply.py --root <mount root> --verify
python3 -m runtime.kit_agent persona
```

The verify command prints `mounted 37 files at de442cf5`. The persona command exits 0. Until both of those happen, Kit is not mounted.

Parts: 119. Files: 37.

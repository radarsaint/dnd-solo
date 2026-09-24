#!/usr/bin/env python3
"""Hydrate the local D&D Solo checkout from the private visual asset pack.

This script never downloads or publishes the asset pack. It accepts either:
- the private zip created by the project integration pass, or
- an already extracted asset-pack directory.

The pack contains SHA256SUMS.txt and repo-relative asset paths.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_pack_root(path: Path, temp_root: Path | None = None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if path.is_dir():
        root = path
        if (root / "SHA256SUMS.txt").exists():
            return root, None
        nested = root / "dnd-solo-private-asset-pack"
        if (nested / "SHA256SUMS.txt").exists():
            return nested, None
        raise SystemExit(f"No SHA256SUMS.txt found under {path}")

    if not path.is_file() or path.suffix.lower() != ".zip":
        raise SystemExit("asset_pack must be a directory or .zip file")

    tmp = tempfile.TemporaryDirectory(prefix="dnd-solo-assets-")
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp.name)
    extracted = Path(tmp.name)
    direct = extracted / "SHA256SUMS.txt"
    nested = extracted / "dnd-solo-private-asset-pack" / "SHA256SUMS.txt"
    if direct.exists():
        return extracted, tmp
    if nested.exists():
        return nested.parent, tmp
    tmp.cleanup()
    raise SystemExit("Zip does not contain SHA256SUMS.txt")


def load_checksums(pack_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in (pack_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        digest, rel = raw.split(None, 1)
        rel = rel.strip()
        result[rel] = digest
    return result


def verify_pack(pack_root: Path, checksums: dict[str, str]) -> None:
    failures: list[str] = []
    for rel, expected in checksums.items():
        src = pack_root / rel
        if not src.is_file():
            failures.append(f"MISSING {rel}")
            continue
        actual = sha256(src)
        if actual != expected:
            failures.append(f"HASH {rel}: expected {expected}, got {actual}")
    if failures:
        raise SystemExit("Asset-pack verification failed:\n" + "\n".join(failures))


def hydrate(pack_root: Path, repo_root: Path, checksums: dict[str, str], overwrite: bool) -> int:
    copied = 0
    for rel in sorted(checksums):
        src = pack_root / rel
        dst = repo_root / rel
        if dst.exists() and not overwrite:
            if sha256(dst) == checksums[rel]:
                continue
            raise SystemExit(f"Refusing to replace differing file without --overwrite: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_pack", type=Path, help="Private asset-pack zip or extracted pack directory")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root (default: current directory)")
    parser.add_argument("--verify-only", action="store_true", help="Verify pack without copying files")
    parser.add_argument("--overwrite", action="store_true", help="Replace differing local asset files")
    args = parser.parse_args()

    pack_root, tmp = find_pack_root(args.asset_pack.resolve())
    try:
        checksums = load_checksums(pack_root)
        if len(checksums) != 87:
            raise SystemExit(f"Expected 87 indexed binaries, found {len(checksums)} checksum entries")
        verify_pack(pack_root, checksums)
        print(f"Verified {len(checksums)} private visual assets.")
        if args.verify_only:
            return 0

        repo_root = args.repo.resolve()
        if not (repo_root / "assets" / "maps" / "index.json").exists():
            raise SystemExit(f"{repo_root} does not look like the dnd-solo repository root")

        copied = hydrate(pack_root, repo_root, checksums, args.overwrite)
        print(f"Hydrated {copied} asset files into {repo_root}.")
        print("These binaries are intentionally gitignored in the public repository.")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())

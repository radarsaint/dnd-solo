#!/usr/bin/env python3
"""Hydrate BFDM style-reference images from a private pack.

The public repository stores only assets/style/index.json. The image bytes are private
reference material and remain gitignored under assets/style/references/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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


def find_pack_root(path: Path):
    if path.is_dir():
        for root in (path, path / "dnd-solo-private-style-pack"):
            if (root / "SHA256SUMS.txt").is_file():
                return root, None
        raise SystemExit(f"No SHA256SUMS.txt found under {path}")
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise SystemExit("style_pack must be a directory or .zip file")
    tmp = tempfile.TemporaryDirectory(prefix="dnd-solo-style-")
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp.name)
    extracted = Path(tmp.name)
    for root in (extracted, extracted / "dnd-solo-private-style-pack"):
        if (root / "SHA256SUMS.txt").is_file():
            return root, tmp
    tmp.cleanup()
    raise SystemExit("Zip does not contain SHA256SUMS.txt")


def load_checksums(path: Path) -> dict[str, str]:
    out = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        digest, rel = raw.split(None, 1)
        out[rel.strip()] = digest
    return out


def manifest_expected(repo: Path) -> dict[str, str]:
    path = repo / "assets/style/index.json"
    if not path.is_file():
        raise SystemExit(f"{repo} does not contain assets/style/index.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {}
    for ref in manifest.get("references") or []:
        rel, digest = ref.get("private_path"), ref.get("sha256")
        if not (isinstance(rel, str) and isinstance(digest, str)):
            raise SystemExit(f"Style reference {ref.get('id')} is missing private_path/sha256")
        expected[rel] = digest
    if not expected:
        raise SystemExit("Style manifest has no references")
    return expected


def verify(pack_root: Path, listed: dict[str, str], expected: dict[str, str]) -> None:
    failures = []
    for rel, digest in expected.items():
        if listed.get(rel) != digest:
            failures.append(f"MANIFEST {rel}: pack checksum does not match assets/style/index.json")
            continue
        src = pack_root / rel
        if not src.is_file():
            failures.append(f"MISSING {rel}")
            continue
        actual = sha256(src)
        if actual != digest:
            failures.append(f"HASH {rel}: expected {digest}, got {actual}")
    extras = sorted(set(listed) - set(expected))
    if extras:
        failures.append("UNEXPECTED " + ", ".join(extras))
    if failures:
        raise SystemExit("Style-pack verification failed:\n" + "\n".join(failures))


def hydrate(pack_root: Path, repo: Path, expected: dict[str, str], overwrite: bool) -> int:
    copied = 0
    for rel, digest in sorted(expected.items()):
        src, dst = pack_root / rel, repo / rel
        if dst.exists() and not overwrite:
            if sha256(dst) == digest:
                continue
            raise SystemExit(f"Refusing to replace differing file without --overwrite: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("style_pack", type=Path, help="Private BFDM style-pack zip or directory")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="dnd-solo repository root")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    expected = manifest_expected(repo)
    root, tmp = find_pack_root(args.style_pack.resolve())
    try:
        listed = load_checksums(root / "SHA256SUMS.txt")
        verify(root, listed, expected)
        print(f"Verified {len(expected)} BFDM style references.")
        if args.verify_only:
            return 0
        copied = hydrate(root, repo, expected, args.overwrite)
        print(f"Hydrated {copied} BFDM style references into {repo}.")
        print("These reference images are intentionally gitignored.")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())

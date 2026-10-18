"""Hydrate DM Kit's private BFDM style-reference images from the v1 pack.

Usage:
    python3 scripts/import_style_reference_pack.py /path/to/bfdm-style-reference-pack-v1.zip

The public repository contains metadata only. This script verifies every selected
reference against style/BFDM_REFERENCE_INDEX.json before copying it to
style/private_refs/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "style" / "BFDM_REFERENCE_INDEX.json"
TARGET = ROOT / "style" / "private_refs"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        raise SystemExit("usage: import_style_reference_pack.py <bfdm-style-reference-pack-v1.zip>")

    pack = Path(argv[0]).expanduser().resolve()
    if not pack.is_file():
        raise SystemExit(f"pack not found: {pack}")

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    expected_pack = index.get("private_pack") or {}
    actual_pack_sha = sha256(pack)
    if expected_pack.get("sha256") and actual_pack_sha != expected_pack["sha256"]:
        raise SystemExit(
            f"pack SHA-256 mismatch: expected {expected_pack['sha256']}, got {actual_pack_sha}")

    refs = {ref["id"]: ref for ref in index.get("references") or []}
    if not refs:
        raise SystemExit("reference index is empty")

    with tempfile.TemporaryDirectory(prefix="kit-style-pack-") as td:
        temp = Path(td)
        with zipfile.ZipFile(pack) as z:
            z.extractall(temp)

        manifest_path = temp / "manifest.json"
        if not manifest_path.is_file():
            raise SystemExit("style pack is missing manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "bfdm_style_reference_pack_v1":
            raise SystemExit("unsupported style-reference pack schema")

        files = {item["id"]: item for item in manifest.get("files") or []}
        missing = sorted(set(refs) - set(files))
        if missing:
            raise SystemExit("style pack is missing: " + ", ".join(missing))

        TARGET.mkdir(parents=True, exist_ok=True)
        copied = []
        for ref_id, ref in refs.items():
            item = files[ref_id]
            if item.get("file") != ref.get("pack_file"):
                raise SystemExit(
                    f"{ref_id}: manifest file {item.get('file')!r} does not match "
                    f"index {ref.get('pack_file')!r}")
            source = temp / item["file"]
            if not source.is_file():
                raise SystemExit(f"{ref_id}: missing file {item['file']}")
            digest = sha256(source)
            expected = ref.get("sha256")
            if expected and digest != expected:
                raise SystemExit(
                    f"{ref_id}: SHA-256 mismatch: expected {expected}, got {digest}")
            target = TARGET / item["file"]
            shutil.copy2(source, target)
            copied.append(target.relative_to(ROOT).as_posix())

    print(json.dumps({
        "status": "ok",
        "pack": pack.name,
        "pack_sha256": actual_pack_sha,
        "references": len(copied),
        "target": TARGET.relative_to(ROOT).as_posix(),
        "files": copied,
    }, indent=2))


if __name__ == "__main__":
    main()

# Apply one mount part, or verify the mount. Standard library only.
# python3 apply.py --root DIR --part PATH
# python3 apply.py --root DIR --verify
import argparse, base64, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def blob_sha(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode())
    h.update(data)
    return h.hexdigest()

def load_manifest():
    return json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))

def fail(msg):
    print(msg, file=sys.stderr)
    return 2

def apply_part(root: Path, part_path: Path) -> int:
    manifest = load_manifest()
    raw = part_path.read_bytes()
    name = part_path.name
    meta = next((p for p in manifest["parts"] if p["name"] == name), None)
    if meta is None:
        return fail(f"{name} is not in MANIFEST.json")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != meta["sha256"] or len(raw) != meta["bytes"]:
        return fail(f"{name} does not match MANIFEST.json. Write the file again, unchanged.")
    doc = json.loads(raw.decode("utf-8"))
    if doc["commit"] != manifest["commit"]:
        return fail("part commit does not match MANIFEST.json")
    for item in doc["files"]:
        rel = Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts:
            return fail(f"refusing path {item['path']}")
        piece = base64.b64decode(item["b64"])
        dest = root / rel
        if item["parts"] == 1:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(piece)
            if blob_sha(piece) != item["blob"] or len(piece) != item["size"]:
                return fail(f"blob mismatch {item['path']}")
            continue
        slot = root / ".kit-mount-partial" / rel / f"{item['part']:05d}"
        slot.parent.mkdir(parents=True, exist_ok=True)
        slot.write_bytes(piece)
        got = [slot.parent.joinpath(f"{i:05d}") for i in range(item["parts"])]
        if not all(p.is_file() for p in got):
            print(f"stored {item['path']} part {item['part'] + 1}/{item['parts']}")
            continue
        data = b"".join(p.read_bytes() for p in got)
        if blob_sha(data) != item["blob"] or len(data) != item["size"]:
            return fail(f"blob mismatch {item['path']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        for p in got:
            p.unlink()
        print(f"wrote {item['path']}")
    print(f"applied {name}")
    return 0

def verify(root: Path) -> int:
    manifest = load_manifest()
    bad = []
    for item in manifest["files"]:
        dest = root / item["path"]
        if not dest.is_file():
            bad.append(f"missing {item['path']}")
            continue
        data = dest.read_bytes()
        if len(data) != item["size"] or blob_sha(data) != item["blob"]:
            bad.append(f"mismatch {item['path']}")
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return fail(f"not mounted ({len(bad)} files)")
    print(f"mounted {len(manifest['files'])} files at {manifest['short']}")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--part")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.verify:
        return verify(root)
    return apply_part(root, Path(args.part).resolve())

if __name__ == "__main__":
    sys.exit(main())

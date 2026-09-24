#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel, key in [("assets/maps/index.json", "maps"), ("assets/art/index.json", "assets")]:
    path = ROOT / rel
    data = json.loads(path.read_text())
    assert data.get("schema_version") == 1, f"{rel}: unsupported schema_version"
    assert isinstance(data.get(key), list), f"{rel}: {key} must be a list"
print("manifests ok")

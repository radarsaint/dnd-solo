"""Fixture sheets as the older suites knew them.

The equipment audit (runtime.kit_gear) flags gear a sheet's build is not trained for, and the
engine then enforces the SRD penalties until the player answers. Suites written before the audit
pin dice and Shield windows for sheets as they were, so they load them through here: the same
sheet without the gear its audit flags. Nothing is picked by name, and the fixture files are
never changed; tests/test_kit_slot_ask_gear.py covers the audited sheets as they are.
"""

import json
import tempfile
from pathlib import Path

from runtime import kit_gear


def sheet(path):
    return kit_gear.before_audit(json.loads(Path(path).read_text()))


def path(path):
    path = Path(path)
    out = Path(tempfile.gettempdir()) / 'dnd-solo-sheets-before-audit' / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sheet(path), indent=2))
    return out

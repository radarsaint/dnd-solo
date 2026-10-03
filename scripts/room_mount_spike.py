"""Spike (parked, no PR): mount any room file and run lines through the adjudicator.

    env -u PYTHONPATH PYTHONPATH=. python3 scripts/room_mount_spike.py ROOM.json "line" ...

Settles one question for docs/architecture/ROOM_LOADER.md: is removing the area_06c gate
enough to run a non-6c room? (No: the tub and south_door rulings are hardcoded.)"""
import json, sys, tempfile
from pathlib import Path
from runtime.kit_agent import Room6CAdjudicator, PendingRuling
from runtime.state_context import Runtime, InvalidChange
src = json.loads(Path(sys.argv[1]).read_text())
d = tempfile.mkdtemp(); r = Runtime(Path(d)/'k.sqlite'); r.initialize(src, src['starting_area'])
r.set_player_sheet(json.loads(Path('tests/fixtures/characters/nik.json').read_text()))
for line in sys.argv[2:]:
    rev, st = r.load(); a = Room6CAdjudicator(roll=lambda: 10); a.source = r.source()
    try:
        res = a.resolve(line, rev, st); r.commit(f't{rev}', rev, list(res.events)); print('OK', res.kind, '|', res.public_event[:120], '<=', line)
    except PendingRuling as e: print('PENDING', str(e)[:120], '<=', line)
    except (InvalidChange, KeyError) as e: print('ERROR', type(e).__name__, str(e)[:120], '<=', line)

"""Kit's host lifecycle: where a save is, and the one command that moves it on.

The state is read from the save (SQLite) on every call, never cached in Python, so a
pending opening or turn survives a Python reset: reload the save and ``status`` says
exactly what to run next.

States
  unmounted       no save, or a save with no room mounted
  mounted         a room is mounted but no opening has been prepared
  ready           the opening is prepared and waiting to be completed
  playing         at least one turn committed and nothing waiting
  awaiting_completion  a player turn is prepared and waiting to be completed

While a turn is waiting, ``prepare`` refuses new input (``turn_pending``): it never stages a
second turn and never files the words as a held or refused attempt. A bare out-of-character
confirmation ("Yes.", "Let's go", "Begin") means: complete the waiting turn now.
"""
import json
import re
import shlex
import sqlite3
from pathlib import Path

# A whole message made only of go-ahead words. Anything with an in-world deed ("Yes, I open
# the door") is not a confirmation and gets the plain turn_pending answer.
_GO_WORDS = (r"(?:yes|yeah|yep|yup|ya|sure|ok|okay|k|alright|all right|absolutely|definitely|please|"
             r"go|go ahead|go on|begin|start|play|ready|i'm ready|im ready|i am ready|we're ready|"
             r"let's go|lets go|let's begin|lets begin|let's start|lets start|let's play|lets play|"
             r"let's do it|lets do it|let's do this|lets do this|let's roll|lets roll|do it|dewit|"
             r"start the adventure|begin the adventure|start the game|begin the game|let's get started|"
             r"lets get started|hit it|roll|kit|sounds good|i'm in|im in)")
CONFIRMATION = re.compile(rf"^\s*{_GO_WORDS}(?:[\s,.!;:-]+{_GO_WORDS})*[\s.!]*$", re.I)


def is_confirmation(text):
    """True for a bare out-of-character go-ahead ('Yes.', "Let's go!", 'Ok, begin')."""
    words = str(text or '').replace('\u2019', "'").strip()
    return bool(words) and len(words) <= 60 and bool(CONFIRMATION.match(words))


def complete_command(db, turn_id, input_file='o.json'):
    return (f'python3 -m runtime.kit_agent complete --db {shlex.quote(str(db))} '
            f'--turn-id {turn_id} --input-file {input_file}')


def _waiting(con):
    """(turn_id, is_opening) for the pending turn at the current revision, or None.
    Pending rows from an older revision are stale (a later turn committed) and ignored."""
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kit_pending'").fetchone() is None:
        return None
    snap = con.execute('SELECT MAX(revision) FROM snapshots').fetchone()
    current = snap[0] if snap else None
    for turn_id, revision, body in con.execute('SELECT turn_id, revision, body FROM kit_pending ORDER BY rowid'):
        if revision != current:
            continue
        try:
            kind = json.loads(body).get('kind')
        except (ValueError, AttributeError):
            kind = None
        return turn_id, kind == 'opening'
    return None


def state_of(con):
    """The lifecycle state of an open save connection, with the waiting turn if any."""
    has_source = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source'").fetchone() is not None
    if not has_source or con.execute('SELECT 1 FROM source WHERE id=1').fetchone() is None:
        return {'state': 'unmounted'}
    waiting = _waiting(con)
    committed = con.execute('SELECT COUNT(*) FROM kit_turns').fetchone()[0] if con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kit_turns'").fetchone() else 0
    if waiting:
        turn_id, opening = waiting
        return {'state': 'ready' if opening else 'awaiting_completion', 'pending_turn_id': turn_id,
                'pending_kind': 'opening' if opening else 'turn', 'committed_turns': committed}
    return {'state': 'playing' if committed else 'mounted', 'committed_turns': committed}


def status(db):
    """Read-only lifecycle status for ``db``: the state and the exact next command."""
    path = Path(db)
    if not path.is_file() or path.stat().st_size == 0:
        found = {'state': 'unmounted'}
    else:
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            found = state_of(con)
        except sqlite3.Error:
            found = {'state': 'unmounted'}
        finally:
            con.close()
    q = shlex.quote(str(db))
    state = found['state']
    if state == 'unmounted':
        nxt = f'python3 -m runtime.kit_agent start --db {q}'
    elif state == 'mounted':
        nxt = f'python3 -m runtime.kit_agent prepare --one-pass --opening --db {q}'
    elif state in ('ready', 'awaiting_completion'):
        nxt = complete_command(db, found['pending_turn_id'])
        found['packet_command'] = packet_command(db, found['pending_turn_id'], state == 'ready')
    else:
        nxt = f'python3 -m runtime.kit_agent prepare --one-pass --db {q} --action-file a.txt'
    out = {'stage': 'status', **found, 'next_command': nxt}
    from . import kit_adventure
    ready = kit_adventure.readiness(db, mounted_room_id(db))
    if ready['adventure_readiness'] != 'none':
        out['adventure'] = ready
        if state == 'unmounted' and ready.get('start_room'):
            out['next_command'] = (f'python3 -m runtime.kit_agent start --db {q} --room '
                                   f"{shlex.quote(ready['start_room'])} --sheet <sheet.json>")
        elif state == 'unmounted' and ready.get('adventure_next'):
            out['next_command'] = ready['adventure_next']
    return out


def mounted_room_id(db):
    """The id of the room mounted in a save, or None (read-only)."""
    path = Path(db)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        row = con.execute('SELECT body FROM source WHERE id=1').fetchone()
        return json.loads(row[0]).get('id') if row else None
    except (sqlite3.Error, ValueError, AttributeError):
        return None
    finally:
        con.close()


def packet_command(db, turn_id, opening):
    """Rebuild the waiting turn's packet after a reset: the opening re-prepares under its own id
    (same body, no new turn); a player turn gets its manifests back from rehydrate."""
    q = shlex.quote(str(db))
    if opening:
        return f'python3 -m runtime.kit_agent prepare --one-pass --opening --db {q} --turn-id {turn_id}'
    return f'python3 -m runtime.kit_agent rehydrate --db {q} --turn-id {turn_id}'


def turn_pending(db, turn_id, opening, action):
    """prepare's answer while a turn is waiting: nothing staged, nothing held or recorded."""
    confirm = is_confirmation(action)
    if opening and confirm:
        say = ('The player said go. Complete the pending opening now: write o.json for that turn '
               '(packet_command rebuilds its packet if you lost it), run next_command, show only "spoken".')
    elif confirm:
        say = 'The player said go. Complete the pending turn now with next_command; show only "spoken".'
    else:
        say = ('A turn is still waiting. Complete it first with next_command, then prepare these words '
               'as a new turn. These words were not recorded.')
    return {'stage': 'turn_pending', 'committed': False, 'input_recorded': False,
            'pending_turn_id': turn_id, 'pending_kind': 'opening' if opening else 'turn',
            'confirmation': confirm, 'instruction': say,
            'next_command': complete_command(db, turn_id),
            'packet_command': packet_command(db, turn_id, opening)}

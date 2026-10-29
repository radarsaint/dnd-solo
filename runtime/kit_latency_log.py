"""Wall-clock turn log a host fills in. One JSON object per line, next to the save.

The engine cannot see the time from the player's message to the reply on screen. The host
appends a line (or calls ``record``) after Kit's line is shown:

    {"v": 1, "turn_id": "t", "message_at": 1000.0, "reply_at": 1017.5, "rejections": 2}

``message_at`` and ``reply_at`` are epoch seconds (``time.time()``). ``rejections`` is how
many complete attempts were rejected before the reply that was shown (0 when the first
committed). ``wall_s`` is ``reply_at - message_at``; a hand-written line may omit it and
``read`` fills it in. Nothing here is estimated. DCs and bonuses are not part of the line.

    python3 -m runtime.kit_agent latency --db kit.sqlite
    python3 -m runtime.kit_agent latency --db kit.sqlite --turn-id T \\
        --message-at 1000.0 --reply-at 1017.5 --rejections 2

The file is ``<db>.latency.jsonl`` and is git-ignored.
"""
import json
import statistics
from pathlib import Path


def path_for(db):
    return Path(str(db) + '.latency.jsonl')


def _epoch(value, name):
    if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
        raise ValueError(name + ' is epoch seconds')
    return float(value)


def record(db, turn_id, message_at, reply_at, rejections, packet_bytes=None, note=None):
    """Append one turn. Raises ValueError when the line is not a real measurement."""
    if not isinstance(turn_id, str) or not turn_id.strip():
        raise ValueError('turn_id is required')
    if type(rejections) is not int or rejections < 0:
        raise ValueError('rejections is the number of rejected attempts, 0 or more')
    message_at = _epoch(message_at, 'message_at')
    reply_at = _epoch(reply_at, 'reply_at')
    if reply_at < message_at:
        raise ValueError('reply_at is before message_at')
    row = {'v': 1, 'turn_id': turn_id, 'message_at': message_at, 'reply_at': reply_at,
           'rejections': rejections, 'wall_s': round(reply_at - message_at, 3)}
    if packet_bytes is not None:
        if type(packet_bytes) is not int or packet_bytes < 0:
            raise ValueError('packet_bytes is a byte count')
        row['packet_bytes'] = packet_bytes
    if note:
        row['note'] = str(note)[:200]
    path = path_for(db)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    return row


def _row(data):
    if not isinstance(data, dict) or data.get('v') != 1:
        return None
    if data.get('wall_s') is None and data.get('message_at') is not None and data.get('reply_at') is not None:
        try:
            data = dict(data, wall_s=round(float(data['reply_at']) - float(data['message_at']), 3))
        except (TypeError, ValueError):
            return data
    return data


def read(db):
    path = path_for(db)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            row = _row(json.loads(line))
        except ValueError:
            continue
        if row is not None:
            rows.append(row)
    return rows


def report(db):
    """The log plus the rejection total and the median wall-clock seconds."""
    rows = read(db)
    walls = [row['wall_s'] for row in rows if type(row.get('wall_s')) in (int, float)
             and not isinstance(row.get('wall_s'), bool)]
    return {'file': str(path_for(db)), 'n': len(rows),
            'rejections': sum(row.get('rejections') or 0 for row in rows),
            'wall_s_median': round(statistics.median(walls), 3) if walls else None,
            'turns': rows}

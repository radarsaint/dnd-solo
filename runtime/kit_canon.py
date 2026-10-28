"""Canon status for the campaign record.

Facts live on the campaign record the save already keeps: ``campaign.json``
``facts`` and the runtime ``campaign_log['facts']`` (one list; the journal and
the save listing render it). This is not a second database. It is not the room
detail canon (``state['canon']`` in ``kit_detail``), which stays with a room.

Status
------
CONFIRMED
    A source document, or the DM explicitly adopted it (``adopt`` / ``promote``).
PROPOSED
    Kit generated it. Saying it does not make it canon.
RESOLVED_IN_PLAY
    The outcome of actual player decisions, including a DM report of what was played.
UNKNOWN
    The fact is unset. Callers must not invent a history for it. A value other than
    empty is refused.

Missing status on an older save
-------------------------------
- Play folds (``loot``, ``npcs_met``, ``learned``, ``choices``, ``rooms``) read as
  RESOLVED_IN_PLAY. They are what already happened in front of the player.
- Player-kept ``debts`` and ``threads`` read as CONFIRMED. The player wrote them.
- A ``facts`` entry with no status reads as PROPOSED. It is not promoted.
- Actor ``status`` (alive, dead, and the rest) is not a canon status.
- UNKNOWN is never inferred from a missing field.

The DM's latest ruling supersedes older drafts: the previous value stays on
``history`` and is not current. An earned loot box and its later contents are
different facts. A paid contract obligation, and a treasure or artifact someone
already holds, cannot be recorded again under a second current holder.
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

STATUSES = ('CONFIRMED', 'PROPOSED', 'RESOLVED_IN_PLAY', 'UNKNOWN')
KINDS = ('npc', 'artifact', 'treasure', 'position', 'contract', 'clock', 'audience', 'award', 'loot_box')
PLAY_FIELDS = ('loot', 'npcs_met', 'learned', 'choices', 'rooms')
PLAYER_FIELDS = ('debts', 'threads')
FACT_LIMIT = 200
HISTORY_LIMIT = 20
VALUE_LIMIT = 2000
KEY = re.compile(r'^[a-z0-9][a-z0-9._-]{0,60}$')
GP_KEYS = ('gp', 'gp_per_day', 'gold', 'amount')
NUMBER = re.compile(r'\b\d{1,3}(?:,\d{3})+|\b\d+\b')
AWARD_MENTION = re.compile(
    r'\b(?:award(?:ed)?|medal|title)\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})')
LABEL = ' (proposed ruling)'


class CanonError(ValueError):
    """A campaign fact that would break canon status."""


def canon_status(entry, field='facts'):
    """The status an entry carries. A missing one uses the documented default for its field."""
    if isinstance(entry, dict):
        explicit = entry.get('canon')
        if explicit in STATUSES:
            return explicit
        if field == 'facts' and entry.get('status') in STATUSES:
            return entry['status']
    if field in PLAYER_FIELDS:
        return 'CONFIRMED'
    if field == 'facts':
        return 'PROPOSED'
    return 'RESOLVED_IN_PLAY'


def _json_size(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except TypeError as exc:
        raise CanonError('A fact value has to be JSON.') from exc


def check_stored(facts):
    """A facts list already on a save or a commit. Missing status is allowed."""
    if not isinstance(facts, list) or len(facts) > FACT_LIMIT:
        raise CanonError('facts must be a list of at most {} entries.'.format(FACT_LIMIT))
    seen = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise CanonError('Each fact is an object.')
        key = fact.get('key')
        if not isinstance(key, str) or not KEY.match(key):
            raise CanonError('A fact key is a short slug (letters, digits, dot, dash).')
        if fact.get('kind') not in KINDS:
            raise CanonError('Unknown fact kind {}.'.format(fact.get('kind')))
        if 'status' in fact and fact.get('status') not in STATUSES:
            raise CanonError('Unknown canon status.')
        if 'canon' in fact and fact.get('canon') not in STATUSES:
            raise CanonError('Unknown canon status.')
        history = fact.get('history') or []
        if not isinstance(history, list) or len(history) > HISTORY_LIMIT:
            raise CanonError('Fact history is too long.')
        if _json_size(fact.get('value')) > VALUE_LIMIT:
            raise CanonError('Fact value is too long.')
        seen.append(key)
    if len(seen) != len(set(seen)):
        raise CanonError('Two current facts share a key.')


def apply_facts(state, facts):
    """Put facts on campaign_log without dropping the rooms already folded there."""
    check_stored(facts)
    log = dict(state.get('campaign_log') or {})
    log['facts'] = copy.deepcopy(facts)
    state['campaign_log'] = log
    return state


def _facts(campaign):
    rows = campaign.get('facts')
    if rows is None:
        rows = []
        campaign['facts'] = rows
    if not isinstance(rows, list):
        raise CanonError('facts must be a list.')
    return rows


def _current(campaign):
    return [fact for fact in _facts(campaign)
            if isinstance(fact, dict) and fact.get('current', True) and fact.get('key')]


def _find(campaign, key):
    for fact in _current(campaign):
        if fact.get('key') == key:
            return fact
    return None


def _numbers(value, prefix=''):
    found = []
    if type(value) is int:
        found.append((prefix or 'value', value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_numbers(item, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_numbers(item, '{}{}'.format(prefix, index)))
    elif isinstance(value, str):
        for raw in re.findall(r'\d[\d,]*', value):
            found.append((prefix or 'value', int(raw.replace(',', ''))))
    return found


def _item_name(fact):
    value = fact.get('value')
    if isinstance(value, dict):
        for key in ('item', 'name'):
            name = value.get(key)
            if isinstance(name, str) and name.strip():
                return name.casefold().strip()
    return None


def _custody_id(fact):
    if fact.get('kind') not in ('treasure', 'artifact'):
        return None
    return _item_name(fact) or fact.get('key')


def _obligation(fact):
    value = fact.get('value')
    if not isinstance(value, dict) or not value.get('paid'):
        return None
    return str(value.get('obligation') or fact.get('key'))


def _assert_unique(campaign, key, kind, value):
    probe = {'key': key, 'kind': kind, 'value': value}
    obligation = _obligation(probe)
    custody = _custody_id(probe)
    for fact in _current(campaign):
        if fact.get('key') == key:
            continue
        if obligation and _obligation(fact) == obligation:
            raise CanonError(
                'Contract payment {} is already paid. It cannot be paid twice.'.format(obligation))
        if custody and _custody_id(fact) == custody:
            raise CanonError(
                '{} already has a holder. It cannot be assigned to two holders.'.format(custody))


def _contents_key(key):
    return key + '.contents'


def _is_contents_key(key):
    return str(key).endswith('.contents')


def record(campaign, kind, key, value=None, status=None, by='kit', source=None):
    """Record a current fact. Kit's own record stays PROPOSED unless it is UNKNOWN."""
    if not isinstance(campaign, dict):
        raise CanonError('The campaign record is an object.')
    if kind not in KINDS:
        raise CanonError('Unknown fact kind {}.'.format(kind))
    if not isinstance(key, str) or not KEY.match(key):
        raise CanonError('A fact key is a short slug (letters, digits, dot, dash).')
    if by not in ('kit', 'dm', 'play'):
        raise CanonError('by is kit, dm, or play.')
    if status is None:
        if by == 'play':
            status = 'RESOLVED_IN_PLAY'
        elif by == 'dm' and isinstance(source, str) and source.strip():
            status = 'CONFIRMED'
        else:
            status = 'PROPOSED'
    if status not in STATUSES:
        raise CanonError('Unknown canon status.')
    if by == 'kit' and status in ('CONFIRMED', 'RESOLVED_IN_PLAY'):
        raise CanonError(
            "Kit's own suggestion does not become canon because she said it. It stays PROPOSED "
            'until the DM adopts it or play resolves it.')
    if by == 'play' and status not in ('RESOLVED_IN_PLAY', 'UNKNOWN'):
        raise CanonError('A play record is RESOLVED_IN_PLAY, or UNKNOWN when it is unset.')
    if status == 'CONFIRMED' and not (isinstance(source, str) and source.strip()):
        raise CanonError('CONFIRMED needs a source document or adopt().')
    if status == 'UNKNOWN' and value is not None:
        raise CanonError('UNKNOWN must not be invented as history.')
    if status == 'UNKNOWN':
        value = None
    if kind == 'loot_box' and not _is_contents_key(key):
        if not isinstance(value, dict):
            raise CanonError('A loot box value is an object with a name and opened.')
        if 'contents' in value or 'items' in value:
            raise CanonError(
                'An earned loot box is not its contents. Determine contents on {}.'.format(
                    _contents_key(key)))
        value = dict(value)
        value.setdefault('opened', False)
    if _find(campaign, key):
        raise CanonError('{} is already recorded. Supersede it to change the current value.'.format(key))
    _assert_unique(campaign, key, kind, value)
    if _json_size(value) > VALUE_LIMIT:
        raise CanonError('Fact value is too long.')
    extra = 2 if kind == 'loot_box' and not _is_contents_key(key) and not _find(campaign, _contents_key(key)) else 1
    if len(_facts(campaign)) + extra > FACT_LIMIT:
        raise CanonError('The campaign record is full.')
    fact = {
        'kind': kind, 'key': key, 'value': copy.deepcopy(value), 'status': status, 'by': by,
        'source': source, 'current': True, 'history': [],
    }
    _facts(campaign).append(fact)
    if kind == 'loot_box' and not _is_contents_key(key) and _find(campaign, _contents_key(key)) is None:
        _facts(campaign).append({
            'kind': 'loot_box', 'key': _contents_key(key), 'parent': key, 'value': None,
            'status': 'UNKNOWN', 'by': by, 'source': None, 'current': True, 'history': [],
        })
    return copy.deepcopy(fact)


def adopt(campaign, key, by='dm', source=None):
    """Promote a PROPOSED fact to CONFIRMED. It stops being provisional."""
    if by == 'kit':
        raise CanonError(
            "Kit cannot adopt her own suggestion. It stays PROPOSED until the DM uses it.")
    if by not in ('dm', 'play'):
        raise CanonError('by is dm or play.')
    fact = _find(campaign, key)
    if fact is None:
        raise CanonError('No current fact {}.'.format(key))
    status = canon_status(fact, 'facts')
    if status == 'UNKNOWN':
        raise CanonError('UNKNOWN has nothing to adopt. Supersede it once the fact is known.')
    if status == 'PROPOSED':
        fact.setdefault('history', []).append({
            'value': copy.deepcopy(fact.get('value')), 'status': 'PROPOSED',
            'by': fact.get('by'), 'source': fact.get('source'),
        })
        fact['history'] = fact['history'][-HISTORY_LIMIT:]
        fact['status'] = 'CONFIRMED'
        fact['by'] = by
        fact['source'] = source or 'adopted by the DM'
        fact['current'] = True
    return copy.deepcopy(fact)


def promote(campaign, key, by='dm', source=None):
    """``adopt`` by the other name."""
    return adopt(campaign, key, by=by, source=source)


def supersede(campaign, key, value, by='dm', status=None, source=None):
    """The DM's latest ruling becomes current. The older value stays in history, not as current."""
    if by not in ('kit', 'dm', 'play'):
        raise CanonError('by is kit, dm, or play.')
    fact = _find(campaign, key)
    if fact is None:
        raise CanonError('No current fact {}.'.format(key))
    if status is None:
        status = 'PROPOSED' if by == 'kit' else ('RESOLVED_IN_PLAY' if by == 'play' else 'CONFIRMED')
    if status not in STATUSES:
        raise CanonError('Unknown canon status.')
    if by == 'kit' and status in ('CONFIRMED', 'RESOLVED_IN_PLAY'):
        raise CanonError(
            "Kit's own suggestion does not become canon because she said it. It stays PROPOSED "
            'until the DM adopts it or play resolves it.')
    if status == 'CONFIRMED' and not (isinstance(source, str) and source.strip()):
        source = 'DM ruling' if by == 'dm' else None
        if not source:
            raise CanonError('CONFIRMED needs a source document or adopt().')
    if status == 'UNKNOWN' and value is not None:
        raise CanonError('UNKNOWN must not be invented as history.')
    if status == 'UNKNOWN':
        value = None
    if fact.get('kind') == 'loot_box' and not _is_contents_key(key):
        if isinstance(value, dict) and ('contents' in value or 'items' in value):
            raise CanonError(
                'An earned loot box is not its contents. Determine contents on {}.'.format(
                    _contents_key(key)))
    _assert_unique(campaign, key, fact.get('kind'), value)
    if _json_size(value) > VALUE_LIMIT:
        raise CanonError('Fact value is too long.')
    prior = {
        'value': copy.deepcopy(fact.get('value')), 'status': canon_status(fact, 'facts'),
        'by': fact.get('by'), 'source': fact.get('source'),
    }
    history = list(fact.get('history') or [])
    history.append(prior)
    fact['history'] = history[-HISTORY_LIMIT:]
    fact['value'] = copy.deepcopy(value)
    fact['status'] = status
    fact['by'] = by
    fact['source'] = source
    fact['current'] = True
    return copy.deepcopy(fact)


def _legacy_rows(campaign):
    rows = []
    fields = PLAY_FIELDS + PLAYER_FIELDS
    for field in fields:
        items = campaign.get(field) or []
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            entry = item if isinstance(item, dict) else {}
            if isinstance(item, dict):
                label = item.get('item') or item.get('name') or item.get('text') or item.get('said') \
                    or item.get('to') or item.get('what') or str(index)
                stored = item
            else:
                label = str(item)
                stored = {'text': label}
            rows.append({
                'kind': field, 'key': '{}:{}'.format(field, index), 'value': copy.deepcopy(stored),
                'status': canon_status(entry, field),
                'by': 'player' if field in PLAYER_FIELDS else 'play',
                'source': None, 'current': True, 'history': [], 'legacy': True, 'label': str(label)[:80],
            })
    return rows


def query(campaign, status=None, kind=None, key=None, include_legacy=False):
    """Current facts, optionally only one status, kind, or key. History is not current."""
    if not isinstance(campaign, dict):
        raise CanonError('The campaign record is an object.')
    rows = []
    for fact in campaign.get('facts') or []:
        if not isinstance(fact, dict) or fact.get('current') is False or not fact.get('key'):
            continue
        row = copy.deepcopy(fact)
        row['status'] = canon_status(row, 'facts')
        row.setdefault('history', [])
        row['current'] = True
        rows.append(row)
    if include_legacy:
        rows.extend(_legacy_rows(campaign))
    if status is not None:
        if status not in STATUSES:
            raise CanonError('Unknown canon status.')
        rows = [row for row in rows if row['status'] == status]
    if kind is not None:
        rows = [row for row in rows if row.get('kind') == kind]
    if key is not None:
        rows = [row for row in rows if row.get('key') == key]
    rows.sort(key=lambda row: (str(row.get('kind')), str(row.get('key'))))
    return rows


def _fmt(number, key):
    if key in GP_KEYS and number >= 1000:
        return '{:,}'.format(number)
    return str(number)


def _forms(number):
    plain = str(number)
    grouped = '{:,}'.format(number)
    if grouped == plain:
        return [plain]
    return [plain, grouped]


def _tail(text, end):
    return text[end:end + 24].lstrip().lower()


def _context_matches(text, end, key):
    """The number at end belongs to this fact's unit, not to some other mention."""
    tail = _tail(text, end)
    per_day = (tail.startswith('gp/day') or tail.startswith('gp / day')
               or tail.startswith('gp per day') or tail.startswith('gp a day'))
    if key == 'gp_per_day':
        return per_day
    if key in ('gp', 'gold', 'amount'):
        if per_day:
            return False
        return tail.startswith('gp') or tail.startswith('gold')
    if key == 'hours':
        return tail.startswith('hour')
    return False


def _occurrences(text, number):
    spans, seen = [], set()
    for form in _forms(number):
        for match in re.finditer(r'\b' + re.escape(form) + r'\b', text):
            span = (match.start(), match.end())
            if span not in seen:
                seen.add(span)
                spans.append(span)
    return spans


def _apply_spans(text, jobs):
    grouped = {}
    for start, end, rendered in jobs:
        grouped.setdefault((start, end), []).append(rendered)
    chosen = []
    for (start, end), rendered in grouped.items():
        if len(set(rendered)) == 1:
            chosen.append((start, end, rendered[0]))
    chosen.sort(key=lambda item: item[0], reverse=True)
    for start, end, rendered in chosen:
        text = text[:start] + rendered + text[end:]
    return text


def _swap(text, campaign):
    """Replace a superseded number only where it is that fact's mention.

    A unit-scoped mention (200 gp/day, not 200 gp) is replaced. A number that
    appears once in the whole recap is that fact's mention. Two unscoped
    mentions are left alone.
    """
    jobs = []
    for fact in query(campaign, include_legacy=False):
        if fact.get('status') not in ('CONFIRMED', 'RESOLVED_IN_PLAY'):
            continue
        current = {}
        for pair_key, number in _numbers(fact.get('value')):
            current[pair_key] = number
        for old in fact.get('history') or []:
            if not isinstance(old, dict):
                continue
            for pair_key, number in _numbers(old.get('value')):
                new = current.get(pair_key)
                if type(new) is not int or type(number) is not int or new == number:
                    continue
                spans = _occurrences(text, number)
                scoped = [span for span in spans if _context_matches(text, span[1], pair_key)]
                if len(scoped) == 1:
                    chosen = scoped
                elif not scoped and len(spans) == 1:
                    chosen = spans
                else:
                    chosen = []
                rendered = _fmt(new, pair_key)
                for start, end in chosen:
                    jobs.append((start, end, rendered))
    return _apply_spans(text, jobs)


def _label_name(text, name):
    if not name or name not in text:
        return text
    pattern = re.compile(re.escape(name) + r'(?!\s*\(proposed ruling\))')
    return pattern.sub(name + LABEL, text, count=1)


def _label(text, campaign):
    for fact in query(campaign, status='PROPOSED', include_legacy=False):
        value = fact.get('value')
        name = None
        if isinstance(value, dict):
            for key in ('name', 'award', 'item', 'title'):
                if isinstance(value.get(key), str) and len(value[key]) >= 3:
                    name = value[key]
                    break
        elif isinstance(value, str) and len(value) >= 3:
            name = value
        if name:
            text = _label_name(text, name)

    confirmed_names = set()
    for fact in query(campaign, include_legacy=False):
        if fact.get('status') in ('CONFIRMED', 'RESOLVED_IN_PLAY'):
            value = fact.get('value')
            if isinstance(value, dict):
                for key in ('name', 'award', 'item', 'title'):
                    if isinstance(value.get(key), str):
                        confirmed_names.add(value[key])
    for match in list(AWARD_MENTION.finditer(text)):
        name = match.group(1)
        if name in confirmed_names:
            continue
        if '(proposed ruling)' in text[match.end(1):match.end(1) + 20]:
            continue
        text = _label_name(text, name)

    def number(match):
        raw = match.group(0)
        if text[match.end():match.end() + 20].lstrip().startswith('(proposed'):
            return raw
        value = int(raw.replace(',', ''))
        facts = []
        for fact in query(campaign, include_legacy=False):
            keys = [key for key, found in _numbers(fact.get('value')) if found == value]
            if keys:
                facts.append((fact, keys))
        settled_hit = False
        proposed_hit = False
        for fact, keys in facts:
            status = fact.get('status')
            for key in keys:
                if not _context_matches(text, match.end(), key):
                    continue
                if status in ('CONFIRMED', 'RESOLVED_IN_PLAY'):
                    settled_hit = True
                elif status == 'PROPOSED':
                    proposed_hit = True
        if proposed_hit:
            return raw + LABEL
        if settled_hit:
            return raw
        statuses = {fact.get('status') for fact, _keys in facts}
        if 'PROPOSED' in statuses:
            return raw + LABEL
        gold = campaign.get('gold_gp')
        if type(gold) is int and gold == value and _context_matches(text, match.end(), 'gp'):
            return raw
        if not facts:
            return raw + LABEL
        return raw

    return NUMBER.sub(number, text)


def render_recap(recap, campaign):
    """Player-facing recap: played values replace superseded drafts; new numbers and awards are labeled."""
    if not isinstance(recap, str) or not recap.strip():
        return recap
    if not isinstance(campaign, dict):
        return recap
    return _label(_swap(recap, campaign), campaign)


def format_value(value):
    if value is None:
        return 'unknown'
    if type(value) is int:
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            item = value[key]
            if key == 'gp_per_day' and type(item) is int:
                parts.append('{} gp/day'.format(_fmt(item, key)))
            elif key == 'gp' and type(item) is int:
                parts.append('{} gp'.format(_fmt(item, key)))
            elif key == 'hours' and type(item) is int:
                parts.append('{} hours'.format(item))
            elif key == 'count' and type(item) is int:
                parts.append('count {}'.format(item))
            elif item is None:
                parts.append('{} unknown'.format(key))
            else:
                parts.append('{} {}'.format(key, item))
        return ', '.join(parts) if parts else 'unknown'
    return str(value)


def record_lines(campaign):
    """Journal / handoff lines. Current facts carry their status; older saves get the documented default."""
    lines = []
    for row in query(campaign, include_legacy=False):
        lines.append('- [{status}] {kind} {key}: {value}'.format(
            status=row['status'], kind=row['kind'], key=row['key'], value=format_value(row.get('value'))))
    counts = {}
    for row in query(campaign, include_legacy=True):
        if row.get('legacy'):
            counts[(row['kind'], row['status'])] = counts.get((row['kind'], row['status']), 0) + 1
    for kind, status in sorted(counts):
        lines.append('- [{status}] {kind}: {count} from the save (status was not stored on the entry)'.format(
            status=status, kind=kind, count=counts[(kind, status)]))
    return lines


def handoff_text(campaign, recap=None):
    """The recap a host shows, plus the current record with each status."""
    if recap is None:
        sessions = sorted(campaign.get('sessions') or [], key=lambda row: row.get('revision') or 0)
        recap = sessions[-1].get('recap') if sessions else None
    lines = []
    shown = render_recap(recap, campaign) if recap else ''
    if shown:
        lines.append(shown)
    lines.append('Campaign record:')
    lines.extend(record_lines(campaign) or ['- None recorded yet.'])
    return '\n'.join(lines)


def _json_same(left, right):
    return (json.dumps(left, sort_keys=True, ensure_ascii=False)
            == json.dumps(right, sort_keys=True, ensure_ascii=False))


def _file_continues(runtime_fact, file_fact):
    """True when the file fact is an adopt or supersede of this runtime snapshot."""
    history = file_fact.get('history') or []
    if not history or not isinstance(history[-1], dict):
        return False
    prior = history[-1]
    if prior.get('status') != canon_status(runtime_fact, 'facts'):
        return False
    if not _json_same(prior.get('value'), runtime_fact.get('value')):
        return False
    return (canon_status(file_fact, 'facts') != canon_status(runtime_fact, 'facts')
            or not _json_same(file_fact.get('value'), runtime_fact.get('value')))


def merge_saved(fresh, old):
    """Runtime facts win per key, except a file adopt or supersede of that snapshot.

    An empty runtime list does not wipe facts already in the save. A CLI adopt or
    supersede whose history ends on the runtime snapshot is kept; the stale
    runtime copy does not become current again.
    """
    fresh_rows = [fact for fact in (fresh or []) if isinstance(fact, dict)]
    old_rows = [fact for fact in (old or []) if isinstance(fact, dict)]
    if not fresh_rows:
        return old_rows
    old_by_key = {fact.get('key'): fact for fact in old_rows}
    merged, seen = [], set()
    for fact in fresh_rows:
        key = fact.get('key')
        seen.add(key)
        previous = old_by_key.get(key)
        if previous is not None and _file_continues(fact, previous):
            merged.append(previous)
        else:
            merged.append(fact)
    for fact in old_rows:
        if fact.get('key') not in seen:
            merged.append(fact)
    return merged


def commit_runtime(runtime, campaign, turn_id='campaign-facts'):
    """Commit the record onto campaign_log. Refuses while a play turn is waiting."""
    if runtime.db.execute('SELECT 1 FROM kit_pending LIMIT 1').fetchone():
        raise CanonError('A turn is waiting. Finish it before recording campaign facts.')
    facts = list(campaign.get('facts') or [])
    check_stored(facts)
    revision, _state = runtime.load()
    runtime.commit(turn_id, revision, [{
        'type': 'campaign_facts', 'facts': facts,
        'evidence': 'Campaign record updated.',
    }])
    return runtime.load()[0]


def _load_file(path):
    file = Path(path)
    if not file.is_file():
        return {'schema': 'kit_campaign_v1', 'facts': []}
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise CanonError('{} is not JSON.'.format(path)) from exc
    if not isinstance(data, dict):
        raise CanonError('The campaign file must be a JSON object.')
    data.setdefault('facts', [])
    return data


def _write_file(path, campaign):
    Path(path).write_text(json.dumps(campaign, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
                          encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='kit_canon', description='Campaign-record canon status.')
    parser.add_argument('command', choices=('record', 'adopt', 'promote', 'supersede', 'query', 'handoff'))
    parser.add_argument('--file', required=True, help='campaign.json (created if missing)')
    parser.add_argument('--kind')
    parser.add_argument('--key')
    parser.add_argument('--value', help='JSON value')
    parser.add_argument('--status', choices=STATUSES)
    parser.add_argument('--by', choices=('kit', 'dm', 'play'))
    parser.add_argument('--source')
    parser.add_argument('--recap')
    args = parser.parse_args(argv)
    try:
        campaign = _load_file(args.file)
        value = None if args.value is None else json.loads(args.value)
        if args.command == 'record':
            fact = record(campaign, args.kind, args.key, value=value, status=args.status,
                          by=args.by or 'kit', source=args.source)
            _write_file(args.file, campaign)
            print(json.dumps(fact, ensure_ascii=False, sort_keys=True))
        elif args.command in ('adopt', 'promote'):
            fact = adopt(campaign, args.key, by=args.by or 'dm', source=args.source)
            _write_file(args.file, campaign)
            print(json.dumps(fact, ensure_ascii=False, sort_keys=True))
        elif args.command == 'supersede':
            fact = supersede(campaign, args.key, value, by=args.by or 'dm', status=args.status,
                             source=args.source)
            _write_file(args.file, campaign)
            print(json.dumps(fact, ensure_ascii=False, sort_keys=True))
        elif args.command == 'query':
            print(json.dumps(query(campaign, status=args.status, kind=args.kind, key=args.key,
                                   include_legacy=True), ensure_ascii=False, sort_keys=True))
        else:
            print(handoff_text(campaign, recap=args.recap))
    except (CanonError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

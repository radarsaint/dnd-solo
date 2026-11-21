"""One-command adventure preparation with per-book caching (v0.11.1).

``adventure prepare <pdf> --db kit.sqlite`` runs ingest and the structural index in
one step and times each part. The finished preparation (and later the accepted
opening skim) is kept per book hash, so the same book never prepares twice: a
fresh save for a book already prepared restores it in about a second.

The cache holds the private retained PDF and its index. It lives outside the
repository (default ``~/.cache/kit-prep``, or ``KIT_PREP_CACHE``) and is never committed.
"""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from . import kit_adventure

META = 'prep_cache.json'


def cache_root(explicit=None):
    root = explicit or os.environ.get('KIT_PREP_CACHE') or str(Path.home() / '.cache' / 'kit-prep')
    return Path(root)


def _entry_name(sha):
    """Cache entry for one book read by one reader: a prep made by another reader is not reused."""
    from . import kit_readers
    return '%s-%s' % (sha, kit_readers.cache_tag())


def book_sha(pdf):
    digest = hashlib.sha256()
    with Path(pdf).open('rb') as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _rewrite(folder, old_folder, new_folder, old_db, new_db):
    """Cached files name the save they were made for; point them at this one."""
    pairs = [(str(old_folder), str(new_folder)), (str(old_db), str(new_db))]
    for path in folder.rglob('*.json'):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        changed = text
        for old, new in pairs:
            if old and old != new:
                changed = changed.replace(json.dumps(old)[1:-1], json.dumps(new)[1:-1])
        if changed != text:
            path.write_text(changed, encoding='utf-8')


def _copy(src, dst):
    def link_or_copy(a, b):
        try:
            os.link(a, b)  # the retained PDF is immutable; a hard link costs nothing
        except OSError:
            shutil.copy2(a, b)
    shutil.copytree(str(src), str(dst), copy_function=link_or_copy)


def save(db, stage, root=None):
    """Keep this save's preparation for its book hash. Returns the cache entry or None."""
    folder = kit_adventure.folder_for(db)
    receipt = folder / 'source.pdf.json'
    if not receipt.is_file():
        return None
    sha = json.loads(receipt.read_text(encoding='utf-8')).get('sha256')
    meta_here = folder / META
    if meta_here.is_file():
        root = root or json.loads(meta_here.read_text(encoding='utf-8')).get('root')
    entry = cache_root(root) / _entry_name(sha)
    tmp = entry.with_name(sha + '.tmp-%d' % os.getpid())
    try:
        if tmp.exists():
            shutil.rmtree(str(tmp))
        tmp.mkdir(parents=True)
        _copy(folder, tmp / 'adventure')
        (tmp / 'meta.json').write_text(json.dumps({
            'sha256': sha, 'stage': stage, 'db': str(Path(db).resolve()), 'folder': str(folder.resolve()),
            'saved_at': time.time()}), encoding='utf-8')
        if entry.exists():
            shutil.rmtree(str(entry))
        os.replace(str(tmp), str(entry))
    except OSError:
        shutil.rmtree(str(tmp), ignore_errors=True)
        return None
    (folder / META).write_text(json.dumps({'root': str(cache_root(root)), 'sha256': sha, 'stage': stage}),
                               encoding='utf-8')
    return entry


def restore(db, sha, root=None):
    """Restore a cached preparation into a fresh save. Returns the cached stage or None."""
    entry = cache_root(root) / _entry_name(sha)
    meta_path = entry / 'meta.json'
    folder = kit_adventure.folder_for(db)
    if not meta_path.is_file() or folder.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    try:
        _copy(entry / 'adventure', folder)
    except OSError:
        shutil.rmtree(str(folder), ignore_errors=True)
        return None
    _rewrite(folder, meta.get('folder'), folder.resolve(), meta.get('db'), Path(db).resolve())
    (folder / META).write_text(json.dumps({'root': str(cache_root(root)), 'sha256': sha,
                                           'stage': meta.get('stage')}), encoding='utf-8')
    _fresh_session(db)
    return meta.get('stage')


# What one session did with the opening, never part of the book's preparation: a restored
# save starts like a cold one (landing, sheet, the ready line, Yes, then the opening).
SESSION_FLAGS = ('speak_now', 'burst_spoken', 'sheet', 'knowledge_result', 'screen_failed')


def _fresh_session(db):
    from . import kit_skim
    data = kit_skim._read(db)
    if not data:
        return
    changed = False
    for key in SESSION_FLAGS:
        if key in data:
            data.pop(key)
            changed = True
    beat = data.get('beat')
    if isinstance(beat, dict) and beat.get('heard'):
        beat['heard'] = 0
        changed = True
    if changed:
        kit_skim._write(db, data)


def prepare(db, pdf, reader='auto', root=None):
    """Ingest plus index in one step, timed, cached per book hash."""
    from . import kit_skim
    steps = {}
    clock = time.perf_counter()
    sha = book_sha(pdf)
    steps['hash_ms'] = round((time.perf_counter() - clock) * 1000, 1)
    tick = time.perf_counter()
    stage = restore(db, sha, root)
    steps['cache_ms'] = round((time.perf_counter() - tick) * 1000, 1)
    if stage:
        readiness = kit_adventure.readiness(db)
        skim = kit_skim._read(db)
        accepted = skim.get('status') == 'accepted'
        return {
            'stage': 'adventure_prepared', 'cached': True, 'source_pdf_sha256': sha,
            'skim_status': skim.get('status') or 'not_started',
            'index_complete': readiness.get('index_complete'),
            # The same first line as a cold prepare: the player hands over the sheet first;
            # the ready line comes from start, and the opening only after Yes.
            'table_line': kit_skim.LANDING,
            'next': ('Opening already accepted for this book. Run status, then start with the sheet.'
                     if accepted else 'Index ready. Skim the opening next (skim_request).'),
            'skim_request': None if accepted else kit_skim.request_for(db),
            'status_command': 'python3 -m runtime.kit_agent status --db %s' % db,
            'steps_ms': steps, 'total_ms': round((time.perf_counter() - clock) * 1000, 1),
        }
    tick = time.perf_counter()
    report = kit_adventure.ingest_adventure(db, pdf=str(pdf), reader=reader)
    steps['ingest_ms'] = round((time.perf_counter() - tick) * 1000, 1)
    tick = time.perf_counter()
    deep = kit_adventure.deepen_index(db, reader=report.get('reader') or reader)
    steps['index_ms'] = round((time.perf_counter() - tick) * 1000, 1)
    tick = time.perf_counter()
    request = kit_skim.request_for(db)
    steps['skim_request_ms'] = round((time.perf_counter() - tick) * 1000, 1)
    tick = time.perf_counter()
    saved = save(db, 'indexed', root)
    steps['cache_save_ms'] = round((time.perf_counter() - tick) * 1000, 1)
    return {
        'stage': 'adventure_prepared', 'cached': False, 'source_pdf_sha256': sha,
        'reader': report.get('reader'), 'title': report.get('title'),
        'index_complete': deep.get('index_complete'), 'locations': deep.get('locations'),
        'start_location': report.get('start_location'),
        'first_scene_page': report.get('first_scene_page'),
        'table_line': kit_skim.LANDING, 'skim_status': 'not_started',
        'next': 'Say table_line now. Then skim the opening (skim_request) while the player answers.',
        'skim_request': request, 'skim_command': request.get('command'),
        'cache_saved': bool(saved),
        'steps_ms': steps, 'total_ms': round((time.perf_counter() - clock) * 1000, 1),
    }


def after_skim(db, result):
    """Keep an accepted opening with the book's cached preparation (only for prepared saves)."""
    if isinstance(result, dict) and result.get('stage') == 'skim_accepted' and \
            (kit_adventure.folder_for(db) / META).is_file():
        save(db, 'skim_accepted')
    return result

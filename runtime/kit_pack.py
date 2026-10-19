"""Private rooms packs: playable rooms a host attaches next to the runtime ZIP.

Rooms adapted from a published adventure can't live in this public repo. A host (a ChatGPT
custom GPT or Project, a Claude Project, any shell) attaches them as a pack instead: a folder
or a ZIP holding ``manifest.json`` and the room files. Plain python3, standard library only;
nothing here depends on one host.

manifest.json (schema ``kit-rooms-pack/v1``; docs/architecture/ROOM_PACKS.md)::

    {"schema": "kit-rooms-pack/v1", "pack": "<name>", "private": true,
     "first_room": "rooms/<file>.json",
     "rooms": [{"path": "rooms/<file>.json", "room_id": "<the room file's id>", ...}, ...]}

Paths are relative to the manifest's folder. Other keys (level, area, kind, summary,
built_for_runtime) are notes for people; the engine never sends them to Kit, and a summary
can carry spoilers. ``campaign`` is optional and defaults to ``dotmm``.

Discovery: ``start --pack PATH`` (a ZIP, a pack folder, its manifest.json, or a folder holding
one of those). Without --pack, ``start`` looks in the working directory, the repository root, and
the usual upload folders (/mnt/data, /mnt/user-data/uploads, /mnt/user-data): each folder itself,
its direct subfolders, and its *.zip files. A ZIP and the folder it was unzipped to are one pack.
Two different packs is an error that asks for --pack. A ZIP is unzipped next to the save, under
.kit-packs/, so the room paths in the save still work after the next start.
"""
import contextlib
import hashlib
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

from .state_context import PROJECT_ROOT

SCHEMA = 'kit-rooms-pack/v1'
MANIFEST = 'manifest.json'
UPLOAD_DIRS = ('/mnt/data', '/mnt/user-data/uploads', '/mnt/user-data')
CACHE_DIR = '.kit-packs'
DEFAULT_CAMPAIGN = 'dotmm'
# Discovery roots. None: the working dir, the repo root and UPLOAD_DIRS. A list replaces them all
# (tests isolate discovery with it; the CLI's --upload-dir replaces UPLOAD_DIRS only).
SEARCH_ROOTS = None


class PackError(Exception):
    """A pack that can't be used. host_view() is the JSON the CLI prints."""

    def __init__(self, error, message, **details):
        super().__init__(message)
        self.error, self.details = error, details

    def host_view(self):
        return {'stage': 'rejected', 'committed': False, 'error': self.error, 'message': str(self),
                **self.details,
                'table_line': getattr(self, 'table_line', None) or
                "I can't open those rooms. The attached rooms pack isn't usable, so I won't improvise one.",
                'next_step': getattr(self, 'next_step', None) or
                'Say table_line. Do not invent a room. Tell the host what message says.'}


class Pack:
    def __init__(self, root, manifest, origin):
        self.root, self.manifest, self.origin = Path(root), manifest, str(origin)

    @property
    def name(self):
        return str(self.manifest.get('pack') or self.root.name)

    @property
    def campaign(self):
        return str(self.manifest.get('campaign') or DEFAULT_CAMPAIGN)

    def rooms(self):
        return [entry for entry in self.manifest['rooms']]

    def path(self, rel):
        return _inside(self.root, rel)

    def first_room(self):
        return self.path(self.manifest['first_room'])

    def find(self, name):
        """The room file for a name: a manifest path, a file name with or without .json, or a room_id."""
        want = str(name).strip()
        key = want.casefold()
        for entry in self.rooms():
            rel = PurePosixPath(entry['path'])
            names = {rel.as_posix(), rel.name, rel.stem, str(entry.get('room_id') or '')}
            if want in names or key in {n.casefold() for n in names if n}:
                return self.path(entry['path'])
        return None

    def room_ids(self):
        return [entry.get('room_id') or PurePosixPath(entry['path']).stem for entry in self.rooms()]

    def summary(self):
        """What the host may see: names and ids. Never summaries (they can carry spoilers)."""
        first = self.manifest['first_room']
        entry = next((e for e in self.rooms() if e['path'] == first), {})
        return {'found': True, 'pack': self.name, 'campaign': self.campaign, 'origin': self.origin,
                'root': str(self.root), 'first_room': entry.get('room_id') or PurePosixPath(first).stem,
                'rooms': self.room_ids()}


@contextlib.contextmanager
def uploads(folders):
    """Use these folders as the host upload folders while the block runs (the CLI's --upload-dir);
    None or empty keeps UPLOAD_DIRS."""
    global UPLOAD_DIRS
    saved = UPLOAD_DIRS
    if folders:
        UPLOAD_DIRS = tuple(str(f) for f in folders)
    try:
        yield
    finally:
        UPLOAD_DIRS = saved


def search_dirs():
    """Where start looks for a pack when --pack is not given, in order."""
    out = []
    roots = SEARCH_ROOTS if SEARCH_ROOTS is not None else (Path.cwd(), PROJECT_ROOT, *map(Path, UPLOAD_DIRS))
    for folder in map(Path, roots):
        try:
            folder = folder.resolve()
        except OSError:
            continue
        if folder not in out and folder.is_dir():
            out.append(folder)
    return out


def _manifest_problems(manifest, has, inside=None):
    """Problems with a manifest. ``has(rel)`` says whether a file exists in the pack."""
    problems = []
    if not isinstance(manifest, dict):
        return ['manifest.json is not a JSON object']
    if manifest.get('schema') != SCHEMA:
        problems.append(f'schema must be {SCHEMA!r}')
    rooms = manifest.get('rooms')
    if not isinstance(rooms, list) or not rooms:
        problems.append('rooms must be a non-empty list of {"path": ...}')
        rooms = []
    paths = []
    for i, entry in enumerate(rooms):
        rel = entry.get('path') if isinstance(entry, dict) else None
        if not isinstance(rel, str) or not _safe(rel):
            problems.append(f'rooms[{i}].path must be a relative path inside the pack')
            continue
        paths.append(rel)
        if not has(rel):
            problems.append(f'rooms[{i}].path {rel!r} is not in the pack')
        elif inside is not None and not inside(rel):
            problems.append(f'rooms[{i}].path {rel!r} resolves outside the pack (a symlink); refused')
    first = manifest.get('first_room')
    if not isinstance(first, str) or not _safe(first):
        problems.append('first_room must be a relative path inside the pack')
    elif first not in paths:
        problems.append(f'first_room {first!r} is not one of rooms[].path')
    return problems


def _inside(root, rel):
    """The real path of ``rel`` under ``root``, or a PackError when it resolves outside the pack
    (a symlink to /etc/passwd, a symlinked rooms folder pointing elsewhere)."""
    real_root = Path(os.path.realpath(root))
    real = Path(os.path.realpath(Path(root) / rel))
    if real != real_root and real_root not in real.parents:
        raise PackError('pack_invalid', f'The rooms pack at {root} has a room outside the pack: {rel!r}.',
                        pack_path=str(root), problems=[f'{rel!r} resolves outside the pack'])
    return real


def _is_inside(root, rel):
    try:
        _inside(root, rel)
        return True
    except PackError:
        return False


def _safe(rel):
    parts = PurePosixPath(rel.replace('\\', '/')).parts
    return bool(parts) and not rel.startswith(('/', '\\')) and '..' not in parts and ':' not in parts[0]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _is_pack_manifest(data):
    return isinstance(data, dict) and data.get('schema') == SCHEMA


def _zip_manifest(zpath):
    """(prefix, manifest) for a ZIP holding a pack manifest at its top or one folder down, else None."""
    try:
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():
                parts = PurePosixPath(name).parts
                if parts and parts[-1] == MANIFEST and len(parts) <= 2:
                    try:
                        data = json.loads(zf.read(name).decode('utf-8'))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if _is_pack_manifest(data):
                        return (parts[0] + '/' if len(parts) == 2 else ''), data
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def _folder_pack(folder):
    data = _read_json(Path(folder) / MANIFEST)
    return data if _is_pack_manifest(data) else None


def candidates(folders):
    """Every pack in these folders: (kind, path, manifest). Each folder, its subfolders, its ZIPs."""
    found = []
    for folder in folders:
        folder = Path(folder)
        if _folder_pack(folder):
            found.append(('folder', folder, _folder_pack(folder)))
        try:
            children = sorted(folder.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith('.'):
                continue  # .kit-packs holds our own unzipped copies
            if child.is_dir() and _folder_pack(child):
                found.append(('folder', child, _folder_pack(child)))
            elif child.is_file() and child.suffix.lower() == '.zip':
                hit = _zip_manifest(child)
                if hit:
                    found.append(('zip', child, hit[1]))
    seen, out = set(), []
    for kind, path, manifest in found:
        key = path.resolve()
        if key not in seen:
            seen.add(key)
            out.append((kind, path, manifest))
    return out


def _distinct(found):
    """One entry per pack name; an unzipped folder wins over its ZIP."""
    by_name = {}
    for kind, path, manifest in found:
        name = str(manifest.get('pack') or path.stem)
        if name not in by_name or (kind == 'folder' and by_name[name][0] == 'zip'):
            by_name[name] = (kind, path, manifest)
    return list(by_name.values())


def _cache_root(db):
    return Path(db).resolve().parent / CACHE_DIR


def _extract(zpath, db):
    prefix, _ = _zip_manifest(zpath)
    digest = hashlib.sha256(Path(zpath).read_bytes()).hexdigest()[:8]
    target = _cache_root(db) / f'{Path(zpath).stem}-{digest}'
    with zipfile.ZipFile(zpath) as zf:
        members = [m for m in zf.infolist() if m.filename.startswith(prefix)]
        bad = [m.filename for m in zf.infolist() if not _safe(m.filename)]
        if bad:
            raise PackError('pack_invalid', f'{zpath} has entries outside its folder',
                            pack_path=str(zpath), problems=[f'unsafe entry {b!r}' for b in bad])
        if not (target / prefix / MANIFEST).is_file():
            target.mkdir(parents=True, exist_ok=True)
            for member in members:
                zf.extract(member, target)
    return target / prefix


def open_pack(path, db):
    """The pack at ``path``: a ZIP, a pack folder, its manifest.json, or a folder holding one pack."""
    path = Path(path).expanduser()
    if not path.exists():
        raise PackError('pack_not_found', f'No rooms pack at {path}.', pack_path=str(path))
    origin = path
    if path.is_file() and path.name == MANIFEST:
        path = path.parent
    if path.is_file():
        if _zip_manifest(path) is None:
            raise PackError('pack_invalid', f'{path} is not a ZIP holding a {SCHEMA} {MANIFEST}.',
                            pack_path=str(path), problems=[f'no {MANIFEST} with schema {SCHEMA!r}'])
        path = _extract(path, db)
    elif not (path / MANIFEST).is_file():
        found = _distinct(candidates([path]))
        if len(found) != 1:
            if not found:
                raise PackError('pack_not_found', f'No rooms pack in {path}.', pack_path=str(path))
            raise _ambiguous(found)
        return open_pack(found[0][1], db)
    manifest = _read_json(path / MANIFEST)
    problems = _manifest_problems(manifest, lambda rel: (path / rel).is_file(), lambda rel: _is_inside(path, rel))
    if problems:
        if any('outside the pack' in p for p in problems):
            problems = [p for p in problems if 'outside the pack' in p] + [p for p in problems if 'outside the pack' not in p]
        raise PackError('pack_invalid', f'The rooms pack at {origin} has problems: ' + '; '.join(problems),
                        pack_path=str(origin), problems=problems)
    return Pack(path.resolve(), manifest, origin)


_COUNT_WORDS = ('No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten')


def _ambiguous(found):
    names = [str(m.get('pack') or p.stem) for _, p, m in found]
    count = _COUNT_WORDS[len(names)] if len(names) < len(_COUNT_WORDS) else str(len(names))
    listed = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    error = PackError('pack_ambiguous', 'More than one rooms pack is attached. Pass --pack with the one to use.',
                      packs=[{'pack': m.get('pack'), 'path': str(p)} for _, p, m in found])
    error.table_line = f'{count} rooms packs are attached: {listed}. Which one should I open?'
    error.next_step = ("Say table_line and wait for the player's answer. Then run start again with --pack and "
                       "that pack's path (packs[].path). Do not pick one yourself.")
    return error


def resolve(db, explicit=None):
    """The pack to use, or None. --pack wins; otherwise exactly one discovered pack."""
    if explicit:
        return open_pack(explicit, db)
    found = _distinct(candidates(search_dirs()))
    if not found:
        return None
    if len(found) > 1:
        raise _ambiguous(found)
    return open_pack(found[0][1], db)


def not_found():
    return {'found': False, 'searched': [str(p) for p in search_dirs()]}


def same_campaign(asked, campaign):
    from .kit_campaign import MAD_MAGE_KEYS
    a, b = str(asked).strip().casefold(), str(campaign).strip().casefold()
    return a == b or (a in MAD_MAGE_KEYS and b in MAD_MAGE_KEYS)


def room_labels(rooms):
    """Spoiler-free labels for the lobby: only the book's level and area numbers ("Level 1, area 8c").
    Never a summary, a kind or the room's own area names: those can give the room away."""
    labels = {}
    for entry in rooms:
        level, area = entry.get('level'), entry.get('area')
        if type(level) is int and isinstance(area, (str, int)) and str(area).strip() and \
                len(str(area)) <= 8 and str(area).replace('-', '').isalnum():
            labels[entry.get('room_id') or PurePosixPath(entry['path']).stem] = f'Level {level}, area {area}'
    return labels


def listing(folders=None):
    """Every attached pack, for the lobby: name, the path to pass to --pack, first room, room ids.
    Read from the manifests only; nothing is unzipped and no summary is shown."""
    out = []
    for kind, path, manifest in _distinct(candidates(search_dirs() if folders is None else folders)):
        rooms = [e for e in manifest.get('rooms') or [] if isinstance(e, dict) and isinstance(e.get('path'), str)]
        ids = [e.get('room_id') or PurePosixPath(e['path']).stem for e in rooms]
        first = next((e.get('room_id') or PurePosixPath(e['path']).stem for e in rooms
                      if e['path'] == manifest.get('first_room')), None)
        out.append({'pack': str(manifest.get('pack') or path.stem), 'path': str(path), 'kind': kind,
                    'campaign': str(manifest.get('campaign') or DEFAULT_CAMPAIGN),
                    'first_room': first, 'rooms': ids, 'room_labels': room_labels(rooms)})
    return out

#!/usr/bin/env python3
"""Build, mount, and verify a complete Kit source snapshot. Python stdlib only.

Building requires git. Mounting needs only the downloaded ZIP and Python 3.10+;
it never needs network access, an API key, or a selected game.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import uuid
import zipfile


PREFIX = 'dnd-solo-main/'
MANIFEST = 'KIT_SOURCE_MANIFEST.json'
SCHEMA = 'kit-host-v1'
REQUIRED = ('AGENTS.md', 'START_HERE.md', 'LOAD_KIT.md',
            'runtime/kit_agent.py', 'runtime/state_context.py',
            'docs/personality/dm-personality-core.md',
            'docs/personality/kit-taste.json', 'runtime/data/srd_5_1_prices.json')


def git_hash(kind, data):
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def safe_path(path):
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or '\\' in path or str(p) != path:
        raise ValueError(f'Invalid source path: {path!r}')
    return p


def tree_hash(files):
    """Reconstruct Git's root tree, so removing a manifest row is detectable."""
    root = {}
    for item in files:
        path = safe_path(item['path'])
        node = root
        for part in path.parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ValueError('Conflicting manifest paths')
        if path.name in node:
            raise ValueError(f'Duplicate manifest path: {path}')
        if item['mode'] not in ('100644', '100755') or not re.fullmatch('[0-9a-f]{40}', item['sha1']):
            raise ValueError(f'Unsupported manifest entry: {path}')
        node[path.name] = (item['mode'], item['sha1'])

    def digest(node):
        rows = []
        for name, value in node.items():
            directory = isinstance(value, dict)
            mode, sha = ('40000', digest(value)) if directory else value
            rows.append(((name + ('/' if directory else '')).encode(),
                         mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(sha)))
        return git_hash('tree', b''.join(row[1] for row in sorted(rows)))
    return digest(root)


def validate_manifest(manifest, expected_commit=None, expected_tree=None):
    if manifest.get('schema') != SCHEMA:
        raise ValueError('This ZIP has no supported complete-source manifest')
    for key in ('commit', 'tree'):
        if not re.fullmatch('[0-9a-f]{40}', manifest.get(key, '')):
            raise ValueError(f'Invalid source {key}')
    if expected_commit and manifest['commit'] != expected_commit:
        raise ValueError('The bundle does not match the requested commit')
    if expected_tree and manifest['tree'] != expected_tree:
        raise ValueError('The bundle does not match the requested source tree')
    files = manifest['files']
    if tree_hash(files) != manifest['tree']:
        raise ValueError('The manifest does not describe the complete source tree')
    paths = {item['path'] for item in files}
    if not set(REQUIRED).issubset(paths):
        raise ValueError('The source snapshot is missing required Kit host files')
    if not any(p.startswith('docs/voice/') and p.endswith('.md') for p in paths):
        raise ValueError('The source snapshot is missing the voice files')
    return manifest


def verify(root, expected_commit=None, expected_tree=None):
    root = Path(root).resolve()
    manifest = validate_manifest(json.loads((root / MANIFEST).read_text(encoding='utf-8')),
                                 expected_commit, expected_tree)
    failures = []
    for item in manifest['files']:
        path = root / item['path']
        if not path.is_file() or path.is_symlink() or root not in path.resolve().parents:
            failures.append(item['path'])
            continue
        data = path.read_bytes()
        if len(data) != item['size'] or git_hash('blob', data) != item['sha1']:
            failures.append(item['path'])
    if failures:
        raise ValueError('Missing or changed source files: ' + ', '.join(failures))
    return manifest


def build(repo, output, commit='HEAD'):
    repo, output = Path(repo).resolve(), Path(output).resolve()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])

    commit = git('rev-parse', '--verify', commit + '^{commit}').decode().strip()
    root_tree = git('rev-parse', commit + '^{tree}').decode().strip()
    entries = []
    for row in git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not row:
            continue
        meta, raw_path = row.split(b'\t', 1)
        mode, kind, sha = meta.decode().split()
        path = raw_path.decode()
        safe_path(path)
        if kind != 'blob' or mode not in ('100644', '100755') or path == MANIFEST:
            raise ValueError(f'Unsupported source entry: {path}')
        data = git('cat-file', 'blob', sha)
        entries.append({'path': path, 'mode': mode, 'sha1': sha, 'size': len(data)})
    manifest = {'schema': SCHEMA, 'commit': commit, 'tree': root_tree, 'files': entries}
    validate_manifest(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write every tracked blob directly: no allowlist, export-ignore, working-tree
    # edits, generated caches, or local campaign databases enter this snapshot.
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.comment = commit.encode()
        for item in entries:
            info = zipfile.ZipInfo(PREFIX + item['path'], (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = int(item['mode'], 8) << 16
            archive.writestr(info, git('cat-file', 'blob', item['sha1']))
        info = zipfile.ZipInfo(PREFIX + MANIFEST, (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(manifest, indent=2) + '\n')
    return {'status': 'built', 'commit': commit, 'tree': root_tree,
            'files': len(entries), 'archive': str(output),
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def host_context(root, manifest):
    """Exercise the real persona entry point; create no game or database."""
    result = subprocess.run([sys.executable, '-B', '-m', 'runtime.kit_agent', 'persona'],
                            cwd=root, capture_output=True, text=True, timeout=60,
                            env={**os.environ, 'PYTHONPATH': str(root), 'PYTHONIOENCODING': 'utf-8'})
    if result.returncode:
        raise ValueError('Kit persona failed: ' + result.stderr[-2000:])
    if not result.stdout.strip() or 'Voice warning:' in result.stdout:
        raise ValueError('Kit persona is empty or reports omitted voice material')
    context = ('# Kit host context\n\nSource commit: ' + manifest['commit'] +
               '\n\nRead this entire file before reporting Kit loaded. '
               'The verified files are mounted; this text supplies the host instructions '
               'and the runtime-produced personality and voice. A game has not been started.\n\n' +
               '## Host instructions\n\n' + (root / 'AGENTS.md').read_text(encoding='utf-8') +
               '\n\n## Runtime personality and voice\n\n' + result.stdout)
    path = root.parent / (root.name + '-HOST_CONTEXT.md')
    path.write_text(context, encoding='utf-8')
    return path


def mount(archive_path, destination, expected_commit=None, expected_tree=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        manifest_bytes = archive.read(PREFIX + MANIFEST)
        manifest = validate_manifest(json.loads(manifest_bytes), expected_commit, expected_tree)
        wanted = {PREFIX + item['path'] for item in manifest['files']} | {PREFIX + MANIFEST}
        if set(names) != wanted:
            raise ValueError('Archive members differ from the complete-source manifest')
        root = destination / ('kit-' + manifest['commit'])
        reuse = False
        if root.is_dir():
            try:
                verify(root, manifest['commit'], manifest['tree'])
                reuse = True
            except (ValueError, OSError, KeyError, TypeError):
                pass
        previous = None
        if not reuse:
            with tempfile.TemporaryDirectory(prefix='kit-mount-', dir=destination) as staging:
                temporary = Path(staging) / 'repo'
                temporary.mkdir()
                for item in manifest['files']:
                    data = archive.read(PREFIX + item['path'])
                    if len(data) != item['size'] or git_hash('blob', data) != item['sha1']:
                        raise ValueError('Archive file failed verification: ' + item['path'])
                    path = temporary / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    path.chmod(int(item['mode'], 8) & 0o777)
                (temporary / MANIFEST).write_bytes(manifest_bytes)
                verify(temporary, manifest['commit'], manifest['tree'])
                if root.exists():
                    previous = root.with_name(root.name + '-preserved-' + uuid.uuid4().hex[:8])
                    root.rename(previous)
                temporary.rename(root)
    manifest = verify(root, manifest['commit'], manifest['tree'])
    context = host_context(root, manifest)
    return {'status': 'mounted', 'commit': manifest['commit'], 'tree': manifest['tree'],
            'verified_files': len(manifest['files']), 'root': str(root),
            'host_context': str(context), 'persona_exit': 0, 'reused': reuse,
            'preserved_previous_root': str(previous) if previous else None,
            'game_started': False, 'host_context_read': False,
            'next': 'Read the entire host_context file; then use this verified build as Kit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    builder = commands.add_parser('build')
    builder.add_argument('--repo', default='.')
    builder.add_argument('--commit', default='HEAD')
    builder.add_argument('--output', required=True)
    mounter = commands.add_parser('mount')
    mounter.add_argument('--archive', required=True)
    mounter.add_argument('--destination', required=True)
    verifier = commands.add_parser('verify')
    verifier.add_argument('--root', required=True)
    for child in (mounter, verifier):
        child.add_argument('--expected-commit')
        child.add_argument('--expected-tree')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            report = build(args.repo, args.output, args.commit)
        elif args.command == 'mount':
            report = mount(args.archive, args.destination, args.expected_commit, args.expected_tree)
        else:
            manifest = verify(args.root, args.expected_commit, args.expected_tree)
            report = {'status': 'verified', 'commit': manifest['commit'],
                      'tree': manifest['tree'], 'verified_files': len(manifest['files'])}
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'blocked', 'error': str(error)}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

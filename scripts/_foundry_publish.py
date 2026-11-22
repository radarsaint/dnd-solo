"""Crash-aware publishing for rebuildable artifacts, Python 3.8+ and stdlib-only.

A single file is atomically replaced after its bytes are flushed. A directory
cannot be atomically exchanged portably on Windows/POSIX; staged_directory
instead preserves a previous version as a backup while promoting a complete
staged tree, and restores it if the final rename fails. On restart, a backup
with a missing target is recovered before new work begins.

Neither primitive guarantees a power-loss-durable directory entry. Consumers
remain responsible for verifying their own schema, provenance, and manifests.
"""
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


def atomic_write_text(path, content, encoding="utf-8"):
    """Replace a generated text file only after a successful complete write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _remove_tree(path):
    if path.is_symlink():
        raise ValueError("Refusing a symlink at publication boundary: " + str(path))
    if path.exists():
        if not path.is_dir():
            raise ValueError("Expected a directory at publication boundary: " + str(path))
        shutil.rmtree(str(path))


@contextmanager
def staged_directory(destination):
    """Build into a sibling staging directory, then promote with rollback.

    Limitations: there is a brief non-atomic interval between the two rename
    operations; a crash in that interval is recovered on the *next invocation*.
    This is suitable for offline rebuildable indexes, not a live database.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name("." + destination.name + ".foundry-backup")
    if destination.is_symlink() or backup.is_symlink():
        raise ValueError("Refusing a symlink at publication boundary")
    if backup.exists():
        if not destination.exists():
            os.replace(str(backup), str(destination))
        else:
            # Promotion had already succeeded; an obsolete backup survived.
            _remove_tree(backup)
    if destination.exists() and not destination.is_dir():
        raise ValueError("Publication target is not a directory")
    stage = Path(tempfile.mkdtemp(prefix="." + destination.name + ".stage-",
                                  dir=str(destination.parent)))
    moved_previous = False
    try:
        yield stage
        if destination.exists():
            os.replace(str(destination), str(backup))
            moved_previous = True
        try:
            os.replace(str(stage), str(destination))
        except BaseException:
            if moved_previous and not destination.exists() and backup.exists():
                os.replace(str(backup), str(destination))
            raise
        if moved_previous:
            _remove_tree(backup)
    finally:
        _remove_tree(stage)

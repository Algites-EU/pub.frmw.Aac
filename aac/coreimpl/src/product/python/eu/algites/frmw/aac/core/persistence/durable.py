from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping, Any

from .aic_inter_process_lock_state import AIcInterProcessLockState
from .aic_inter_process_file_lock import AIcInterProcessFileLock

def fsync_directory(path: Path) -> None:
    """Best-effort directory sync after durable namespace changes."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)

def fsync_file(path: Path) -> None:
    try:
        with path.open("rb") as stream:
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
    except OSError:
        pass

def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
        fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
        fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

def durable_replace(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_parent = source.parent
    target_parent = target.parent
    os.replace(source, target)
    fsync_directory(target_parent)
    if source_parent != target_parent:
        fsync_directory(source_parent)

def durable_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    fsync_directory(path.parent)

_AI_INTERPROCESS_LOCK_REGISTRY = {}

_AI_INTERPROCESS_LOCK_REGISTRY_GUARD = None

def _lock_registry_guard():
    global _AI_INTERPROCESS_LOCK_REGISTRY_GUARD
    if _AI_INTERPROCESS_LOCK_REGISTRY_GUARD is None:
        from threading import Lock
        _AI_INTERPROCESS_LOCK_REGISTRY_GUARD = Lock()
    return _AI_INTERPROCESS_LOCK_REGISTRY_GUARD

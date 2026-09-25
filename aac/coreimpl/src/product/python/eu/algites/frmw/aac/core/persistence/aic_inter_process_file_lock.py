from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping, Any

from .aic_inter_process_lock_state import AIcInterProcessLockState

_AI_INTERPROCESS_LOCK_REGISTRY = {}

_AI_INTERPROCESS_LOCK_REGISTRY_GUARD = None

def _lock_registry_guard():
    global _AI_INTERPROCESS_LOCK_REGISTRY_GUARD
    if _AI_INTERPROCESS_LOCK_REGISTRY_GUARD is None:
        from threading import Lock
        _AI_INTERPROCESS_LOCK_REGISTRY_GUARD = Lock()
    return _AI_INTERPROCESS_LOCK_REGISTRY_GUARD

class AIcInterProcessFileLock:
    """Reentrant-in-process, exclusive cross-process filesystem-domain lock."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        with _lock_registry_guard():
            self._state = _AI_INTERPROCESS_LOCK_REGISTRY.setdefault(str(self.path), AIcInterProcessLockState())
        self._entered = False

    def __enter__(self):
        self._state.thread_lock.acquire()
        try:
            if self._state.depth == 0:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                stream = self.path.open("a+b")
                try:
                    try:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                    except ImportError:
                        import msvcrt
                        stream.seek(0)
                        stream.write(b"0")
                        stream.flush()
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                except Exception:
                    stream.close()
                    raise
                self._state.stream = stream
            self._state.depth += 1
            self._entered = True
            return self
        except Exception:
            self._state.thread_lock.release()
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._entered:
            return
        try:
            self._state.depth -= 1
            if self._state.depth == 0:
                stream = self._state.stream
                self._state.stream = None
                if stream is not None:
                    try:
                        try:
                            import fcntl
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                        except ImportError:
                            import msvcrt
                            stream.seek(0)
                            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    finally:
                        stream.close()
        finally:
            self._entered = False
            self._state.thread_lock.release()

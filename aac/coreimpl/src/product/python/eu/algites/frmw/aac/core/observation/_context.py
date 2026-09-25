from __future__ import annotations

from contextvars import ContextVar

ACTIVE_OBSERVERS: ContextVar[frozenset[str]] = ContextVar("aac_active_observers", default=frozenset())

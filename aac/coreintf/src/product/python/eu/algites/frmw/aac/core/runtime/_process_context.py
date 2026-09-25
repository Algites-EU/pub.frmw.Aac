from __future__ import annotations

from contextvars import ContextVar

CURRENT_PROCESS_INVOCATION_ID: ContextVar[str | None] = ContextVar("aac_process_invocation_id", default=None)

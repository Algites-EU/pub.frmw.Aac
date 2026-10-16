from __future__ import annotations
from enum import Enum


class AInOperationCancellationReason(str, Enum):
    """Core-assigned cancellation reasons; callers never select their own reason."""
    CALLER_REQUEST = "caller_request"
    ENGINE_SHUTDOWN = "engine_shutdown"
    DEPENDENCY_FAILURE = "dependency_failure"
    ADMINISTRATIVE_REQUEST = "administrative_request"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"

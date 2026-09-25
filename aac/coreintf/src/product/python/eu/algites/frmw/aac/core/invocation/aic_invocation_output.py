from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar

@dataclass(frozen=True, slots=True)
class AIcInvocationOutput:
    success: bool
    result: object | None = None
    error: Mapping[str, object] | None = None

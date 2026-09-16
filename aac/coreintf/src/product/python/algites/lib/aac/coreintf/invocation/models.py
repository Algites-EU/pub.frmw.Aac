from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AIcInvocationInput:
    invocation_id: str
    parent_invocation_id: str | None
    capability_id: str
    capability_version: int
    operation_id: str
    provider_instance_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    consumer_instance_id: str | None = None
    requirement_id: str | None = None


@dataclass(frozen=True, slots=True)
class AIcInvocationOutput:
    success: bool
    result: object | None = None
    error: Mapping[str, object] | None = None

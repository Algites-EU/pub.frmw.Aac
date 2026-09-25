from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar


@dataclass(frozen=True, slots=True)
class AIcInvocationInput:
    invocation_id: str
    parent_invocation_id: str | None
    capability_id: str
    capability_version: int
    operation_id: str
    provider_instance_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    operation_parameter_overrides: Mapping[str, object] = field(default_factory=dict)
    effective_operation_parameters: Mapping[str, object] = field(default_factory=dict)
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class AIcInvocationOutput:
    success: bool
    result: object | None = None
    error: Mapping[str, object] | None = None


class AInOperationCompletionState(str, Enum):
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"


AIcOperationSuccessT = TypeVar("AIcOperationSuccessT")
AIcOperationCancelledT = TypeVar("AIcOperationCancelledT")


@dataclass(frozen=True, slots=True)
class AIcOperationCompletion(Generic[AIcOperationSuccessT, AIcOperationCancelledT]):
    state: AInOperationCompletionState
    success_result: AIcOperationSuccessT | None = None
    cancelled_result: AIcOperationCancelledT | None = None

    def __post_init__(self) -> None:
        if self.state is AInOperationCompletionState.SUCCESS and self.cancelled_result is not None:
            raise ValueError("SUCCESS operation completion cannot contain cancelled_result")
        if self.state is AInOperationCompletionState.CANCELLED and self.success_result is not None:
            raise ValueError("CANCELLED operation completion cannot contain success_result")

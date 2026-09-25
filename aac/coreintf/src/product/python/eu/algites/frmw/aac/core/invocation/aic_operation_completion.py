from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar

from .ain_operation_completion_state import AInOperationCompletionState

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

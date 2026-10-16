from __future__ import annotations
from abc import ABC, abstractmethod
from .ain_operation_execution_state import AInOperationExecutionState


class AIiOperationInteractionCoreControl(ABC):
    """Private Core-owned lifecycle operations; not granted to callers/providers."""

    @abstractmethod
    def core_transition(self, state: AInOperationExecutionState, *,
                        state_result: object = None, has_state_result: bool = False) -> None: ...

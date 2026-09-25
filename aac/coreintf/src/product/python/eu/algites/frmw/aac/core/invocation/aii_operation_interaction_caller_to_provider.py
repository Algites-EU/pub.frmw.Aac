from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage
from .aii_operation_failure_exception_factory import AIiOperationFailureExceptionFactory
from .aii_operation_interaction_provider_to_caller import AIiOperationInteractionProviderToCaller
from .ain_operation_execution_state import AInOperationExecutionState
from .ain_operation_interaction_detail_level import AInOperationInteractionDetailLevel
from .ain_operation_interaction_failure_detail_level import AInOperationInteractionFailureDetailLevel
from .ain_operation_interaction_mode import AInOperationInteractionMode
from .aix_capability_operation_failed import AIxCapabilityOperationFailed

AIxOperationFailureT = TypeVar("AIxOperationFailureT", bound=AIxCapabilityOperationFailed)

class AIiOperationInteractionCallerToProvider(AIiOperationInteractionProviderToCaller, Generic[AIxOperationFailureT], ABC):
    """Caller-facing controller for an interactive or asynchronous capability invocation."""

    @abstractmethod
    def set_exception_factory(
        self, factory: AIiOperationFailureExceptionFactory[AIxOperationFailureT] | None
    ) -> None: ...

    @abstractmethod
    def exception_factory(self) -> AIiOperationFailureExceptionFactory[AIxOperationFailureT] | None: ...

    @abstractmethod
    def provider_snapshot(self) -> AIcOperationInteractionProviderToCallerMessage: ...

    @abstractmethod
    def request_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def set_interaction_mode(self, mode: AInOperationInteractionMode) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def set_detail_level(self, level: AInOperationInteractionDetailLevel) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def set_reporting_interval_ms(self, value: int | None) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def set_failure_detail_level(
        self, level: AInOperationInteractionFailureDetailLevel
    ) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def set_state_result_delivery_mode(
        self, mode: AInStateResultDeliveryMode
    ) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def request_state_result(self) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def accept_state_result_revision(self, revision: int) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def wait_for_terminal_state(self, timeout: float | None = None) -> AIcOperationInteractionProviderToCallerMessage: ...

    @abstractmethod
    def core_transition(
        self,
        state: AInOperationExecutionState,
        *,
        state_result: object = None,
        has_state_result: bool = False,
    ) -> None:
        """Apply a Core-owned lifecycle transition atomically with its optional terminal state result."""

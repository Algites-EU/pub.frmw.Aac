from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from datetime import datetime
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage
from .aii_operation_failure_exception_factory import AIiOperationFailureExceptionFactory
from .ain_operation_execution_state import AInOperationExecutionState
from .ain_operation_interaction_detail_level import AInOperationInteractionDetailLevel
from .ain_operation_interaction_failure_detail_level import AInOperationInteractionFailureDetailLevel
from .ain_operation_interaction_mode import AInOperationInteractionMode
from .aix_capability_operation_failed import AIxCapabilityOperationFailed

AIxOperationFailureT = TypeVar("AIxOperationFailureT", bound=AIxCapabilityOperationFailed)

C2PM = TypeVar("C2PM", bound=AIcOperationInteractionCallerToProviderMessage)


class AIiOperationInteractionCallerToProviderOnCaller(Generic[AIxOperationFailureT, C2PM], ABC):
    """Caller endpoint: change AAC interaction preferences and publish full C2P messages.

    Each C2P message represents one immutable, revisioned caller state.
    The transport decides when and how to deliver it to the provider endpoint.
    """

    @abstractmethod
    def send_message(self, message: C2PM) -> None: ...

    @abstractmethod
    def set_exception_factory(
        self, factory: AIiOperationFailureExceptionFactory[AIxOperationFailureT] | None
    ) -> None: ...

    @abstractmethod
    def exception_factory(self) -> AIiOperationFailureExceptionFactory[AIxOperationFailureT] | None: ...

    @abstractmethod
    def provider_snapshot(self) -> AIcOperationInteractionProviderToCallerMessage: ...

    @abstractmethod
    def schedule_cancellation(self, deadline: datetime, *, message: object | None = None,
                              origin: str | None = None) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def cancel_now(self, *, message: object | None = None,
                   origin: str | None = None) -> AIcOperationInteractionCallerToProviderMessage: ...

    @abstractmethod
    def withdraw_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage: ...

    def request_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage:
        """Backward-compatible spelling for immediate caller cancellation."""
        return self.cancel_now()


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


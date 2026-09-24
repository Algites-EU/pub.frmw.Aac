from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar

from ..presentation import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode


class AInOperationExecutionState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AInOperationInteractionEventType(str, Enum):
    STATUS = "STATUS"
    PROGRESS = "PROGRESS"
    DETAIL = "DETAIL"
    DIAGNOSTIC = "DIAGNOSTIC"


class AInOperationInteractionSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AInOperationInteractionMode(str, Enum):
    FOREGROUND = "FOREGROUND"
    BACKGROUND = "BACKGROUND"


class AInOperationInteractionDetailLevel(str, Enum):
    SUMMARY = "SUMMARY"
    DETAILED = "DETAILED"


class AInOperationInteractionFailureDetailLevel(str, Enum):
    BASIC = "BASIC"
    STACK_TRACE = "STACK_TRACE"


@dataclass(frozen=True, slots=True)
class AIcOperationInteractionEvent:
    event_type: AInOperationInteractionEventType
    progress_id: str | None = None
    parent_progress_id: str | None = None
    phase_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    current: int | float | None = None
    total: int | float | None = None
    unit: str | None = None
    severity: AInOperationInteractionSeverity = AInOperationInteractionSeverity.INFO
    code: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type is AInOperationInteractionEventType.PROGRESS and not self.progress_id:
            raise ValueError("PROGRESS interaction event requires progress_id")
        if self.progress_id is not None and not self.progress_id:
            raise ValueError("operation interaction progress_id must not be empty")
        if self.parent_progress_id is not None and not self.parent_progress_id:
            raise ValueError("operation interaction parent_progress_id must not be empty")
        if self.parent_progress_id is not None and self.parent_progress_id == self.progress_id:
            raise ValueError("operation interaction progress cannot be its own parent")
        if self.phase_id is not None and not self.phase_id:
            raise ValueError("operation interaction phase_id must not be empty")
        if self.unit is not None and not self.unit:
            raise ValueError("operation interaction unit must not be empty")
        if self.code is not None and not self.code:
            raise ValueError("operation interaction code must not be empty")
        if self.total is not None and self.total < 0:
            raise ValueError("operation interaction total must be non-negative")
        if self.current is not None and self.current < 0:
            raise ValueError("operation interaction current must be non-negative")


@dataclass(frozen=True, slots=True)
class AIcOperationInteractionFeatures:
    progress_reporting: bool = False
    cancellation: bool = False
    detail_level: bool = False
    reporting_interval: bool = False
    supported_state_result_delivery_modes: tuple[AInStateResultDeliveryMode, ...] = (
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
    )

    def __post_init__(self) -> None:
        if not self.supported_state_result_delivery_modes:
            raise ValueError("operation interaction must support at least one state-result delivery mode")
        if len(self.supported_state_result_delivery_modes) != len(set(self.supported_state_result_delivery_modes)):
            raise ValueError("supported state-result delivery modes must be unique")
        if AInStateResultDeliveryMode.ON_DEMAND_COMPLETE not in self.supported_state_result_delivery_modes:
            raise ValueError("every operation interaction must support ON_DEMAND_COMPLETE")


@dataclass(frozen=True, slots=True)
class AIcOperationInteractionProviderToCallerMessage:
    interaction_revision: int = 0
    execution_state: AInOperationExecutionState = AInOperationExecutionState.PENDING
    state_result_revision: int = 0
    state_result_payload_revision: int | None = None
    state_result: object | None = None
    events: tuple[AIcOperationInteractionEvent, ...] = ()
    features: AIcOperationInteractionFeatures = AIcOperationInteractionFeatures()

    def __post_init__(self) -> None:
        if self.interaction_revision < 0:
            raise ValueError("interaction_revision must be non-negative")
        if self.state_result_revision < 0:
            raise ValueError("state_result_revision must be non-negative")
        if self.state_result_payload_revision is not None:
            if self.state_result_payload_revision < 1:
                raise ValueError("state_result_payload_revision must be >= 1 when present")
            if self.state_result_payload_revision > self.state_result_revision:
                raise ValueError("state_result_payload_revision cannot exceed state_result_revision")

    @property
    def state_result_included(self) -> bool:
        return self.state_result_payload_revision is not None


@dataclass(frozen=True, slots=True)
class AIcOperationInteractionCallerToProviderMessage:
    last_accepted_state_result_revision: int = 0
    interaction_mode: AInOperationInteractionMode = AInOperationInteractionMode.FOREGROUND
    cancellation_requested: bool = False
    detail_level: AInOperationInteractionDetailLevel = AInOperationInteractionDetailLevel.SUMMARY
    reporting_interval_ms: int | None = None
    failure_detail_level: AInOperationInteractionFailureDetailLevel = AInOperationInteractionFailureDetailLevel.BASIC
    state_result_delivery_mode: AInStateResultDeliveryMode = AInStateResultDeliveryMode.ON_DEMAND_COMPLETE
    state_result_request_id: int = 0

    def __post_init__(self) -> None:
        if self.last_accepted_state_result_revision < 0:
            raise ValueError("last_accepted_state_result_revision must be non-negative")
        if self.reporting_interval_ms is not None and self.reporting_interval_ms < 0:
            raise ValueError("reporting_interval_ms must be non-negative")
        if self.state_result_request_id < 0:
            raise ValueError("state_result_request_id must be non-negative")


@dataclass(frozen=True, slots=True)
class AIcOperationFailure:
    system_message: str
    exception_type: str
    user_message: AIcDisplayText | None = None
    error_code: str | None = None
    stack_trace: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)
    extension: object | None = None

    def __post_init__(self) -> None:
        if not self.system_message:
            raise ValueError("operation failure system_message must not be empty")
        if not self.exception_type:
            raise ValueError("operation failure exception_type must not be empty")
        if self.error_code is not None and not self.error_code:
            raise ValueError("operation failure error_code must not be empty")


class AIxCapabilityOperationFailed(RuntimeError):
    """Caller-side AAC exception representing a FAILED capability-operation execution."""

    def __init__(self, failure: AIcOperationFailure) -> None:
        super().__init__(failure.system_message)
        self.failure = failure
        self.additional_data = failure.extension


AIxOperationFailureT = TypeVar("AIxOperationFailureT", bound=AIxCapabilityOperationFailed)


class AIiOperationFailureExceptionFactory(Generic[AIxOperationFailureT], ABC):
    @abstractmethod
    def create(self, failure: AIcOperationFailure) -> AIxOperationFailureT: ...


class AIcCallableOperationFailureExceptionFactory(AIiOperationFailureExceptionFactory[AIxOperationFailureT]):
    def __init__(self, factory: Callable[[AIcOperationFailure], AIxOperationFailureT]) -> None:
        self._factory = factory

    def create(self, failure: AIcOperationFailure) -> AIxOperationFailureT:
        result = self._factory(failure)
        if not isinstance(result, AIxCapabilityOperationFailed):
            raise TypeError("operation failure exception factory must return AIxCapabilityOperationFailed")
        return result


class AIxOperationCancelled(RuntimeError):
    """Raised by a cooperative provider after observing cancellation_requested."""

    def __init__(
        self,
        message: str = "operation cancelled",
        *,
        state_result: object = None,
        has_state_result: bool = False,
    ) -> None:
        super().__init__(message)
        self.state_result = state_result
        self.has_state_result = has_state_result


class AIiOperationInteractionProviderToCaller(ABC):
    """Provider-facing half of one bidirectional, UI-neutral operation interaction."""

    @abstractmethod
    def declare_features(self, features: AIcOperationInteractionFeatures) -> None: ...

    @abstractmethod
    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None: ...

    def report(self, event: AIcOperationInteractionEvent) -> None:
        self.report_events((event,))

    @abstractmethod
    def state_result_changed(self) -> int:
        """Publish a new logical result revision without attaching its payload."""

    @abstractmethod
    def update_state_result(self, state_result: object) -> int:
        """Publish a new immutable result revision, attaching payload when the selected delivery mode requires it."""

    @abstractmethod
    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        """Deliver an existing result revision without creating another logical result revision."""

    @abstractmethod
    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage: ...


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


class AIcNullOperationInteraction(AIiOperationInteractionProviderToCaller):
    """No-op interaction used by simple synchronous invocations without a caller callback."""

    def __init__(self) -> None:
        self._state_result_revision = 0
        self._caller = AIcOperationInteractionCallerToProviderMessage(
            state_result_delivery_mode=AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        )

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        return None

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        return None

    def state_result_changed(self) -> int:
        self._state_result_revision += 1
        return self._state_result_revision

    def update_state_result(self, state_result: object) -> int:
        self._state_result_revision += 1
        return self._state_result_revision

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        return None

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        return self._caller

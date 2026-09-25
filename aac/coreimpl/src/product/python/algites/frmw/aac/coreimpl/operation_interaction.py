from __future__ import annotations

import copy
from dataclasses import replace
from threading import Condition, RLock
from typing import Callable

from algites.frmw.aac.coreintf.invocation import (
    AInOperationExecutionState,
    AInOperationInteractionDetailLevel,
    AInOperationInteractionFailureDetailLevel,
    AInOperationInteractionMode,
    AInStateResultDeliveryMode,
    AIcOperationInteractionCallerToProviderMessage,
    AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures,
    AIcOperationInteractionProviderToCallerMessage,
    AIiOperationInteractionCallerToProvider,
    AIiOperationFailureExceptionFactory,
    AIxCapabilityOperationFailed,
)


class AIcOperationInteractionController(AIiOperationInteractionCallerToProvider):
    """Thread-safe caller controller and provider interaction endpoint for one invocation."""

    def __init__(
        self,
        listener: Callable[[AIcOperationInteractionProviderToCallerMessage], None] | None = None,
        *,
        caller_state: AIcOperationInteractionCallerToProviderMessage | None = None,
    ) -> None:
        self._listener = listener
        self._exception_factory: AIiOperationFailureExceptionFactory | None = None
        self._caller_state = caller_state or AIcOperationInteractionCallerToProviderMessage()
        self._features = AIcOperationInteractionFeatures()
        self._features_declared = False
        self._execution_state = AInOperationExecutionState.PENDING
        self._interaction_revision = 0
        self._state_result_revision = 0
        self._last_message = AIcOperationInteractionProviderToCallerMessage()
        self._terminal_state_result: object | None = None
        self._terminal_state_result_revision: int | None = None
        self._always_complete_state_result: object | None = None
        self._always_complete_state_result_revision: int | None = None
        self._lock = RLock()
        self._condition = Condition(self._lock)

    def set_exception_factory(self, factory: AIiOperationFailureExceptionFactory | None) -> None:
        with self._lock:
            self._exception_factory = factory

    def exception_factory(self) -> AIiOperationFailureExceptionFactory | None:
        with self._lock:
            return self._exception_factory

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        with self._lock:
            selected_mode = self._caller_state.state_result_delivery_mode
            if selected_mode not in features.supported_state_result_delivery_modes:
                raise ValueError(
                    f"current state-result delivery mode {selected_mode.value} is not supported by declared features"
                )
            self._features = features
            self._features_declared = True
            self._publish_locked()

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        if not events:
            return
        with self._lock:
            self._publish_locked(events=tuple(events))

    def state_result_changed(self) -> int:
        with self._lock:
            mode = self._caller_state.state_result_delivery_mode
            if mode in (
                AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
                AInStateResultDeliveryMode.ON_CHANGE_DELTA,
                AInStateResultDeliveryMode.ALWAYS_COMPLETE,
            ):
                raise ValueError(
                    f"state-result delivery mode {mode.value} requires update_state_result() with a payload"
                )
            self._state_result_revision += 1
            self._publish_locked()
            return self._state_result_revision

    def update_state_result(self, state_result: object) -> int:
        immutable_snapshot = copy.deepcopy(state_result)
        with self._lock:
            self._state_result_revision += 1
            revision = self._state_result_revision
            mode = self._caller_state.state_result_delivery_mode
            payload_revision = None
            payload = None
            if mode in (
                AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
                AInStateResultDeliveryMode.ON_CHANGE_DELTA,
                AInStateResultDeliveryMode.ALWAYS_COMPLETE,
            ):
                payload_revision = revision
                payload = immutable_snapshot
            if mode is AInStateResultDeliveryMode.ALWAYS_COMPLETE:
                self._always_complete_state_result_revision = revision
                self._always_complete_state_result = immutable_snapshot
            self._publish_locked(
                state_result_payload_revision=payload_revision,
                state_result=copy.deepcopy(payload),
            )
            return revision

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        immutable_snapshot = copy.deepcopy(state_result)
        with self._lock:
            effective_revision = self._state_result_revision if revision is None else revision
            if effective_revision < 1 or effective_revision > self._state_result_revision:
                raise ValueError("delivered state-result revision must reference an existing result revision")
            if self._caller_state.state_result_delivery_mode is AInStateResultDeliveryMode.ALWAYS_COMPLETE:
                if effective_revision != self._state_result_revision:
                    raise ValueError("ALWAYS_COMPLETE can deliver only the current complete state-result revision")
                self._always_complete_state_result_revision = effective_revision
                self._always_complete_state_result = immutable_snapshot
            self._publish_locked(
                state_result_payload_revision=effective_revision,
                state_result=immutable_snapshot,
            )

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            return self._caller_state

    def provider_snapshot(self) -> AIcOperationInteractionProviderToCallerMessage:
        with self._lock:
            if self._terminal_state_result_revision is not None:
                return replace(
                    self._last_message,
                    state_result_payload_revision=self._terminal_state_result_revision,
                    state_result=copy.deepcopy(self._terminal_state_result),
                    events=(),
                )
            return replace(self._last_message, events=(), state_result=copy.deepcopy(self._last_message.state_result))

    def request_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if not self._features.cancellation:
                raise ValueError("operation does not declare cancellation support")
            self._caller_state = replace(self._caller_state, cancellation_requested=True)
            return self._caller_state

    def set_interaction_mode(self, mode: AInOperationInteractionMode) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            self._caller_state = replace(self._caller_state, interaction_mode=mode)
            return self._caller_state

    def set_detail_level(self, level: AInOperationInteractionDetailLevel) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if not self._features.detail_level:
                raise ValueError("operation does not declare adjustable detail-level support")
            self._caller_state = replace(self._caller_state, detail_level=level)
            return self._caller_state

    def set_reporting_interval_ms(self, value: int | None) -> AIcOperationInteractionCallerToProviderMessage:
        if value is not None and value < 0:
            raise ValueError("reporting_interval_ms must be non-negative")
        with self._lock:
            if not self._features.reporting_interval:
                raise ValueError("operation does not declare adjustable reporting-interval support")
            self._caller_state = replace(self._caller_state, reporting_interval_ms=value)
            return self._caller_state

    def set_failure_detail_level(
        self, level: AInOperationInteractionFailureDetailLevel
    ) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            self._caller_state = replace(self._caller_state, failure_detail_level=level)
            return self._caller_state

    def set_state_result_delivery_mode(
        self, mode: AInStateResultDeliveryMode
    ) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if self._features_declared and mode not in self._features.supported_state_result_delivery_modes:
                raise ValueError(f"operation does not support state-result delivery mode {mode.value}")
            self._caller_state = replace(self._caller_state, state_result_delivery_mode=mode)
            return self._caller_state

    def request_state_result(self) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            self._caller_state = replace(
                self._caller_state,
                state_result_request_id=self._caller_state.state_result_request_id + 1,
            )
            return self._caller_state

    def accept_state_result_revision(self, revision: int) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if revision < self._caller_state.last_accepted_state_result_revision:
                raise ValueError("last accepted state-result revision cannot move backwards")
            if revision > self._state_result_revision:
                raise ValueError("cannot accept a state-result revision that has not been published")
            self._caller_state = replace(self._caller_state, last_accepted_state_result_revision=revision)
            return self._caller_state

    def wait_for_terminal_state(self, timeout: float | None = None) -> AIcOperationInteractionProviderToCallerMessage:
        with self._condition:
            completed = self._condition.wait_for(
                lambda: self._execution_state in (
                    AInOperationExecutionState.COMPLETED,
                    AInOperationExecutionState.FAILED,
                    AInOperationExecutionState.CANCELLED,
                ),
                timeout=timeout,
            )
            if not completed:
                raise TimeoutError("operation did not reach a terminal state before timeout")
            return self.provider_snapshot()

    def core_transition(self, state: AInOperationExecutionState, *, state_result: object = None, has_state_result: bool = False) -> None:
        with self._lock:
            self._validate_transition_locked(state)
            payload_revision = None
            payload = None
            if has_state_result:
                immutable_snapshot = copy.deepcopy(state_result)
                self._state_result_revision += 1
                self._terminal_state_result_revision = self._state_result_revision if state in (
                    AInOperationExecutionState.COMPLETED,
                    AInOperationExecutionState.FAILED,
                    AInOperationExecutionState.CANCELLED,
                ) else None
                if self._terminal_state_result_revision is not None:
                    self._terminal_state_result = immutable_snapshot
                if self._caller_state.state_result_delivery_mode in (
                    AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
                    AInStateResultDeliveryMode.ON_CHANGE_DELTA,
                    AInStateResultDeliveryMode.ALWAYS_COMPLETE,
                ):
                    payload_revision = self._state_result_revision
                    payload = immutable_snapshot
                if self._caller_state.state_result_delivery_mode is AInStateResultDeliveryMode.ALWAYS_COMPLETE:
                    self._always_complete_state_result_revision = self._state_result_revision
                    self._always_complete_state_result = immutable_snapshot
            self._execution_state = state
            self._publish_locked(
                state_result_payload_revision=payload_revision,
                state_result=copy.deepcopy(payload),
            )
            if state in (
                AInOperationExecutionState.COMPLETED,
                AInOperationExecutionState.FAILED,
                AInOperationExecutionState.CANCELLED,
            ):
                self._condition.notify_all()

    def _validate_transition_locked(self, state: AInOperationExecutionState) -> None:
        current = self._execution_state
        if current is state:
            return
        allowed = {
            AInOperationExecutionState.PENDING: {AInOperationExecutionState.RUNNING},
            AInOperationExecutionState.RUNNING: {
                AInOperationExecutionState.COMPLETED,
                AInOperationExecutionState.FAILED,
                AInOperationExecutionState.CANCELLED,
            },
            AInOperationExecutionState.COMPLETED: set(),
            AInOperationExecutionState.FAILED: set(),
            AInOperationExecutionState.CANCELLED: set(),
        }
        if state not in allowed[current]:
            raise ValueError(f"invalid operation execution transition {current.value} -> {state.value}")

    def _publish_locked(
        self,
        *,
        events: tuple[AIcOperationInteractionEvent, ...] = (),
        state_result_payload_revision: int | None = None,
        state_result: object | None = None,
    ) -> None:
        if (
            state_result_payload_revision is None
            and self._caller_state.state_result_delivery_mode is AInStateResultDeliveryMode.ALWAYS_COMPLETE
            and self._always_complete_state_result_revision is not None
        ):
            state_result_payload_revision = self._always_complete_state_result_revision
            state_result = copy.deepcopy(self._always_complete_state_result)
        self._interaction_revision += 1
        message = AIcOperationInteractionProviderToCallerMessage(
            interaction_revision=self._interaction_revision,
            execution_state=self._execution_state,
            state_result_revision=self._state_result_revision,
            state_result_payload_revision=state_result_payload_revision,
            state_result=state_result,
            events=events,
            features=self._features,
        )
        self._last_message = message
        listener = self._listener
        if listener is not None:
            try:
                listener(copy.deepcopy(message))
            except Exception:
                return None

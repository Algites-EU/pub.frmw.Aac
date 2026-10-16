from __future__ import annotations
import copy
from datetime import datetime, timezone
from dataclasses import replace
from threading import Condition, RLock
from typing import Callable
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationExecutionState,
    AInOperationCancellationReason,
    AIcOperationCancellationReasonRecord,
    AIcOperationCancellationAcceptance,
    AIcOperationInteractionDeliveryBuffer,
    accept_cancellation_locally,
    AIiOperationInteractionCallerToProviderOnProvider,
    AIiOperationInteractionCoreControl,
    AIiOperationInteractionProviderToCallerOnProvider,
    AIiOperationInteractionProviderToCallerOnCaller,
    AInOperationInteractionDetailLevel,
    AInOperationInteractionFailureDetailLevel,
    AInOperationInteractionMode,
    AInStateResultDeliveryMode,
    AIcOperationInteractionCallerToProviderMessage,
    AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures,
    AIcOperationInteractionProviderToCallerMessage,
    AIiOperationInteractionCallerToProviderOnCaller,
    AIiOperationFailureExceptionFactory,
    AIxCapabilityOperationFailed,
)

class AIcOperationInteractionController(AIiOperationInteractionCallerToProviderOnCaller, AIiOperationInteractionCallerToProviderOnProvider, AIiOperationInteractionProviderToCallerOnProvider, AIiOperationInteractionProviderToCallerOnCaller, AIiOperationInteractionCoreControl):
    """Thread-safe caller controller and provider interaction endpoint for one invocation."""

    def __init__(
        self,
        listener: Callable[[tuple[AIcOperationInteractionProviderToCallerMessage, ...]], None] | None = None,
        *,
        delivery_buffer: AIcOperationInteractionDeliveryBuffer | None = None,
        caller_state: AIcOperationInteractionCallerToProviderMessage | None = None,
    ) -> None:
        self._listener = listener
        self._delivery_buffer = delivery_buffer
        self._exception_factory: AIiOperationFailureExceptionFactory | None = None
        self._caller_state = caller_state or AIcOperationInteractionCallerToProviderMessage()
        self._features = AIcOperationInteractionFeatures()
        self._features_declared = False
        self._execution_state = AInOperationExecutionState.PENDING
        self._interaction_revision = 0
        self._state_result_revision = 0
        self._last_message = AIcOperationInteractionProviderToCallerMessage()
        self._cancellation_acceptance: AIcOperationCancellationAcceptance | None = None
        self._terminal_state_result: object | None = None
        self._terminal_state_result_revision: int | None = None
        self._always_complete_state_result: object | None = None
        self._always_complete_state_result_revision: int | None = None
        self._lock = RLock()
        self._condition = Condition(self._lock)

    def send_message(self, message: AIcOperationInteractionCallerToProviderMessage | AIcOperationInteractionProviderToCallerMessage) -> None:
        """Explicit message publication on the corresponding endpoint.

        In-process controller implements both directional endpoints. In a remote
        deployment distinct bound endpoint adapters separate the two call sites.
        """
        if isinstance(message, AIcOperationInteractionCallerToProviderMessage):
            self.receive_message(message)
        elif isinstance(message, AIcOperationInteractionProviderToCallerMessage):
            with self._lock:
                self._interaction_revision += 1
                publication = replace(message, interaction_revision=self._interaction_revision,
                    published_at=datetime.now(timezone.utc))
                self._last_message = publication
                if self._delivery_buffer is not None:
                    self._delivery_buffer.enqueue(publication)
                if self._listener is not None:
                    try:
                        self._listener((copy.deepcopy(publication),))
                    except Exception:
                        pass
        else:
            raise TypeError("unsupported interaction message type")

    def receive_message(self, message: AIcOperationInteractionCallerToProviderMessage) -> AIcOperationInteractionProviderToCallerMessage | None:
        """Accept latest delivered C2P state; stale or duplicated revisions have no effect.

        No implicit response: a concrete provider can override this method and
        return one P2C message, which its transport appends after queued ones.
        """
        if not isinstance(message, AIcOperationInteractionCallerToProviderMessage):
            raise TypeError("expected caller-to-provider message")
        with self._lock:
            if message.caller_interaction_revision <= self._caller_state.caller_interaction_revision:
                return None
            if self._cancellation_acceptance is not None:
                message = replace(message, cancellation_schedule=self._caller_state.cancellation_schedule)
            self._caller_state = message
        return None

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

    def accept_cancellation(self, reasons: frozenset[str]) -> AIcOperationCancellationAcceptance:
        """Provider-local acceptance; no caller/controller round-trip in this path."""
        with self._lock:
            if self._cancellation_acceptance is not None:
                return self._cancellation_acceptance
            acceptance = accept_cancellation_locally(self._caller_state, reasons)
            self._cancellation_acceptance = acceptance
            self._publish_locked()
            return acceptance

    def record_cancellation_acceptance(self, acceptance: AIcOperationCancellationAcceptance) -> None:
        """Ingest asynchronously reported evidence from an isolated provider."""
        with self._lock:
            if self._cancellation_acceptance is None:
                self._cancellation_acceptance = acceptance
                self._publish_locked()
            elif self._cancellation_acceptance != acceptance:
                raise ValueError("cancellation was already accepted using another snapshot")

    def _change_caller_state_locked(self, **changes) -> AIcOperationInteractionCallerToProviderMessage:
        self._caller_state = replace(
            self._caller_state,
            caller_interaction_revision=self._caller_state.caller_interaction_revision + 1,
            **changes,
        )
        return self._caller_state

    def receive_messages(self, messages: tuple[AIcOperationInteractionProviderToCallerMessage, ...]) -> None:
        """Caller-side batch entrypoint: process EVERY publication before notifying host once."""
        if not messages:
            return
        copied = copy.deepcopy(tuple(messages))
        with self._lock:
            last_revision = self._last_message.interaction_revision
            for message in copied:
                if message.interaction_revision <= last_revision:
                    raise ValueError("stale or out-of-order provider-to-caller interaction revision")
                last_revision = message.interaction_revision
            before = (self._last_message, self._interaction_revision, self._cancellation_acceptance)
            self._last_message = copied[-1]
            self._interaction_revision = last_revision
            if copied[-1].cancellation_acceptance is not None:
                self._cancellation_acceptance = copied[-1].cancellation_acceptance
            listener = self._listener
        if listener is not None:
            try:
                listener(copied)
            except BaseException:
                # The transport will redeliver the full unacknowledged batch.
                # Host-side effects must be idempotent by message revision.
                with self._lock:
                    if self._interaction_revision == last_revision:
                        self._last_message, self._interaction_revision, self._cancellation_acceptance = before
                raise

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

    def schedule_cancellation(
        self, deadline: datetime, *, message: AIcDisplayText | None = None,
        origin: str | None = None,
    ) -> AIcOperationInteractionCallerToProviderMessage:
        if not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset() is None:
            raise ValueError("cancellation deadline must be timezone-aware")
        with self._lock:
            if self._cancellation_acceptance is not None:
                return self._caller_state  # No effective changes after provider acceptance.
            if self._features_declared and not self._features.cancellation:
                raise ValueError("operation does not declare cancellation support")
            reason = AInOperationCancellationReason.CALLER_REQUEST.value
            now = datetime.now(timezone.utc)
            schedule = dict(self._caller_state.cancellation_schedule)
            previous = schedule.get(reason)
            schedule[reason] = AIcOperationCancellationReasonRecord(
                reason=reason, current_deadline=deadline,
                first_requested_at=previous.first_requested_at if previous else now,
                last_requested_at=now,
                request_count=(previous.request_count + 1 if previous else 1),
                last_message=message, last_origin=origin,
            )
            return self._change_caller_state_locked(cancellation_schedule=schedule)

    def cancel_now(self, *, message: AIcDisplayText | None = None,
                   origin: str | None = None) -> AIcOperationInteractionCallerToProviderMessage:
        return self.schedule_cancellation(datetime.now(timezone.utc), message=message, origin=origin)

    def request_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage:
        return self.cancel_now()

    def withdraw_cancellation(self) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if self._cancellation_acceptance is not None:
                return self._caller_state
            schedule = dict(self._caller_state.cancellation_schedule)
            reason = AInOperationCancellationReason.CALLER_REQUEST.value
            if reason not in schedule:
                return self._caller_state
            del schedule[reason]
            return self._change_caller_state_locked(cancellation_schedule=schedule)

    def schedule_framework_cancellation(
        self, reason: AInOperationCancellationReason, deadline: datetime, *,
        message: AIcDisplayText | None = None, origin: str | None = None,
    ) -> AIcOperationInteractionCallerToProviderMessage:
        """Core-only entrypoint; not exposed on the caller-facing interface."""
        if not isinstance(reason, AInOperationCancellationReason) or reason is AInOperationCancellationReason.CALLER_REQUEST:
            raise ValueError("use caller cancellation API for CALLER_REQUEST")
        if not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset() is None:
            raise ValueError("cancellation deadline must be timezone-aware")
        with self._lock:
            if self._cancellation_acceptance is not None:
                return self._caller_state
            now = datetime.now(timezone.utc)
            schedule = dict(self._caller_state.cancellation_schedule)
            previous = schedule.get(reason.value)
            schedule[reason.value] = AIcOperationCancellationReasonRecord(
                reason=reason.value, current_deadline=deadline,
                first_requested_at=previous.first_requested_at if previous else now,
                last_requested_at=now, request_count=(previous.request_count + 1 if previous else 1),
                last_message=message, last_origin=origin,
            )
            return self._change_caller_state_locked(cancellation_schedule=schedule)

    def withdraw_framework_cancellation(self, reason: AInOperationCancellationReason) -> AIcOperationInteractionCallerToProviderMessage:
        if not isinstance(reason, AInOperationCancellationReason) or reason is AInOperationCancellationReason.CALLER_REQUEST:
            raise ValueError("framework cancellation withdrawal requires framework-owned reason")
        with self._lock:
            if self._cancellation_acceptance is not None:
                return self._caller_state
            schedule = dict(self._caller_state.cancellation_schedule)
            if reason.value not in schedule:
                return self._caller_state
            del schedule[reason.value]
            return self._change_caller_state_locked(cancellation_schedule=schedule)

    def set_interaction_mode(self, mode: AInOperationInteractionMode) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            return self._change_caller_state_locked(interaction_mode=mode)

    def set_detail_level(self, level: AInOperationInteractionDetailLevel) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if not self._features.detail_level:
                raise ValueError("operation does not declare adjustable detail-level support")
            return self._change_caller_state_locked(detail_level=level)

    def set_reporting_interval_ms(self, value: int | None) -> AIcOperationInteractionCallerToProviderMessage:
        if value is not None and value < 0:
            raise ValueError("reporting_interval_ms must be non-negative")
        with self._lock:
            if not self._features.reporting_interval:
                raise ValueError("operation does not declare adjustable reporting-interval support")
            return self._change_caller_state_locked(reporting_interval_ms=value)

    def set_failure_detail_level(
        self, level: AInOperationInteractionFailureDetailLevel
    ) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            return self._change_caller_state_locked(failure_detail_level=level)

    def set_state_result_delivery_mode(
        self, mode: AInStateResultDeliveryMode
    ) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if self._features_declared and mode not in self._features.supported_state_result_delivery_modes:
                raise ValueError(f"operation does not support state-result delivery mode {mode.value}")
            return self._change_caller_state_locked(state_result_delivery_mode=mode)

    def request_state_result(self) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            return self._change_caller_state_locked(
                state_result_request_id=self._caller_state.state_result_request_id + 1,
            )

    def accept_state_result_revision(self, revision: int) -> AIcOperationInteractionCallerToProviderMessage:
        with self._lock:
            if revision < self._caller_state.last_accepted_state_result_revision:
                raise ValueError("last accepted state-result revision cannot move backwards")
            if revision > self._state_result_revision:
                raise ValueError("cannot accept a state-result revision that has not been published")
            return self._change_caller_state_locked(last_accepted_state_result_revision=revision)

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
            published_at=datetime.now(timezone.utc),
            cancellation_acceptance=self._cancellation_acceptance,
        )
        self._last_message = message
        if self._delivery_buffer is not None:
            self._delivery_buffer.enqueue(message)
        listener = self._listener
        if listener is not None:
            try:
                listener((copy.deepcopy(message),))
            except Exception:
                return None

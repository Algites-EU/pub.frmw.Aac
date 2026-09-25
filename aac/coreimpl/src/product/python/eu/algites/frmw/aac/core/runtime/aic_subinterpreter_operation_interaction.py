from __future__ import annotations
from dataclasses import asdict
from importlib import import_module
import queue
from typing import Mapping
from eu.algites.frmw.aac.core.invocation.api import (
    AIiCapabilityEndpoint,
    AIiOperationInteractionProviderToCaller,
    AIcInvocationInput,
    AIcInvocationOutput,
    AIcOperationInteractionCallerToProviderMessage,
    AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures,
    AIxOperationCancelled,
    current_operation_interaction,
    invocation_locale_context,
    operation_interaction_context,
    operation_parameter_context,
)
from eu.algites.frmw.aac.core.implementation.errors import AIxSubinterpreterUnavailableError

class AIcSubinterpreterOperationInteraction(AIiOperationInteractionProviderToCaller):
    """Provider-side proxy over cross-interpreter queues."""

    def __init__(self, provider_to_core, core_to_provider) -> None:
        self._provider_to_core = provider_to_core
        self._core_to_provider = core_to_provider
        self._next_request_id = 0

    def _request(self, kind: str, payload: object | None = None) -> object:
        self._next_request_id += 1
        request_id = self._next_request_id
        self._provider_to_core.put((kind, request_id, payload))
        while True:
            response_id, success, result = self._core_to_provider.get()
            if response_id != request_id:
                raise RuntimeError("subinterpreter operation interaction response order was violated")
            if not success:
                raise RuntimeError(str(result))
            return result

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        self._provider_to_core.put(("features", 0, features))

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        if events:
            self._provider_to_core.put(("events", 0, events))

    def state_result_changed(self) -> int:
        return int(self._request("state_result_changed"))

    def update_state_result(self, state_result: object) -> int:
        return int(self._request("update_state_result", state_result))

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        self._request("deliver_state_result", (revision, state_result))

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        result = self._request("caller_snapshot")
        if not isinstance(result, AIcOperationInteractionCallerToProviderMessage):
            raise TypeError("invalid subinterpreter caller interaction snapshot")
        return result

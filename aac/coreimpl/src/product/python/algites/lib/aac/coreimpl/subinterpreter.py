from __future__ import annotations

from dataclasses import asdict
from importlib import import_module
import queue
from typing import Mapping

from algites.lib.aac.coreintf.invocation import (
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

from .errors import AIxSubinterpreterUnavailableError


def subinterpreter_available() -> bool:
    try:
        from concurrent import interpreters  # type: ignore[attr-defined]
    except ImportError:
        return False
    return hasattr(interpreters, "create") and hasattr(interpreters, "create_queue")


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


def _invoke_entrypoint(entrypoint: str, payload: Mapping[str, object], provider_to_core, core_to_provider) -> None:
    module_name, sep, attr_name = entrypoint.partition(":")
    if not sep:
        provider_to_core.put(("final", 0, AIcInvocationOutput(False, error={
            "type": "ValueError", "message": "subinterpreter entrypoint must use 'module:function'"
        })))
        return
    interaction = AIcSubinterpreterOperationInteraction(provider_to_core, core_to_provider)
    try:
        target = getattr(import_module(module_name), attr_name)
        parameters = payload.get("effective_operation_parameters", {})
        if not isinstance(parameters, Mapping):
            raise TypeError("effective_operation_parameters must be an object")
        locale = str(payload["locale"]) if payload.get("locale") is not None else None
        with operation_parameter_context(parameters), operation_interaction_context(interaction), invocation_locale_context(locale):
            result = target(str(payload["operation_id"]), dict(payload.get("arguments", {})))
        provider_to_core.put(("final", 0, AIcInvocationOutput(True, result=result)))
    except AIxOperationCancelled as exc:
        provider_to_core.put(("final", 0, AIcInvocationOutput(False, error={
            "type": "OPERATION_CANCELLED",
            "message": str(exc) or "operation cancelled",
            "has_state_result": exc.has_state_result,
            "state_result": exc.state_result if exc.has_state_result else None,
        })))
    except Exception as exc:
        provider_to_core.put(("final", 0, AIcInvocationOutput(False, error={
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "message": str(exc) or type(exc).__name__,
        })))


class AIcSubinterpreterCapabilityEndpoint(AIiCapabilityEndpoint):
    """CPython 3.14+ capability endpoint using one private interpreter and live interaction queues."""

    def __init__(self, entrypoint: str) -> None:
        try:
            from concurrent import interpreters  # type: ignore[attr-defined]
        except ImportError as exc:
            raise AIxSubinterpreterUnavailableError(
                "CPython concurrent.interpreters is unavailable; Python 3.14+ is required"
            ) from exc
        if not hasattr(interpreters, "create_queue"):
            raise AIxSubinterpreterUnavailableError(
                "CPython concurrent.interpreters.create_queue is unavailable; Python 3.14+ is required"
            )
        self.entrypoint = entrypoint
        self._interpreters = interpreters
        self._interpreter = interpreters.create()

    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        interaction = current_operation_interaction()
        provider_to_core = self._interpreters.create_queue()
        core_to_provider = self._interpreters.create_queue()
        payload = asdict(invocation_input)
        worker = self._interpreter.call_in_thread(
            _invoke_entrypoint, self.entrypoint, payload, provider_to_core, core_to_provider
        )
        final_output: AIcInvocationOutput | None = None
        while final_output is None:
            try:
                kind, request_id, data = provider_to_core.get(timeout=0.05)
            except queue.Empty:
                if not worker.is_alive():
                    break
                continue
            try:
                if kind == "features":
                    interaction.declare_features(data)
                elif kind == "events":
                    interaction.report_events(tuple(data))
                elif kind == "state_result_changed":
                    core_to_provider.put((request_id, True, interaction.state_result_changed()))
                elif kind == "update_state_result":
                    core_to_provider.put((request_id, True, interaction.update_state_result(data)))
                elif kind == "deliver_state_result":
                    revision, state_result = data
                    interaction.deliver_state_result(state_result, revision=revision)
                    core_to_provider.put((request_id, True, None))
                elif kind == "caller_snapshot":
                    core_to_provider.put((request_id, True, interaction.caller_snapshot()))
                elif kind == "final":
                    if not isinstance(data, AIcInvocationOutput):
                        raise TypeError("subinterpreter returned an invalid invocation output")
                    final_output = data
                else:
                    raise ValueError(f"unknown subinterpreter operation interaction message {kind!r}")
            except Exception as exc:
                if request_id:
                    core_to_provider.put((request_id, False, f"{type(exc).__name__}: {exc}"))
                else:
                    final_output = AIcInvocationOutput(False, error={
                        "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                        "message": str(exc) or type(exc).__name__,
                    })
        worker.join()
        if final_output is None:
            return AIcInvocationOutput(False, error={
                "type": "SubinterpreterExecutionError",
                "message": "subinterpreter execution ended without returning an invocation result",
            })
        return final_output

    def close(self) -> None:
        interpreter = getattr(self, "_interpreter", None)
        if interpreter is not None:
            interpreter.close()
            self._interpreter = None

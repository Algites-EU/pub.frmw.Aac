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

from .aic_subinterpreter_operation_interaction import AIcSubinterpreterOperationInteraction
from .aic_subinterpreter_capability_endpoint import AIcSubinterpreterCapabilityEndpoint

def subinterpreter_available() -> bool:
    try:
        from concurrent import interpreters  # type: ignore[attr-defined]
    except ImportError:
        return False
    return hasattr(interpreters, "create") and hasattr(interpreters, "create_queue")

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

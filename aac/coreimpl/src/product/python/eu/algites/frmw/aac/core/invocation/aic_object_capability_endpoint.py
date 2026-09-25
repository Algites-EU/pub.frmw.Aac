from __future__ import annotations
import copy
import dataclasses
import inspect
import types
import traceback
import threading
from contextvars import ContextVar
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Mapping, Union, get_args, get_origin, get_type_hints
from uuid import uuid4
from eu.algites.frmw.aac.core.instances.api import AIcBinding
from eu.algites.frmw.aac.core.capability.api import AInCapabilityOperationInteractionKind
from eu.algites.frmw.aac.core.descriptor.api import AIcCapabilityProviderOperationDescriptor
from eu.algites.frmw.aac.core.authorization.api import AIcAuthorizationPrincipal, AIcAuthorizationRequest, AIiAuthorizationProvider
from eu.algites.frmw.aac.core.errors import AIxPermissionDenied
from eu.algites.frmw.aac.core.entitlement.api import (
    AInPermissionRetryDisposition, AIcEntitlementRemediationRequest, AIiEntitlementRemediator,
)
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationCompletionState, AInOperationExecutionState, AInOperationInteractionFailureDetailLevel, AInStateResultDeliveryMode,
    AIiCapabilityEndpoint, AIiCapabilityHandle, AIiOperationInteractionProviderToCaller, AIiOperationInteractionCallerToProvider,
    AIcInvocationInput, AIcInvocationOutput, AIcNullOperationInteraction, AIcOperationCompletion, AIcOperationFailure, AIcOperationInteractionFeatures,
    AIiOperationFailureExceptionFactory, AIxCapabilityOperationFailed, AIxOperationCancelled,
    current_invocation_locale, current_operation_interaction, invocation_locale_context,
    operation_interaction_context, operation_parameter_context,
)
from eu.algites.frmw.aac.core.observation.api import AIcObservationInput, AInObservationOutcome, AInObservationPhase
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController
from eu.algites.frmw.aac.core.observation.dispatcher import AIcObservationDispatcher
from eu.algites.frmw.aac.core.implementation.errors import AIxSchemaValidationError
from eu.algites.frmw.aac.core.authorization.implementation import AIcComponentAuthorizationGrantStore

def _generated_capability_invoker(provider: object, capability_id: str, capability_version: int):
    """Return the generated invoker owned by the exact capability interface in the provider MRO."""
    for candidate in type(provider).__mro__:
        namespace = candidate.__dict__
        if (
            namespace.get("__aac_capability_id__") == capability_id
            and namespace.get("__aac_capability_version__") == capability_version
        ):
            invoker = namespace.get("__aac_invoke__")
            if invoker is not None:
                return invoker
    return None

def _coerce_invocation_value(annotation: object | None, value: object) -> object:
    if annotation is None or annotation is inspect._empty or annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _coerce_invocation_value(candidate, value)
            except (TypeError, ValueError, KeyError):
                pass
        return value
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return annotation(value)
    if inspect.isclass(annotation) and dataclasses.is_dataclass(annotation):
        if not isinstance(value, Mapping):
            raise TypeError(f"cannot coerce {type(value).__name__} to dataclass {annotation.__name__}")
        hints = get_type_hints(annotation)
        return annotation(**{
            field.name: _coerce_invocation_value(hints.get(field.name), value.get(field.name))
            for field in dataclasses.fields(annotation)
        })
    if origin in (tuple, list) and isinstance(value, (tuple, list)):
        item_type = args[0] if args else None
        converted = [_coerce_invocation_value(item_type, item) for item in value]
        return tuple(converted) if origin is tuple else converted
    return value

def _invoke_versioned_method(method, arguments: Mapping[str, object]):
    """Invoke a hand-written versioned SPI method using request-object or keyword style."""
    parameters = tuple(inspect.signature(method).parameters.values())
    hints = get_type_hints(method)
    if len(parameters) == 1 and parameters[0].name not in arguments:
        parameter = parameters[0]
        annotation = hints.get(parameter.name)
        if parameter.name == "request" or (inspect.isclass(annotation) and dataclasses.is_dataclass(annotation)):
            return method(_coerce_invocation_value(annotation, dict(arguments)))
    return method(**dict(arguments))

def _exception_error(exc: Exception) -> dict[str, object]:
    if isinstance(exc, AIxCapabilityOperationFailed):
        failure = exc.failure
        error: dict[str, object] = {
            "type": failure.exception_type,
            "message": failure.system_message,
        }
        if failure.user_message is not None:
            error["user_message"] = dataclasses.asdict(failure.user_message)
        if failure.error_code is not None:
            error["error_code"] = failure.error_code
        if failure.stack_trace is not None:
            error["stack_trace"] = failure.stack_trace
        if failure.details:
            error["details"] = dict(failure.details)
        if failure.extension is not None:
            error["extension"] = copy.deepcopy(failure.extension)
        return error
    error: dict[str, object] = {
        "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
        "message": str(exc) or type(exc).__name__,
    }
    try:
        caller = current_operation_interaction().caller_snapshot()
        if caller.failure_detail_level is AInOperationInteractionFailureDetailLevel.STACK_TRACE:
            error["stack_trace"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        pass
    return error

class AIcObjectCapabilityEndpoint(AIiCapabilityEndpoint):
    """In-process Python profile adapter using operation id -> method name mapping."""

    def __init__(self, provider: object) -> None:
        self.provider = provider

    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        try:
            generated_invoke = _generated_capability_invoker(
                self.provider, invocation_input.capability_id, invocation_input.capability_version
            )
            if generated_invoke is not None:
                result = generated_invoke(self.provider, invocation_input.operation_id, dict(invocation_input.arguments))
            else:
                method = getattr(
                    self.provider,
                    f"{invocation_input.operation_id}_{invocation_input.capability_version}",
                )
                result = _invoke_versioned_method(method, dict(invocation_input.arguments))
            return AIcInvocationOutput(True, result=result)
        except AttributeError as exc:
            return AIcInvocationOutput(False, error=_exception_error(exc))
        except AIxOperationCancelled as exc:
            return AIcInvocationOutput(False, error={
                "type": "OPERATION_CANCELLED",
                "message": str(exc) or "operation cancelled",
                "has_state_result": exc.has_state_result,
                "state_result": exc.state_result if exc.has_state_result else None,
            })
        except AIxPermissionDenied as exc:
            return AIcInvocationOutput(False, error={
                "type": "PERMISSION_DENIED",
                "message": str(exc),
                "capability_id": exc.capability_id or invocation_input.capability_id,
                "capability_version": exc.capability_version or invocation_input.capability_version,
                "permission_id": exc.permission_id,
                "retry_disposition": exc.retry_disposition.value,
                "remediation_hint": exc.remediation_hint,
            })
        except Exception as exc:
            return AIcInvocationOutput(False, error=_exception_error(exc))

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

from .aic_validated_operation_interaction_provider_proxy import AIcValidatedOperationInteractionProviderProxy
from .aic_object_capability_endpoint import AIcObjectCapabilityEndpoint
from .aic_endpoint_registry import AIcEndpointRegistry
from .aic_invocation_dispatcher import AIcInvocationDispatcher
from .aic_core_capability_handle import AIcCoreCapabilityHandle
from .aic_capability_handle_factory import AIcCapabilityHandleFactory
from ._context import CURRENT_AUTHORIZATION_PRINCIPAL as _CURRENT_AUTHORIZATION_PRINCIPAL
from ._context import CURRENT_INVOCATION_ID as _CURRENT_INVOCATION_ID

@contextmanager
def authorization_principal_context(principal: AIcAuthorizationPrincipal | None):
    token = _CURRENT_AUTHORIZATION_PRINCIPAL.set(principal)
    try:
        yield
    finally:
        _CURRENT_AUTHORIZATION_PRINCIPAL.reset(token)

def _resolve_operation_interaction(explicit: AIiOperationInteractionProviderToCaller | None) -> AIiOperationInteractionProviderToCaller:
    if explicit is not None:
        return explicit
    inherited = current_operation_interaction()
    if isinstance(inherited, AIcNullOperationInteraction):
        return AIcNullOperationInteraction()
    return inherited

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

def _failure_from_output(output: AIcInvocationOutput) -> AIcOperationFailure:
    error = dict(output.error or {})
    system_message = str(error.pop("message", "operation failed"))
    exception_type = str(error.pop("type", "AAC.OperationFailure"))
    stack_trace = str(error.pop("stack_trace")) if error.get("stack_trace") is not None else None
    error.pop("stack_trace", None)
    error_code = str(error.pop("error_code")) if error.get("error_code") is not None else None
    error.pop("error_code", None)
    user_message_raw = error.pop("user_message", None)
    user_message = None
    if isinstance(user_message_raw, Mapping):
        from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
        user_message = normalize_display_text(user_message_raw)
    extension = error.pop("extension", None)
    explicit_details = error.pop("details", None)
    details = dict(explicit_details) if isinstance(explicit_details, Mapping) else {}
    details.update(error)
    return AIcOperationFailure(
        system_message=system_message,
        exception_type=exception_type,
        user_message=user_message,
        error_code=error_code,
        stack_trace=stack_trace,
        details=details,
        extension=extension,
    )

def invoke_handle_with_parent_context(
    handle: AIiCapabilityHandle,
    parent_invocation_id: str | None,
    operation_id: str,
    arguments: Mapping[str, object] | None = None,
    operation_parameters: Mapping[str, object] | None = None,
    operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
    locale: str | None = None,
) -> AIcInvocationOutput:
    """Invoke a Core handle while restoring causal context received over a runtime boundary."""
    token = _CURRENT_INVOCATION_ID.set(parent_invocation_id)
    try:
        with operation_interaction_context(operation_interaction or current_operation_interaction()), invocation_locale_context(locale):
            return handle.invoke(
                operation_id, arguments, operation_parameters=operation_parameters,
                operation_interaction=operation_interaction, locale=locale,
            )
    finally:
        _CURRENT_INVOCATION_ID.reset(token)

def _redact_mapping(value: Mapping[str, object], paths: tuple[str, ...]) -> Mapping[str, object]:
    result = copy.deepcopy(dict(value))
    for path in paths:
        _redact_path(result, path)
    return result

def _redact_value(value: object, paths: tuple[str, ...]) -> object:
    result = copy.deepcopy(value)
    if not isinstance(result, (dict, list)):
        return "<redacted>" if paths and ("$" in paths or "" in paths) else result
    for path in paths:
        _redact_path(result, path)
    return result

def _redact_path(root: object, path: str) -> None:
    normalized = path.strip().removeprefix("$.").removeprefix("$")
    if not normalized:
        if isinstance(root, dict):
            for key in list(root):
                root[key] = "<redacted>"
        return
    parts = [part for part in normalized.split(".") if part]
    current = root
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return
    if not parts:
        return
    last = parts[-1]
    if isinstance(current, dict) and last in current:
        current[last] = "<redacted>"

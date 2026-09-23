from __future__ import annotations

import copy
import dataclasses
import inspect
import types
from contextvars import ContextVar
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Mapping, Union, get_args, get_origin, get_type_hints
from uuid import uuid4

from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreintf.authorization import AIcAuthorizationPrincipal, AIcAuthorizationRequest, AIiAuthorizationProvider
from algites.lib.aac.coreintf.errors import AIxPermissionDenied
from algites.lib.aac.coreintf.entitlement import (
    AInPermissionRetryDisposition, AIcEntitlementRemediationRequest, AIiEntitlementRemediator,
)
from algites.lib.aac.coreintf.invocation import AIiCapabilityEndpoint, AIiCapabilityHandle, AIcInvocationInput, AIcInvocationOutput
from algites.lib.aac.coreintf.observation import AIcObservationInput, AInObservationOutcome, AInObservationPhase

from .contracts import AIcActiveContractCatalog
from .observation import AIcObservationDispatcher
from .errors import AIxSchemaValidationError
from .authorization import AIcComponentAuthorizationGrantStore

_CURRENT_INVOCATION_ID: ContextVar[str | None] = ContextVar("aac_current_invocation_id", default=None)
_CURRENT_AUTHORIZATION_PRINCIPAL: ContextVar[AIcAuthorizationPrincipal | None] = ContextVar("aac_current_authorization_principal", default=None)


@contextmanager
def authorization_principal_context(principal: AIcAuthorizationPrincipal | None):
    token = _CURRENT_AUTHORIZATION_PRINCIPAL.set(principal)
    try:
        yield
    finally:
        _CURRENT_AUTHORIZATION_PRINCIPAL.reset(token)




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
            return AIcInvocationOutput(False, error={"type": "AttributeError", "message": str(exc)})
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
            return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})


class AIcEndpointRegistry:
    def __init__(self) -> None:
        self._endpoints: dict[str, AIiCapabilityEndpoint] = {}

    def register(self, provider_instance_id: str, endpoint: AIiCapabilityEndpoint) -> None:
        self._endpoints[provider_instance_id] = endpoint

    def register_object(self, provider_instance_id: str, runtime: object) -> None:
        self.register(provider_instance_id, AIcObjectCapabilityEndpoint(runtime))

    def unregister(self, provider_instance_id: str) -> None:
        self._endpoints.pop(provider_instance_id, None)

    def get(self, provider_instance_id: str) -> AIiCapabilityEndpoint:
        return self._endpoints[provider_instance_id]


class AIcInvocationDispatcher:
    def __init__(
        self,
        contracts: AIcActiveContractCatalog,
        observations: AIcObservationDispatcher | None = None,
        component_authorizations: AIcComponentAuthorizationGrantStore | None = None,
        principal_authorization_provider: AIiAuthorizationProvider | None = None,
        *,
        entitlement_remediator: AIiEntitlementRemediator | None = None,
        entitlement_refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        self.contracts = contracts
        self.observations = observations
        self.component_authorizations = component_authorizations
        self.principal_authorization_provider = principal_authorization_provider
        self.entitlement_remediator = entitlement_remediator
        self.entitlement_refresh_callback = entitlement_refresh_callback

    def _authorization_denial(self, invocation_input: AIcInvocationInput, operation, message: str) -> AIcInvocationOutput:
        requirement = operation.authorization
        return AIcInvocationOutput(False, error={
            "type": "AUTHORIZATION_DENIED",
            "message": message,
            "capability_id": invocation_input.capability_id,
            "capability_version": invocation_input.capability_version,
            "operation_id": invocation_input.operation_id,
            "required_all_of": list(requirement.all_of if requirement is not None else ()),
            "required_any_of": list(requirement.any_of if requirement is not None else ()),
        })

    def _authorize(self, invocation_input: AIcInvocationInput, operation) -> AIcInvocationOutput | None:
        requirement = operation.authorization
        if requirement is None or (not requirement.all_of and not requirement.any_of):
            return None
        if invocation_input.consumer_instance_id is None or invocation_input.requirement_id is None:
            return self._authorization_denial(invocation_input, operation, "authorized operation requires a Core binding consumer identity")
        grant = None if self.component_authorizations is None else self.component_authorizations.get(
            invocation_input.consumer_instance_id, invocation_input.requirement_id
        )
        granted = set(() if grant is None else grant.permission_ids)
        if not requirement.is_satisfied_by(granted):
            return self._authorization_denial(invocation_input, operation, "component authorization grant does not satisfy the operation requirement")
        if self.principal_authorization_provider is None:
            return None
        principal = _CURRENT_AUTHORIZATION_PRINCIPAL.get()
        if principal is None:
            return self._authorization_denial(invocation_input, operation, "current principal is required for this application authorization policy")
        def allowed(permission_id: str) -> bool:
            decision = self.principal_authorization_provider.authorize(AIcAuthorizationRequest(
                action=permission_id,
                resource_type="CAPABILITY_OPERATION",
                resource_id=f"{invocation_input.capability_id}/{invocation_input.capability_version}/{invocation_input.operation_id}",
                principal=principal,
                context={
                    "consumer_instance_id": invocation_input.consumer_instance_id,
                    "requirement_id": invocation_input.requirement_id,
                    "provider_instance_id": invocation_input.provider_instance_id,
                    "capability_id": invocation_input.capability_id,
                    "capability_version": invocation_input.capability_version,
                    "operation_id": invocation_input.operation_id,
                },
            ))
            return decision.allowed
        if any(not allowed(permission) for permission in requirement.all_of):
            return self._authorization_denial(invocation_input, operation, "current principal lacks an all_of authorization permission")
        if requirement.any_of and not any(allowed(permission) for permission in requirement.any_of):
            return self._authorization_denial(invocation_input, operation, "current principal lacks every any_of authorization permission")
        return None

    def invoke(self, endpoint: AIiCapabilityEndpoint, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        operation = self.contracts.operation(
            invocation_input.capability_id,
            invocation_input.capability_version,
            invocation_input.operation_id,
        )
        authorization_denial = self._authorize(invocation_input, operation)
        if authorization_denial is not None:
            return authorization_denial
        if operation.input_schema is not None:
            try:
                normalized_arguments = self.contracts.schema_registry.normalize_value(
                    operation.input_schema, dict(invocation_input.arguments)
                )
                if not isinstance(normalized_arguments, Mapping):
                    return AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": "operation input schema must normalize to an object"})
                invocation_input = AIcInvocationInput(
                    invocation_id=invocation_input.invocation_id,
                    parent_invocation_id=invocation_input.parent_invocation_id,
                    capability_id=invocation_input.capability_id,
                    capability_version=invocation_input.capability_version,
                    operation_id=invocation_input.operation_id,
                    provider_instance_id=invocation_input.provider_instance_id,
                    arguments=dict(normalized_arguments),
                    consumer_instance_id=invocation_input.consumer_instance_id,
                    requirement_id=invocation_input.requirement_id,
                )
            except AIxSchemaValidationError as exc:
                return AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": str(exc)})

        if self.observations is not None:
            self.observations.dispatch(AIcObservationInput(
                invocation_id=invocation_input.invocation_id,
                parent_invocation_id=invocation_input.parent_invocation_id,
                phase=AInObservationPhase.PRE,
                capability_id=invocation_input.capability_id,
                capability_version=invocation_input.capability_version,
                operation_id=invocation_input.operation_id,
                provider_instance_id=invocation_input.provider_instance_id,
                arguments=_redact_mapping(invocation_input.arguments, operation.sensitive_input_paths),
            ))

        token = _CURRENT_INVOCATION_ID.set(invocation_input.invocation_id)
        try:
            output = endpoint.invoke(invocation_input)
            if (
                not output.success
                and output.error is not None
                and output.error.get("type") == "PERMISSION_DENIED"
                and output.error.get("retry_disposition") == AInPermissionRetryDisposition.SAFE_AFTER_ENTITLEMENT_CHANGE.value
                and self.entitlement_remediator is not None
            ):
                remediation = self.entitlement_remediator.remediate(AIcEntitlementRemediationRequest(
                    component_id=str(output.error.get("component_id") or ""),
                    provider_instance_id=invocation_input.provider_instance_id,
                    capability_id=invocation_input.capability_id,
                    capability_version=invocation_input.capability_version,
                    permission_id=(str(output.error.get("permission_id")) if output.error.get("permission_id") is not None else None),
                    remediation_hint=(str(output.error.get("remediation_hint")) if output.error.get("remediation_hint") is not None else None),
                    context={
                        "consumer_instance_id": invocation_input.consumer_instance_id,
                        "requirement_id": invocation_input.requirement_id,
                        "operation_id": invocation_input.operation_id,
                    },
                ))
                if remediation.changed:
                    if self.entitlement_refresh_callback is not None:
                        self.entitlement_refresh_callback()
                    output = endpoint.invoke(invocation_input)
        finally:
            _CURRENT_INVOCATION_ID.reset(token)

        if output.success and operation.output_schema is not None:
            try:
                normalized_result = self.contracts.schema_registry.normalize_value(
                    operation.output_schema, output.result
                )
                output = AIcInvocationOutput(True, result=normalized_result)
            except AIxSchemaValidationError as exc:
                output = AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": str(exc)})

        if self.observations is not None:
            result = _redact_value(output.result, operation.sensitive_output_paths)
            self.observations.dispatch(AIcObservationInput(
                invocation_id=invocation_input.invocation_id,
                parent_invocation_id=invocation_input.parent_invocation_id,
                phase=AInObservationPhase.POST,
                capability_id=invocation_input.capability_id,
                capability_version=invocation_input.capability_version,
                operation_id=invocation_input.operation_id,
                provider_instance_id=invocation_input.provider_instance_id,
                arguments={},
                outcome=AInObservationOutcome.SUCCESS if output.success else AInObservationOutcome.ERROR,
                result=result if output.success else None,
                error=output.error if not output.success else None,
            ))
        return output


class AIcCoreCapabilityHandle(AIiCapabilityHandle):
    def __init__(self, binding: AIcBinding, endpoints: AIcEndpointRegistry, dispatcher: AIcInvocationDispatcher) -> None:
        self._binding = binding
        self._endpoints = endpoints
        self._dispatcher = dispatcher

    @property
    def binding(self) -> AIcBinding:
        return self._binding

    def invoke(self, operation_id: str, arguments: Mapping[str, object] | None = None) -> AIcInvocationOutput:
        invocation_input = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=_CURRENT_INVOCATION_ID.get(),
            capability_id=self._binding.capability_id,
            capability_version=self._binding.capability_version,
            operation_id=operation_id,
            provider_instance_id=self._binding.provider_instance_id,
            arguments=dict(arguments or {}),
            consumer_instance_id=self._binding.consumer_instance_id,
            requirement_id=self._binding.requirement_id,
        )
        return self._dispatcher.invoke(self._endpoints.get(self._binding.provider_instance_id), invocation_input)


def invoke_handle_with_parent_context(
    handle: AIiCapabilityHandle,
    parent_invocation_id: str | None,
    operation_id: str,
    arguments: Mapping[str, object] | None = None,
) -> AIcInvocationOutput:
    """Invoke a Core handle while restoring causal context received over a runtime boundary."""
    token = _CURRENT_INVOCATION_ID.set(parent_invocation_id)
    try:
        return handle.invoke(operation_id, arguments)
    finally:
        _CURRENT_INVOCATION_ID.reset(token)


class AIcCapabilityHandleFactory:
    def __init__(self, endpoints: AIcEndpointRegistry, dispatcher: AIcInvocationDispatcher) -> None:
        self.endpoints = endpoints
        self.dispatcher = dispatcher

    def for_consumer(self, consumer_instance_id: str, bindings: tuple[AIcBinding, ...]) -> dict[str, tuple[AIiCapabilityHandle, ...]]:
        grouped: dict[str, list[AIiCapabilityHandle]] = {}
        for binding in bindings:
            if binding.consumer_instance_id != consumer_instance_id:
                continue
            grouped.setdefault(binding.requirement_id, []).append(
                AIcCoreCapabilityHandle(binding, self.endpoints, self.dispatcher)
            )
        return {key: tuple(value) for key, value in grouped.items()}


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

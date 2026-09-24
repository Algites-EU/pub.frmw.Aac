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

from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreintf.contracts import AInCapabilityOperationInteractionKind
from algites.lib.aac.coreintf.descriptor import AIcCapabilityProviderOperationDescriptor
from algites.lib.aac.coreintf.authorization import AIcAuthorizationPrincipal, AIcAuthorizationRequest, AIiAuthorizationProvider
from algites.lib.aac.coreintf.errors import AIxPermissionDenied
from algites.lib.aac.coreintf.entitlement import (
    AInPermissionRetryDisposition, AIcEntitlementRemediationRequest, AIiEntitlementRemediator,
)
from algites.lib.aac.coreintf.invocation import (
    AInOperationCompletionState, AInOperationExecutionState, AInOperationInteractionFailureDetailLevel, AInStateResultDeliveryMode,
    AIiCapabilityEndpoint, AIiCapabilityHandle, AIiOperationInteractionProviderToCaller, AIiOperationInteractionCallerToProvider,
    AIcInvocationInput, AIcInvocationOutput, AIcNullOperationInteraction, AIcOperationCompletion, AIcOperationFailure, AIcOperationInteractionFeatures,
    AIiOperationFailureExceptionFactory, AIxCapabilityOperationFailed, AIxOperationCancelled,
    current_invocation_locale, current_operation_interaction, invocation_locale_context,
    operation_interaction_context, operation_parameter_context,
)
from algites.lib.aac.coreintf.observation import AIcObservationInput, AInObservationOutcome, AInObservationPhase

from .contracts import AIcActiveContractCatalog
from .operation_interaction import AIcOperationInteractionController
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




def _resolve_operation_interaction(explicit: AIiOperationInteractionProviderToCaller | None) -> AIiOperationInteractionProviderToCaller:
    if explicit is not None:
        return explicit
    inherited = current_operation_interaction()
    if isinstance(inherited, AIcNullOperationInteraction):
        return AIcNullOperationInteraction()
    return inherited


class AIcValidatedOperationInteractionProviderProxy(AIiOperationInteractionProviderToCaller):
    """Validate portable RUNNING state-result payloads while delegating interaction transport."""

    def __init__(self, delegate: AIiOperationInteractionProviderToCaller, operation, schema_registry) -> None:
        self._delegate = delegate
        self._operation = operation
        self._schema_registry = schema_registry

    def _running_schema_ref(self):
        mode = self._delegate.caller_snapshot().state_result_delivery_mode
        kind = (
            AInCapabilityOperationInteractionKind.RUNNING_DELTA_STATE_RESULT
            if mode in (AInStateResultDeliveryMode.ON_DEMAND_DELTA, AInStateResultDeliveryMode.ON_CHANGE_DELTA)
            else AInCapabilityOperationInteractionKind.RUNNING_COMPLETE_STATE_RESULT
        )
        schema_ref = self._operation.schema_ref(kind)
        if schema_ref is None:
            raise ValueError(
                f"operation does not define {kind.value} required by state-result delivery mode {mode.value}"
            )
        return schema_ref

    def _normalize(self, value: object) -> object:
        schema_ref = self._running_schema_ref()
        return self._schema_registry.normalize_value_identity(schema_ref.id, schema_ref.version, value)

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        self._delegate.declare_features(features)

    def report_events(self, events) -> None:
        self._delegate.report_events(events)

    def state_result_changed(self) -> int:
        self._running_schema_ref()
        return self._delegate.state_result_changed()

    def update_state_result(self, state_result: object) -> int:
        return self._delegate.update_state_result(self._normalize(state_result))

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        self._delegate.deliver_state_result(self._normalize(state_result), revision=revision)

    def caller_snapshot(self):
        return self._delegate.caller_snapshot()


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
        operation_parameter_resolver: Callable[[AIcInvocationInput], Mapping[str, object]] | None = None,
        provider_operation_resolver: Callable[[AIcInvocationInput], AIcCapabilityProviderOperationDescriptor] | None = None,
    ) -> None:
        self.contracts = contracts
        self.observations = observations
        self.component_authorizations = component_authorizations
        self.principal_authorization_provider = principal_authorization_provider
        self.entitlement_remediator = entitlement_remediator
        self.entitlement_refresh_callback = entitlement_refresh_callback
        self.operation_parameter_resolver = operation_parameter_resolver
        self.provider_operation_resolver = provider_operation_resolver

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

    def _invoke_once(
        self, endpoint: AIiCapabilityEndpoint, invocation_input: AIcInvocationInput,
        operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
    ) -> AIcInvocationOutput:
        operation = self.contracts.operation(
            invocation_input.capability_id,
            invocation_input.capability_version,
            invocation_input.operation_id,
        )
        authorization_denial = self._authorize(invocation_input, operation)
        if authorization_denial is not None:
            return authorization_denial
        input_schema = operation.schema_ref(AInCapabilityOperationInteractionKind.INPUT)
        if input_schema is not None:
            try:
                normalized_arguments = self.contracts.schema_registry.normalize_value_identity(
                    input_schema.id, input_schema.version, dict(invocation_input.arguments)
                )
                if not isinstance(normalized_arguments, Mapping):
                    return AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": "operation INPUT schema must normalize to an object"})
                invocation_input = AIcInvocationInput(
                    invocation_id=invocation_input.invocation_id,
                    parent_invocation_id=invocation_input.parent_invocation_id,
                    capability_id=invocation_input.capability_id,
                    capability_version=invocation_input.capability_version,
                    operation_id=invocation_input.operation_id,
                    provider_instance_id=invocation_input.provider_instance_id,
                    arguments=dict(normalized_arguments),
                    operation_parameter_overrides=dict(invocation_input.operation_parameter_overrides),
                    effective_operation_parameters=dict(invocation_input.effective_operation_parameters),
                    consumer_instance_id=invocation_input.consumer_instance_id,
                    requirement_id=invocation_input.requirement_id,
                    locale=invocation_input.locale,
                )
            except (AIxSchemaValidationError, KeyError) as exc:
                return AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": str(exc)})
        elif invocation_input.arguments:
            return AIcInvocationOutput(False, error={
                "type": "UNEXPECTED_OPERATION_INPUT",
                "message": "operation does not define an INPUT interaction",
            })

        if self.operation_parameter_resolver is not None:
            try:
                effective_operation_parameters = dict(self.operation_parameter_resolver(invocation_input))
                invocation_input = AIcInvocationInput(
                    invocation_id=invocation_input.invocation_id,
                    parent_invocation_id=invocation_input.parent_invocation_id,
                    capability_id=invocation_input.capability_id,
                    capability_version=invocation_input.capability_version,
                    operation_id=invocation_input.operation_id,
                    provider_instance_id=invocation_input.provider_instance_id,
                    arguments=dict(invocation_input.arguments),
                    operation_parameter_overrides=dict(invocation_input.operation_parameter_overrides),
                    effective_operation_parameters=effective_operation_parameters,
                    consumer_instance_id=invocation_input.consumer_instance_id,
                    requirement_id=invocation_input.requirement_id,
                    locale=invocation_input.locale,
                )
            except Exception as exc:
                return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})

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
            with operation_interaction_context(operation_interaction), operation_parameter_context(
                invocation_input.effective_operation_parameters
            ), invocation_locale_context(invocation_input.locale):
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
                    with operation_interaction_context(operation_interaction), operation_parameter_context(
                        invocation_input.effective_operation_parameters
                    ), invocation_locale_context(invocation_input.locale):
                        output = endpoint.invoke(invocation_input)
        finally:
            _CURRENT_INVOCATION_ID.reset(token)

        if output.success:
            success_schema = operation.schema_ref(AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT)
            if success_schema is not None:
                try:
                    normalized_result = self.contracts.schema_registry.normalize_value_identity(
                        success_schema.id, success_schema.version, output.result
                    )
                    output = AIcInvocationOutput(True, result=normalized_result)
                except (AIxSchemaValidationError, KeyError) as exc:
                    output = AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": str(exc)})
            elif output.result is not None:
                output = AIcInvocationOutput(False, error={
                    "type": "UNEXPECTED_FINAL_SUCCESS_STATE_RESULT",
                    "message": "operation returned a result but does not define FINAL_SUCCESS_STATE_RESULT",
                })

        if not output.success and output.error is not None:
            error = dict(output.error)
            if error.get("type") == "OPERATION_CANCELLED" and bool(error.get("has_state_result", False)):
                cancelled_schema = operation.schema_ref(AInCapabilityOperationInteractionKind.FINAL_CANCELLED_STATE_RESULT)
                if cancelled_schema is None:
                    output = AIcInvocationOutput(False, error={
                        "type": "UNEXPECTED_FINAL_CANCELLED_STATE_RESULT",
                        "message": "operation returned cancelled state data but defines no FINAL_CANCELLED_STATE_RESULT",
                    })
                else:
                    try:
                        normalized_cancelled = self.contracts.schema_registry.normalize_value_identity(
                            cancelled_schema.id, cancelled_schema.version, error.get("state_result")
                        )
                        error["state_result"] = normalized_cancelled
                        output = AIcInvocationOutput(False, error=error)
                    except (AIxSchemaValidationError, KeyError) as exc:
                        output = AIcInvocationOutput(False, error={"type": "AIxSchemaValidationError", "message": str(exc)})
            elif error.get("extension") is not None:
                failed_schema = operation.schema_ref(AInCapabilityOperationInteractionKind.FINAL_FAILED_STATE_RESULT_EXTENSION)
                if failed_schema is None:
                    output = AIcInvocationOutput(False, error={
                        "type": "UNEXPECTED_FINAL_FAILED_STATE_RESULT_EXTENSION",
                        "message": "operation returned failure extension data but defines no FINAL_FAILED_STATE_RESULT_EXTENSION",
                    })
                else:
                    try:
                        error["extension"] = self.contracts.schema_registry.normalize_value_identity(
                            failed_schema.id, failed_schema.version, error.get("extension")
                        )
                        output = AIcInvocationOutput(False, error=error)
                    except (AIxSchemaValidationError, KeyError) as exc:
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


    def invoke(
        self, endpoint: AIiCapabilityEndpoint, invocation_input: AIcInvocationInput,
        operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
    ) -> AIcInvocationOutput:
        interaction = _resolve_operation_interaction(operation_interaction)
        controller = interaction if isinstance(interaction, AIiOperationInteractionCallerToProvider) else None
        operation = self.contracts.operation(
            invocation_input.capability_id, invocation_input.capability_version, invocation_input.operation_id
        )
        selected_mode = interaction.caller_snapshot().state_result_delivery_mode
        provider_operation = self.provider_operation_resolver(invocation_input) if self.provider_operation_resolver is not None else None
        if provider_operation is not None:
            provider_interaction = provider_operation.interaction
            if selected_mode not in provider_interaction.supported_state_result_delivery_modes:
                output = AIcInvocationOutput(False, error={
                    "type": "UNSUPPORTED_STATE_RESULT_DELIVERY_MODE",
                    "message": f"provider operation does not support state-result delivery mode {selected_mode.value}",
                })
                if controller is not None:
                    controller.core_transition(AInOperationExecutionState.RUNNING)
                    controller.core_transition(
                        AInOperationExecutionState.FAILED,
                        state_result=_failure_from_output(output),
                        has_state_result=True,
                    )
                return output
            interaction.declare_features(AIcOperationInteractionFeatures(
                progress_reporting=provider_interaction.progress_reporting,
                cancellation=provider_interaction.cancellation,
                detail_level=provider_interaction.detail_level,
                reporting_interval=provider_interaction.reporting_interval,
                supported_state_result_delivery_modes=provider_interaction.supported_state_result_delivery_modes,
            ))
        provider_interaction_endpoint = AIcValidatedOperationInteractionProviderProxy(
            interaction, operation, self.contracts.schema_registry
        )
        if controller is not None:
            controller.core_transition(AInOperationExecutionState.RUNNING)
        try:
            output = self._invoke_once(endpoint, invocation_input, provider_interaction_endpoint)
        except Exception as exc:
            output = AIcInvocationOutput(False, error=_exception_error(exc))
        if controller is not None:
            if output.success:
                has_final_success_result = operation.schema_ref(
                    AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT
                ) is not None
                controller.core_transition(
                    AInOperationExecutionState.COMPLETED,
                    state_result=output.result,
                    has_state_result=has_final_success_result,
                )
            elif output.error is not None and output.error.get("type") == "OPERATION_CANCELLED":
                controller.core_transition(
                    AInOperationExecutionState.CANCELLED,
                    state_result=output.error.get("state_result"),
                    has_state_result=bool(output.error.get("has_state_result", False)),
                )
            else:
                controller.core_transition(
                    AInOperationExecutionState.FAILED,
                    state_result=_failure_from_output(output),
                    has_state_result=True,
                )
        return output


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
        from algites.lib.aac.coreintf.presentation import normalize_display_text
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


class AIcCoreCapabilityHandle(AIiCapabilityHandle):
    def __init__(self, binding: AIcBinding, endpoints: AIcEndpointRegistry, dispatcher: AIcInvocationDispatcher) -> None:
        self._binding = binding
        self._endpoints = endpoints
        self._dispatcher = dispatcher

    @property
    def binding(self) -> AIcBinding:
        return self._binding

    def invoke(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
        locale: str | None = None,
    ) -> AIcInvocationOutput:
        effective_locale = locale if locale is not None else current_invocation_locale()
        invocation_input = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=_CURRENT_INVOCATION_ID.get(),
            capability_id=self._binding.capability_id,
            capability_version=self._binding.capability_version,
            operation_id=operation_id,
            provider_instance_id=self._binding.provider_instance_id,
            arguments=dict(arguments or {}),
            operation_parameter_overrides=dict(operation_parameters or {}),
            consumer_instance_id=self._binding.consumer_instance_id,
            requirement_id=self._binding.requirement_id,
            locale=effective_locale,
        )
        interaction = _resolve_operation_interaction(operation_interaction)
        return self._dispatcher.invoke(
            self._endpoints.get(self._binding.provider_instance_id), invocation_input, interaction
        )

    def new_operation_interaction(
        self, *,
        listener: Callable[[object], None] | None = None,
        exception_factory: AIiOperationFailureExceptionFactory | None = None,
    ) -> AIiOperationInteractionCallerToProvider:
        interaction = AIcOperationInteractionController(listener=listener)
        interaction.set_exception_factory(exception_factory)
        return interaction

    def invoke_completion(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionCallerToProvider | None = None,
        locale: str | None = None,
    ) -> AIcOperationCompletion:
        output = self.invoke(
            operation_id, arguments, operation_parameters=operation_parameters,
            operation_interaction=operation_interaction, locale=locale,
        )
        if output.success:
            return AIcOperationCompletion(
                AInOperationCompletionState.SUCCESS, success_result=output.result
            )
        error = dict(output.error or {})
        if error.get("type") == "OPERATION_CANCELLED":
            return AIcOperationCompletion(
                AInOperationCompletionState.CANCELLED,
                cancelled_result=error.get("state_result") if error.get("has_state_result") else None,
            )
        failure = _failure_from_output(output)
        factory = operation_interaction.exception_factory() if operation_interaction is not None else None
        if factory is not None:
            exception = factory.create(failure)
            if not isinstance(exception, AIxCapabilityOperationFailed):
                raise TypeError("operation failure exception factory returned an incompatible exception")
            raise exception
        raise AIxCapabilityOperationFailed(failure)

    def start(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionCallerToProvider | None = None,
        locale: str | None = None,
    ) -> AIiOperationInteractionCallerToProvider:
        interaction = operation_interaction or AIcOperationInteractionController()
        thread = threading.Thread(
            target=self.invoke,
            kwargs={
                "operation_id": operation_id,
                "arguments": arguments,
                "operation_parameters": operation_parameters,
                "operation_interaction": interaction,
                "locale": locale,
            },
            name=f"aac-operation-{self._binding.provider_instance_id}-{operation_id}",
            daemon=True,
        )
        thread.start()
        return interaction


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

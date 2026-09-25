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
from ._context import CURRENT_AUTHORIZATION_PRINCIPAL as _CURRENT_AUTHORIZATION_PRINCIPAL
from ._context import CURRENT_INVOCATION_ID as _CURRENT_INVOCATION_ID

def _resolve_operation_interaction(explicit: AIiOperationInteractionProviderToCaller | None) -> AIiOperationInteractionProviderToCaller:
    if explicit is not None:
        return explicit
    inherited = current_operation_interaction()
    if isinstance(inherited, AIcNullOperationInteraction):
        return AIcNullOperationInteraction()
    return inherited

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

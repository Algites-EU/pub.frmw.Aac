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

from .aic_endpoint_registry import AIcEndpointRegistry
from .aic_invocation_dispatcher import AIcInvocationDispatcher
from ._context import CURRENT_INVOCATION_ID as _CURRENT_INVOCATION_ID

def _resolve_operation_interaction(explicit: AIiOperationInteractionProviderToCaller | None) -> AIiOperationInteractionProviderToCaller:
    if explicit is not None:
        return explicit
    inherited = current_operation_interaction()
    if isinstance(inherited, AIcNullOperationInteraction):
        return AIcNullOperationInteraction()
    return inherited

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

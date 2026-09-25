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

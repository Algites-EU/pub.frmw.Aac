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

from .aic_core_capability_handle import AIcCoreCapabilityHandle
from .aic_endpoint_registry import AIcEndpointRegistry
from .aic_invocation_dispatcher import AIcInvocationDispatcher

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

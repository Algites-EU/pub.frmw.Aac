from __future__ import annotations
import dataclasses
from contextvars import ContextVar
import importlib
import inspect
import json
import sys
import threading
import traceback
import types
from enum import Enum
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints
from ..capability.api import AIcProvidedCapability
from ..instances.api import AIcBinding, AIcProviderInstance, AInProviderAccessMode, AInProviderInstanceState
from ..presentation.api import AIcDisplayText
from ..errors import AIxPermissionDenied
from ..entitlement.api import AIcEntitlementLicensingScope
from ..entitlement.api import (
    AIcCapabilityEntitlementContext, AIcEffectiveEntitlementPermission, AIcEntitlementContext,
    AIcEntitlementGrantProvenance,
)
from ..configuration.api import (
    AInConfigurationTargetKind, AInConfigurationValueSourceKind, AIcConfigurationContributionProvenance,
    AIcConfigurationPolicy, AIcConfigurationTarget, AIcEffectiveConfiguration, AIcEffectiveConfigurationPolicy,
    AIcEffectiveConfigurationValue,
)
from ..invocation.api import (
    AInOperationInteractionDetailLevel, AInOperationInteractionEventType, AInOperationInteractionFailureDetailLevel,
    AInOperationInteractionMode, AInOperationInteractionSeverity, AInStateResultDeliveryMode,
    AIiCapabilityHandle, AIiOperationInteractionProviderToCaller, AIiOperationInteractionCallerToProvider, AIcInvocationInput,
    AIcInvocationOutput, AIcOperationInteractionCallerToProviderMessage, AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures, AIxCapabilityOperationFailed, AIxOperationCancelled, current_invocation_locale,
    current_operation_interaction, invocation_locale_context, operation_interaction_context, operation_parameter_context,
)
from .provider import AIcProviderRuntimeContext, AIiProviderRuntime, AIiProviderRuntimeFactory

from ._process_context import CURRENT_PROCESS_INVOCATION_ID as _CURRENT_PROCESS_INVOCATION_ID

class AIcProcessCapabilityHandle(AIiCapabilityHandle):
    """Process-local consumer handle backed by Core over the host control channel."""

    def __init__(self, binding: AIcBinding, requirement_id: str, handle_index: int, channel: "AIcHostChannel") -> None:
        self._binding = binding
        self._requirement_id = requirement_id
        self._handle_index = handle_index
        self._channel = channel

    @property
    def binding(self) -> AIcBinding:
        return self._binding

    def invoke(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
        locale: str | None = None,
    ) -> AIcInvocationOutput:
        response = self._channel.core_invoke(
            self._requirement_id,
            self._handle_index,
            operation_id,
            dict(arguments or {}),
            dict(operation_parameters or {}),
            _CURRENT_PROCESS_INVOCATION_ID.get(),
            locale if locale is not None else current_invocation_locale(),
        )
        return AIcInvocationOutput(
            success=bool(response.get("success", False)),
            result=response.get("result"),
            error=response.get("error") if isinstance(response.get("error"), Mapping) else None,
        )

    def start(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionCallerToProvider | None = None,
        locale: str | None = None,
    ) -> AIiOperationInteractionCallerToProvider:
        if operation_interaction is None:
            raise ValueError("process-local asynchronous invocation requires an explicit operation interaction controller")
        thread = threading.Thread(
            target=self.invoke,
            kwargs={
                "operation_id": operation_id,
                "arguments": arguments,
                "operation_parameters": operation_parameters,
                "operation_interaction": operation_interaction,
                "locale": locale,
            },
            name=f"aac-process-nested-operation-{operation_id}",
            daemon=True,
        )
        thread.start()
        return operation_interaction

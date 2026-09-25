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

from .aic_host_channel import AIcHostChannel

def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

class AIcProcessOperationInteraction(AIiOperationInteractionProviderToCaller):
    def __init__(self, invocation_id: str, channel: AIcHostChannel) -> None:
        self._invocation_id = invocation_id
        self._channel = channel

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        self._channel.write({
            "kind": "operation_interaction_features",
            "invocation_id": self._invocation_id,
            "features": _jsonable(features),
        })

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        if not events:
            return
        self._channel.write({
            "kind": "operation_interaction_events",
            "invocation_id": self._invocation_id,
            "events": _jsonable(events),
        })

    def state_result_changed(self) -> int:
        result = self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_state_result_changed"
        )
        return int(result["revision"])

    def update_state_result(self, state_result: object) -> int:
        result = self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_update_state_result",
            {"state_result": _jsonable(state_result)},
        )
        return int(result["revision"])

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_deliver_state_result",
            {"state_result": _jsonable(state_result), "revision": revision},
        )

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        return self._channel.operation_interaction_caller_snapshot(self._invocation_id)

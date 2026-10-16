from __future__ import annotations
import dataclasses
from datetime import datetime
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
    AIiCapabilityHandle, AIiOperationInteractionProviderToCallerOnProvider, AIiOperationInteractionCallerToProviderOnCaller, AIcInvocationInput,
    AIcInvocationOutput, AIcOperationInteractionCallerToProviderMessage, AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures, AIxCapabilityOperationFailed, AIxOperationCancelled, current_invocation_locale,
    current_operation_interaction, invocation_locale_context, operation_interaction_context, operation_parameter_context,
)
from .provider import AIcProviderRuntimeContext, AIiProviderRuntime, AIiProviderRuntimeFactory

from .aic_host_channel import AIcHostChannel
from ..invocation.aic_operation_cancellation_acceptance import accept_cancellation_locally

def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {"".join(part[:1].upper() + part[1:] for part in field.name.split("_")): _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

class AIcProcessOperationInteraction(AIiOperationInteractionProviderToCallerOnProvider):
    def __init__(self, invocation_id: str, channel: AIcHostChannel) -> None:
        self._invocation_id = invocation_id
        self._channel = channel
        self._last_caller_snapshot = None
        self._cancellation_acceptance = None

    def send_message(self, message) -> None:
        from ..invocation.aic_operation_interaction_provider_to_caller_message import (
            AIcOperationInteractionProviderToCallerMessage,
        )
        if not isinstance(message, AIcOperationInteractionProviderToCallerMessage):
            raise TypeError("expected provider-to-caller message")
        self._channel.write({
            "Kind": "operation_interaction_message",
            "InvocationId": self._invocation_id,
            "Message": _jsonable(message),
        })

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        self._channel.write({
            "Kind": "operation_interaction_features",
            "InvocationId": self._invocation_id,
            "Features": _jsonable(features),
        })

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        if not events:
            return
        self._channel.write({
            "Kind": "operation_interaction_events",
            "InvocationId": self._invocation_id,
            "Events": _jsonable(events),
        })

    def state_result_changed(self) -> int:
        result = self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_state_result_changed"
        )
        return int(result["Revision"])

    def update_state_result(self, state_result: object) -> int:
        result = self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_update_state_result",
            {"StateResult": _jsonable(state_result)},
        )
        return int(result["Revision"])

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        self._channel._operation_interaction_request(
            self._invocation_id, "operation_interaction_deliver_state_result",
            {"StateResult": _jsonable(state_result), "Revision": revision},
        )

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        state = self._channel.operation_interaction_caller_snapshot(self._invocation_id)
        self._last_caller_snapshot = state
        return state

    def accept_cancellation(self, reasons: frozenset[str]):
        if self._cancellation_acceptance is not None:
            return self._cancellation_acceptance
        state = self._last_caller_snapshot or self.caller_snapshot()
        acceptance = accept_cancellation_locally(state, reasons)
        self._cancellation_acceptance = acceptance
        # Fire-and-forget report. No Core approval is required for local acceptance.
        self._channel.write({
            "Kind": "operation_interaction_cancellation_acceptance",
            "InvocationId": self._invocation_id,
            "Acceptance": _jsonable(acceptance),
        })
        return acceptance

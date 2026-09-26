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

def _operation_interaction_caller_message_from_dict(
    raw: Mapping[str, object]
) -> AIcOperationInteractionCallerToProviderMessage:
    return AIcOperationInteractionCallerToProviderMessage(
        last_accepted_state_result_revision=int(raw.get("LastAcceptedStateResultRevision", 0)),
        interaction_mode=AInOperationInteractionMode(str(raw.get("InteractionMode", "foreground"))),
        cancellation_requested=bool(raw.get("CancellationRequested", False)),
        detail_level=AInOperationInteractionDetailLevel(str(raw.get("DetailLevel", "summary"))),
        reporting_interval_ms=(int(raw["ReportingIntervalMs"]) if raw.get("ReportingIntervalMs") is not None else None),
        failure_detail_level=AInOperationInteractionFailureDetailLevel(str(raw.get("FailureDetailLevel", "basic"))),
        state_result_delivery_mode=AInStateResultDeliveryMode(str(raw.get("StateResultDeliveryMode", "on_demand_complete"))),
        state_result_request_id=int(raw.get("StateResultRequestId", 0)),
    )

def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("AAC process payload must be an object")
    return value

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

class AIcHostChannel:
    def __init__(self) -> None:
        self._reader = sys.stdin
        self._protocol_writer = sys.stdout
        # Provider code may freely print; physical stdout is reserved for protocol frames.
        sys.stdout = sys.stderr
        self._next_id = 0

    def read(self) -> dict[str, object] | None:
        line = self._reader.readline()
        if line == "":
            return None
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("AAC process frame must be a json object")
        return raw

    def write(self, frame: Mapping[str, object]) -> None:
        self._protocol_writer.write(json.dumps(_jsonable(dict(frame)), sort_keys=True, separators=(",", ":")) + "\n")
        self._protocol_writer.flush()

    def respond(self, request_id: str, *, success: bool, result: object | None = None, error: Mapping[str, object] | None = None) -> None:
        self.write({"Kind": "response", "RequestId": request_id, "Success": success, "Result": result, "Error": error})

    def core_invoke(
        self, requirement_id: str, handle_index: int, operation_id: str, arguments: Mapping[str, object],
        operation_parameters: Mapping[str, object], parent_invocation_id: str | None, locale: str | None,
    ) -> Mapping[str, object]:
        self._next_id += 1
        request_id = f"child-{self._next_id}"
        self.write({
            "Kind": "core_invoke",
            "RequestId": request_id,
            "RequirementId": requirement_id,
            "HandleIndex": handle_index,
            "OperationId": operation_id,
            "Arguments": dict(arguments),
            "OperationParameters": dict(operation_parameters),
            "ParentInvocationId": parent_invocation_id,
            "Locale": locale,
        })
        while True:
            frame = self.read()
            if frame is None:
                raise RuntimeError("Core process channel closed while waiting for nested invocation")
            if frame.get("Kind") == "core_response" and frame.get("RequestId") == request_id:
                return frame
            raise RuntimeError(f"unexpected AAC frame while waiting for core response: {frame.get('Kind')!r}")


    def _operation_interaction_request(
        self, invocation_id: str, kind: str, payload: Mapping[str, object] | None = None
    ) -> Mapping[str, object]:
        self._next_id += 1
        request_id = f"interaction-{self._next_id}"
        frame = {"Kind": kind, "RequestId": request_id, "InvocationId": invocation_id}
        if payload:
            frame.update(dict(payload))
        self.write(frame)
        while True:
            response = self.read()
            if response is None:
                raise RuntimeError("Core process channel closed while waiting for operation interaction response")
            if response.get("Kind") == "operation_interaction_response" and response.get("RequestId") == request_id:
                if not bool(response.get("Success", False)):
                    raise RuntimeError(str(response.get("Error") or "operation interaction request failed"))
                result = response.get("Result", {})
                return _as_mapping(result) if isinstance(result, Mapping) else {}
            raise RuntimeError(f"unexpected AAC frame while waiting for operation interaction response: {response.get('Kind')!r}")

    def operation_interaction_caller_snapshot(
        self, invocation_id: str
    ) -> AIcOperationInteractionCallerToProviderMessage:
        result = self._operation_interaction_request(invocation_id, "operation_interaction_caller_snapshot")
        return _operation_interaction_caller_message_from_dict(_as_mapping(result.get("Caller", {})))

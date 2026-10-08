from __future__ import annotations

from eu.algites.frmw.aac.core.invocation.aiig_operation_interaction_event_1 import AIigOperationInteractionEvent_1
import json
import os
import queue
import subprocess
import sys
import threading
from dataclasses import asdict
from typing import Mapping, Sequence
from uuid import uuid4
from eu.algites.frmw.aac.core.descriptor.api import AIcProviderDefinitionDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementContext
from eu.algites.frmw.aac.core.configuration.api import AInConfigurationTargetKind, AIcConfigurationTarget, AIcEffectiveConfiguration
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationInteractionEventType, AInOperationInteractionSeverity, AInStateResultDeliveryMode,
    AIiCapabilityEndpoint, AIiCapabilityHandle, AIiOperationInteractionProviderToCaller, AIcInvocationInput, AIcInvocationOutput,
    AIcOperationInteractionEvent, AIcOperationInteractionFeatures, current_operation_interaction,
)
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime
from eu.algites.frmw.aac.core.readiness.api import AInReadinessState, AIcReadinessReason, AIcReadinessResult
from eu.algites.frmw.aac.core.implementation.errors import AIxProcessEndpointError
from eu.algites.frmw.aac.core.instances.registry import instance_to_dict
from eu.algites.frmw.aac.core.invocation.dispatcher import invoke_handle_with_parent_context

from .aic_json_line_process_endpoint import AIcJsonLineProcessEndpoint
from .aic_process_provider_runtime import AIcProcessProviderRuntime

_DEFAULT_PROCESS_COMMAND = (
    "{python}",
    "-m",
    "eu.algites.frmw.aac.core.runtime.process_host",
)

def _display_text_from_raw(raw: object) -> AIcDisplayText | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError("operation interaction display text must be an object")
    return AIcDisplayText(
        text=str(raw["Text"]) if raw.get("Text") is not None else None,
        resource_key=str(raw["ResourceKey"]) if raw.get("ResourceKey") is not None else None,
    )

def _operation_interaction_event_from_dict(raw: Mapping[str, object]) -> AIcOperationInteractionEvent:
    details = raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__DETAILS, {})
    return AIcOperationInteractionEvent(
        event_type=AInOperationInteractionEventType(str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__EVENT_TYPE])),
        progress_id=str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PROGRESS_ID]) if raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PROGRESS_ID) is not None else None,
        parent_progress_id=str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PARENT_PROGRESS_ID]) if raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PARENT_PROGRESS_ID) is not None else None,
        phase_id=str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PHASE_ID]) if raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__PHASE_ID) is not None else None,
        name=_display_text_from_raw(raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__NAME)),
        description=_display_text_from_raw(raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
        current=raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__CURRENT) if isinstance(raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__CURRENT), (int, float)) else None,
        total=raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__TOTAL) if isinstance(raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__TOTAL), (int, float)) else None,
        unit=str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__UNIT]) if raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__UNIT) is not None else None,
        severity=AInOperationInteractionSeverity(str(raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__SEVERITY, "info"))),
        code=str(raw[AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__CODE]) if raw.get(AIigOperationInteractionEvent_1.SCHEMA_FIELD_NAME__CODE) is not None else None,
        details=dict(details) if isinstance(details, Mapping) else {},
    )

def _output_from_raw(raw: object) -> AIcInvocationOutput:
    # Persistent process host wraps the provider AIcInvocationOutput in a request result.
    if isinstance(raw, Mapping) and "success" in raw:
        return AIcInvocationOutput(
            success=bool(raw.get("Success")),
            result=raw.get("Result"),
            error=raw.get("Error") if isinstance(raw.get("Error"), Mapping) else None,
        )
    return AIcInvocationOutput(False, error={"Type": "InvalidProcessResponse", "Message": "response must contain boolean success"})

def _json_default(value: object) -> object:
    if hasattr(value, "value"):
        return getattr(value, "value")
    raise TypeError(f"value of type {type(value).__name__} is not json serializable")

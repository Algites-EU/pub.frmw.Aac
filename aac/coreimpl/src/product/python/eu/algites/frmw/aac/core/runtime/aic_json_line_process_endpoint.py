from __future__ import annotations
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

def _output_from_raw(raw: object) -> AIcInvocationOutput:
    # Persistent process host wraps the provider AIcInvocationOutput in a request result.
    if isinstance(raw, Mapping) and "success" in raw:
        return AIcInvocationOutput(
            success=bool(raw.get("success")),
            result=raw.get("result"),
            error=raw.get("error") if isinstance(raw.get("error"), Mapping) else None,
        )
    return AIcInvocationOutput(False, error={"type": "InvalidProcessResponse", "message": "response must contain boolean success"})

def _json_default(value: object) -> object:
    if hasattr(value, "value"):
        return getattr(value, "value")
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")

class AIcJsonLineProcessEndpoint(AIiCapabilityEndpoint):
    """Legacy one-invocation-per-process endpoint retained for explicit utility use.

    Normal AAC PROCESS provider runtimes use AIcProcessProviderRuntime below, which owns
    one persistent process per provider instance for the full runtime lifecycle.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not command:
            raise ValueError("process endpoint command must not be empty")
        self.command = tuple(command)
        self.cwd = cwd
        self.env = dict(env or {})
        self.timeout = timeout

    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        payload = json.dumps(asdict(invocation_input), sort_keys=True, separators=(",", ":"), default=_json_default)
        process_env = os.environ.copy()
        process_env.update(self.env)
        try:
            completed = subprocess.run(
                self.command,
                input=payload + "\n",
                text=True,
                capture_output=True,
                cwd=self.cwd,
                env=process_env,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})
        if completed.returncode != 0:
            return AIcInvocationOutput(False, error={
                "type": "ProcessExitError",
                "message": f"process exited with code {completed.returncode}",
                "stderr": completed.stderr[-4000:],
            })
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return AIcInvocationOutput(False, error={
                "type": "InvalidProcessResponse",
                "message": str(exc),
                "stdout": completed.stdout[-4000:],
            })
        return _output_from_raw(raw)

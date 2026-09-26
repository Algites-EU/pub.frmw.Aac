from __future__ import annotations
import json
import os
import queue
import subprocess
import sys
import threading
import dataclasses
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

def _canonical_property_name(aPythonName: str) -> str:
    return "".join(locPart[:1].upper() + locPart[1:] for locPart in aPythonName.split("_"))

def _wire_value(aValue: object) -> object:
    if dataclasses.is_dataclass(aValue):
        return {
            _canonical_property_name(locField.name): _wire_value(getattr(aValue, locField.name))
            for locField in dataclasses.fields(aValue)
        }
    if hasattr(aValue, "value"):
        return getattr(aValue, "value")
    if isinstance(aValue, Mapping):
        return {str(locKey): _wire_value(locValue) for locKey, locValue in aValue.items()}
    if isinstance(aValue, tuple):
        return [_wire_value(locValue) for locValue in aValue]
    if isinstance(aValue, list):
        return [_wire_value(locValue) for locValue in aValue]
    return aValue

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
    details = raw.get("Details", {})
    return AIcOperationInteractionEvent(
        event_type=AInOperationInteractionEventType(str(raw["EventType"])),
        progress_id=str(raw["ProgressId"]) if raw.get("ProgressId") is not None else None,
        parent_progress_id=str(raw["ParentProgressId"]) if raw.get("ParentProgressId") is not None else None,
        phase_id=str(raw["PhaseId"]) if raw.get("PhaseId") is not None else None,
        name=_display_text_from_raw(raw.get("Name")),
        description=_display_text_from_raw(raw.get("Description")),
        current=raw.get("Current") if isinstance(raw.get("Current"), (int, float)) else None,
        total=raw.get("Total") if isinstance(raw.get("Total"), (int, float)) else None,
        unit=str(raw["Unit"]) if raw.get("Unit") is not None else None,
        severity=AInOperationInteractionSeverity(str(raw.get("Severity", "info"))),
        code=str(raw["Code"]) if raw.get("Code") is not None else None,
        details=dict(details) if isinstance(details, Mapping) else {},
    )

def _output_from_raw(raw: object) -> AIcInvocationOutput:
    # Persistent process host wraps the provider AIcInvocationOutput in a request result.
    if isinstance(raw, Mapping) and "Success" in raw:
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

class AIcProcessProviderRuntime(AIiProviderRuntime, AIiCapabilityEndpoint):
    """Persistent AAC process Runtime: exactly one child process per provider instance.

    Core owns the Popen handle, process lifetime and json-lines IPC channel.  Provider
    configuration and module state are therefore naturally instance-local.  Requests are
    serialized per instance; nested calls to already resolved consumed capabilities travel
    back to Core using `core_invoke` frames and are safe because the resolved instance graph
    is acyclic.
    """

    def __init__(
        self,
        application_scope_id: str,
        instance: AIcProviderInstance,
        provider_definition: AIcProviderDefinitionDescriptor,
        entitlement: AIcEntitlementContext | None = None,
        *,
        component_configuration: AIcEffectiveConfiguration | None = None,
        provider_instance_configuration: AIcEffectiveConfiguration | None = None,
    ) -> None:
        self.application_scope_id = application_scope_id
        self.instance = instance
        self.provider_definition = provider_definition
        entitlement = entitlement or AIcEntitlementContext(instance.component_id)
        component_configuration = component_configuration or AIcEffectiveConfiguration(
            AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, instance.component_id), {}, ()
        )
        provider_instance_configuration = provider_instance_configuration or AIcEffectiveConfiguration(
            AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, instance.component_id, instance.id), {}, ()
        )
        runtime = provider_definition.runtime
        raw_command = runtime.command or _DEFAULT_PROCESS_COMMAND
        self.command = tuple(sys.executable if token == "{python}" else token for token in raw_command)
        self.cwd = runtime.cwd
        self.timeout = runtime.timeout_seconds
        self.environment = dict(runtime.environment)
        self._handles: dict[str, tuple[AIiCapabilityHandle, ...]] = {}
        self._pending: dict[str, queue.Queue[dict[str, object]]] = {}
        self._pending_lock = threading.Lock()
        self._interaction_lock = threading.Lock()
        self._active_interactions: dict[str, AIiOperationInteractionProviderToCaller] = {}
        self._write_lock = threading.Lock()
        self._request_lock = threading.RLock()
        self._closed = False
        self._stderr_lines: list[str] = []

        process_env = os.environ.copy()
        process_env.update(self.environment)
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self.cwd,
                env=process_env,
            )
        except OSError as exc:
            raise AIxProcessEndpointError(f"cannot start provider process {self.command!r}: {exc}") from exc
        if self._process.stdin is None or self._process.stdout is None or self._process.stderr is None:
            raise AIxProcessEndpointError("provider process pipes were not created")
        self._reader = threading.Thread(target=self._reader_loop, name=f"aac-process-reader-{instance.id}", daemon=True)
        self._stderr_reader = threading.Thread(target=self._stderr_loop, name=f"aac-process-stderr-{instance.id}", daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        self._request("bootstrap", payload={
            "ApplicationScopeId": application_scope_id,
            "ProviderInstance": instance_to_dict(instance),
            "ImplementationClass": provider_definition.implementation_class_for("python"),
            "RuntimeFactoryClass": provider_definition.runtime_factory_class,
            "Entitlement": _wire_value(entitlement),
            "ComponentConfiguration": _wire_value(component_configuration),
            "ProviderInstanceConfiguration": _wire_value(provider_instance_configuration),
        })

    @property
    def process_id(self) -> int:
        return int(self._process.pid)

    @property
    def is_running(self) -> bool:
        return not self._closed and self._process.poll() is None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_lines[-100:])

    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        interaction = current_operation_interaction()
        with self._interaction_lock:
            self._active_interactions[invocation_input.invocation_id] = interaction
        try:
            result = self._request("invoke", payload=invocation_input.to_mapping())
        except Exception as exc:
            return AIcInvocationOutput(False, error={"Type": type(exc).__name__, "Message": str(exc)})
        finally:
            with self._interaction_lock:
                self._active_interactions.pop(invocation_input.invocation_id, None)
        return _output_from_raw(result)

    def entitlement_changed(self, entitlement: AIcEntitlementContext) -> None:
        self._request("lifecycle", action="entitlement_changed", payload={"Entitlement": _wire_value(entitlement)})

    def wire(self, bindings: Mapping[str, tuple[AIiCapabilityHandle, ...]]) -> None:
        self._handles = {key: tuple(value) for key, value in bindings.items()}
        payload: dict[str, list[dict[str, object]]] = {}
        for requirement_id, handles in self._handles.items():
            payload[requirement_id] = [_wire_value(handle.binding) for handle in handles]
        self._request("lifecycle", action="wire", payload={"Bindings": payload})

    def prepare_activation(self) -> None:
        self._request("lifecycle", action="prepare_activation", payload={})

    def readiness(self) -> AIcReadinessResult:
        raw = self._request("lifecycle", action="readiness", payload={})
        if not isinstance(raw, Mapping):
            return AIcReadinessResult()
        state = AInReadinessState(str(raw.get("State", "ready")))
        reasons = tuple(
            AIcReadinessReason(
                str(item.get("Code", "RUNTIME_READINESS")),
                str(item.get("Message", "runtime readiness condition")),
                AInReadinessState(str(item.get("State", state.value))),
                str(item["RequirementId"]) if item.get("RequirementId") is not None else None,
                str(item["Key"]) if item.get("Key") is not None else None,
            )
            for item in raw.get("reasons", ()) if isinstance(item, Mapping)
        )
        return AIcReadinessResult(state, reasons)

    def activate(self) -> None:
        self._request("lifecycle", action="activate", payload={})

    def suspend(self, reason: str) -> None:
        self._request("lifecycle", action="suspend", payload={"Reason": reason})

    def deactivate(self, reason: str) -> None:
        if self._closed:
            return
        self._request("lifecycle", action="deactivate", payload={"Reason": reason})

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._process.poll() is None:
                try:
                    self._request("shutdown", payload={})
                except Exception:
                    pass
                try:
                    self._process.wait(timeout=min(self.timeout, 5.0))
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2.0)
        finally:
            self._closed = True
            for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass

    def _request(self, kind: str, *, payload: Mapping[str, object], action: str | None = None) -> object:
        if self._closed:
            raise AIxProcessEndpointError("provider process runtime is closed")
        with self._request_lock:
            if self._process.poll() is not None:
                raise AIxProcessEndpointError(self._process_failure_message())
            request_id = str(uuid4())
            waiter: queue.Queue[dict[str, object]] = queue.Queue(maxsize=1)
            with self._pending_lock:
                self._pending[request_id] = waiter
            frame: dict[str, object] = {"Kind": kind, "RequestId": request_id, "Payload": dict(payload)}
            if action is not None:
                frame["Action"] = action
            try:
                self._write(frame)
                try:
                    response = waiter.get(timeout=self.timeout)
                except queue.Empty as exc:
                    raise AIxProcessEndpointError(
                        f"timeout waiting for provider process {self.instance.id} ({kind}{'/' + action if action else ''})"
                    ) from exc
            finally:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
            if not bool(response.get("Success", False)):
                error = response.get("Error")
                raise AIxProcessEndpointError(f"provider process request failed: {error}")
            return response.get("Result")

    def _write(self, frame: Mapping[str, object]) -> None:
        if self._process.stdin is None:
            raise AIxProcessEndpointError("provider process stdin is closed")
        line = json.dumps(dict(frame), sort_keys=True, separators=(",", ":"), default=_json_default)
        with self._write_lock:
            try:
                self._process.stdin.write(line + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise AIxProcessEndpointError(self._process_failure_message()) from exc

    def _reader_loop(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                try:
                    frame = json.loads(line)
                    if not isinstance(frame, dict):
                        continue
                    kind = frame.get("Kind")
                    if kind == "response":
                        request_id = str(frame.get("RequestId", ""))
                        with self._pending_lock:
                            waiter = self._pending.get(request_id)
                        if waiter is not None:
                            waiter.put(frame)
                    elif kind == "core_invoke":
                        self._handle_core_invoke(frame)
                    elif kind == "operation_interaction_features":
                        self._handle_operation_interaction_features(frame)
                    elif kind == "operation_interaction_events":
                        self._handle_operation_interaction_events(frame)
                    elif kind == "operation_interaction_state_result_changed":
                        self._handle_operation_interaction_state_result_changed(frame)
                    elif kind == "operation_interaction_update_state_result":
                        self._handle_operation_interaction_update_state_result(frame)
                    elif kind == "operation_interaction_deliver_state_result":
                        self._handle_operation_interaction_deliver_state_result(frame)
                    elif kind == "operation_interaction_caller_snapshot":
                        self._handle_operation_interaction_caller_snapshot(frame)
                except Exception as exc:
                    self._stderr_lines.append(f"protocol reader Error: {type(exc).__name__}: {exc}")
        finally:
            failure = {"Kind": "response", "Success": False, "Error": {"Type": "ProcessExitError", "Message": self._process_failure_message()}}
            with self._pending_lock:
                pending = tuple(self._pending.values())
            for waiter in pending:
                try:
                    waiter.put_nowait(dict(failure))
                except queue.Full:
                    pass

    def _stderr_loop(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            text = line.rstrip("\n")
            self._stderr_lines.append(text)
            # stdout is the component's logical STDOUT in the reference PROCESS profile;
            # physical child stderr carries it because child stdout is reserved for protocol.
            print(text, file=sys.stdout, flush=True)

    def _handle_core_invoke(self, frame: Mapping[str, object]) -> None:
        request_id = str(frame.get("RequestId", ""))
        try:
            requirement_id = str(frame["RequirementId"])
            index = int(frame.get("HandleIndex", 0))
            handles = self._handles[requirement_id]
            handle = handles[index]
            arguments = frame.get("Arguments", {})
            if not isinstance(arguments, Mapping):
                raise TypeError("nested invocation arguments must be an object")
            operation_parameters = frame.get("OperationParameters", {})
            if not isinstance(operation_parameters, Mapping):
                raise TypeError("nested invocation operation_parameters must be an object")
            parent_invocation_id = str(frame["ParentInvocationId"]) if frame.get("ParentInvocationId") is not None else None
            locale = str(frame["Locale"]) if frame.get("Locale") is not None else None
            with self._interaction_lock:
                interaction = self._active_interactions.get(parent_invocation_id or "")
            output = invoke_handle_with_parent_context(
                handle, parent_invocation_id, str(frame["OperationId"]), dict(arguments), dict(operation_parameters),
                interaction, locale,
            )
            response = {
                "Kind": "core_response",
                "RequestId": request_id,
                "Success": output.success,
                "Result": output.result,
                "Error": output.error,
            }
        except Exception as exc:
            response = {
                "Kind": "core_response",
                "RequestId": request_id,
                "Success": False,
                "Error": {"Type": type(exc).__name__, "Message": str(exc)},
            }
        self._write(response)


    def _interaction_for_frame(self, frame: Mapping[str, object]) -> AIiOperationInteractionProviderToCaller | None:
        invocation_id = str(frame.get("InvocationId", ""))
        with self._interaction_lock:
            return self._active_interactions.get(invocation_id)

    def _interaction_response(
        self, frame: Mapping[str, object], *, result: object | None = None, error: Mapping[str, object] | None = None
    ) -> None:
        request_id = str(frame.get("RequestId", ""))
        if not request_id:
            return
        self._write({
            "Kind": "operation_interaction_response",
            "RequestId": request_id,
            "Success": error is None,
            "Result": result,
            "Error": error,
        })

    def _handle_operation_interaction_features(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        raw = frame.get("Features", {})
        if interaction is None or not isinstance(raw, Mapping):
            return
        interaction.declare_features(AIcOperationInteractionFeatures(
            progress_reporting=bool(raw.get("ProgressReporting", False)),
            cancellation=bool(raw.get("Cancellation", False)),
            detail_level=bool(raw.get("DetailLevel", False)),
            reporting_interval=bool(raw.get("ReportingInterval", False)),
            supported_state_result_delivery_modes=tuple(
                AInStateResultDeliveryMode(str(value))
                for value in raw.get("SupportedStateResultDeliveryModes", ("on_demand_complete",))
            ),
        ))

    def _handle_operation_interaction_events(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        raw_events = frame.get("Events", ())
        if interaction is None or not isinstance(raw_events, (list, tuple)):
            return
        events = tuple(
            _operation_interaction_event_from_dict(raw)
            for raw in raw_events if isinstance(raw, Mapping)
        )
        interaction.report_events(events)

    def _handle_operation_interaction_state_result_changed(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"Type": "UnknownInvocation", "Message": "operation interaction is no longer active"})
            return
        try:
            self._interaction_response(frame, result={"Revision": interaction.state_result_changed()})
        except Exception as exc:
            self._interaction_response(frame, error={"Type": type(exc).__name__, "Message": str(exc)})

    def _handle_operation_interaction_update_state_result(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"Type": "UnknownInvocation", "Message": "operation interaction is no longer active"})
            return
        try:
            self._interaction_response(frame, result={"Revision": interaction.update_state_result(frame.get("StateResult"))})
        except Exception as exc:
            self._interaction_response(frame, error={"Type": type(exc).__name__, "Message": str(exc)})

    def _handle_operation_interaction_deliver_state_result(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"Type": "UnknownInvocation", "Message": "operation interaction is no longer active"})
            return
        try:
            revision = int(frame["revision"]) if frame.get("Revision") is not None else None
            interaction.deliver_state_result(frame.get("StateResult"), revision=revision)
            self._interaction_response(frame, result={})
        except Exception as exc:
            self._interaction_response(frame, error={"Type": type(exc).__name__, "Message": str(exc)})

    def _handle_operation_interaction_caller_snapshot(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"Type": "UnknownInvocation", "Message": "operation interaction is no longer active"})
            return
        self._interaction_response(frame, result={"Caller": _wire_value(interaction.caller_snapshot())})

    def _process_failure_message(self) -> str:
        code = self._process.poll()
        tail = " | ".join(self._stderr_lines[-10:])
        return f"provider process {self.instance.id} exited with code {code}; stderr: {tail}" if tail else f"provider process {self.instance.id} exited with code {code}"

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

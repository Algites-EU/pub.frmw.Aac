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

from algites.frmw.aac.coreintf.descriptor import AIcProviderDefinitionDescriptor
from algites.frmw.aac.coreintf.instances import AIcBinding, AIcProviderInstance
from algites.frmw.aac.coreintf.entitlement import AIcEntitlementContext
from algites.frmw.aac.coreintf.configuration import AInConfigurationTargetKind, AIcConfigurationTarget, AIcEffectiveConfiguration
from algites.frmw.aac.coreintf.invocation import (
    AInOperationInteractionEventType, AInOperationInteractionSeverity, AInStateResultDeliveryMode,
    AIiCapabilityEndpoint, AIiCapabilityHandle, AIiOperationInteractionProviderToCaller, AIcInvocationInput, AIcInvocationOutput,
    AIcOperationInteractionEvent, AIcOperationInteractionFeatures, current_operation_interaction,
)
from algites.frmw.aac.coreintf.presentation import AIcDisplayText
from algites.frmw.aac.coreintf.runtime import AIiProviderRuntime
from algites.frmw.aac.coreintf.readiness import AInReadinessState, AIcReadinessReason, AIcReadinessResult

from .errors import AIxProcessEndpointError
from .instances import instance_to_dict
from .invocation import invoke_handle_with_parent_context

_DEFAULT_PROCESS_COMMAND = (
    "{python}",
    "-m",
    "algites.frmw.aac.coreintf.runtime.process_host",
)


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


class AIcProcessProviderRuntime(AIiProviderRuntime, AIiCapabilityEndpoint):
    """Persistent AAC PROCESS runtime: exactly one child process per provider instance.

    Core owns the Popen handle, process lifetime and JSON-lines IPC channel.  Provider
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
            "application_scope_id": application_scope_id,
            "provider_instance": instance_to_dict(instance),
            "implementation_class": provider_definition.implementation_class_for("python"),
            "runtime_factory_class": provider_definition.runtime_factory_class,
            "entitlement": asdict(entitlement),
            "component_configuration": asdict(component_configuration),
            "provider_instance_configuration": asdict(provider_instance_configuration),
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
            result = self._request("invoke", payload=asdict(invocation_input))
        except Exception as exc:
            return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})
        finally:
            with self._interaction_lock:
                self._active_interactions.pop(invocation_input.invocation_id, None)
        return _output_from_raw(result)

    def entitlement_changed(self, entitlement: AIcEntitlementContext) -> None:
        self._request("lifecycle", action="entitlement_changed", payload={"entitlement": asdict(entitlement)})

    def wire(self, bindings: Mapping[str, tuple[AIiCapabilityHandle, ...]]) -> None:
        self._handles = {key: tuple(value) for key, value in bindings.items()}
        payload: dict[str, list[dict[str, object]]] = {}
        for requirement_id, handles in self._handles.items():
            payload[requirement_id] = [asdict(handle.binding) for handle in handles]
        self._request("lifecycle", action="wire", payload={"bindings": payload})

    def prepare_activation(self) -> None:
        self._request("lifecycle", action="prepare_activation", payload={})

    def readiness(self) -> AIcReadinessResult:
        raw = self._request("lifecycle", action="readiness", payload={})
        if not isinstance(raw, Mapping):
            return AIcReadinessResult()
        state = AInReadinessState(str(raw.get("state", "READY")))
        reasons = tuple(
            AIcReadinessReason(
                str(item.get("code", "RUNTIME_READINESS")),
                str(item.get("message", "runtime readiness condition")),
                AInReadinessState(str(item.get("state", state.value))),
                str(item["requirement_id"]) if item.get("requirement_id") is not None else None,
                str(item["key"]) if item.get("key") is not None else None,
            )
            for item in raw.get("reasons", ()) if isinstance(item, Mapping)
        )
        return AIcReadinessResult(state, reasons)

    def activate(self) -> None:
        self._request("lifecycle", action="activate", payload={})

    def suspend(self, reason: str) -> None:
        self._request("lifecycle", action="suspend", payload={"reason": reason})

    def deactivate(self, reason: str) -> None:
        if self._closed:
            return
        self._request("lifecycle", action="deactivate", payload={"reason": reason})

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
            frame: dict[str, object] = {"kind": kind, "request_id": request_id, "payload": dict(payload)}
            if action is not None:
                frame["action"] = action
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
            if not bool(response.get("success", False)):
                error = response.get("error")
                raise AIxProcessEndpointError(f"provider process request failed: {error}")
            return response.get("result")

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
                    kind = frame.get("kind")
                    if kind == "response":
                        request_id = str(frame.get("request_id", ""))
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
                    self._stderr_lines.append(f"protocol reader error: {type(exc).__name__}: {exc}")
        finally:
            failure = {"kind": "response", "success": False, "error": {"type": "ProcessExitError", "message": self._process_failure_message()}}
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
        request_id = str(frame.get("request_id", ""))
        try:
            requirement_id = str(frame["requirement_id"])
            index = int(frame.get("handle_index", 0))
            handles = self._handles[requirement_id]
            handle = handles[index]
            arguments = frame.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise TypeError("nested invocation arguments must be an object")
            operation_parameters = frame.get("operation_parameters", {})
            if not isinstance(operation_parameters, Mapping):
                raise TypeError("nested invocation operation_parameters must be an object")
            parent_invocation_id = str(frame["parent_invocation_id"]) if frame.get("parent_invocation_id") is not None else None
            locale = str(frame["locale"]) if frame.get("locale") is not None else None
            with self._interaction_lock:
                interaction = self._active_interactions.get(parent_invocation_id or "")
            output = invoke_handle_with_parent_context(
                handle, parent_invocation_id, str(frame["operation_id"]), dict(arguments), dict(operation_parameters),
                interaction, locale,
            )
            response = {
                "kind": "core_response",
                "request_id": request_id,
                "success": output.success,
                "result": output.result,
                "error": output.error,
            }
        except Exception as exc:
            response = {
                "kind": "core_response",
                "request_id": request_id,
                "success": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        self._write(response)


    def _interaction_for_frame(self, frame: Mapping[str, object]) -> AIiOperationInteractionProviderToCaller | None:
        invocation_id = str(frame.get("invocation_id", ""))
        with self._interaction_lock:
            return self._active_interactions.get(invocation_id)

    def _interaction_response(
        self, frame: Mapping[str, object], *, result: object | None = None, error: Mapping[str, object] | None = None
    ) -> None:
        request_id = str(frame.get("request_id", ""))
        if not request_id:
            return
        self._write({
            "kind": "operation_interaction_response",
            "request_id": request_id,
            "success": error is None,
            "result": result,
            "error": error,
        })

    def _handle_operation_interaction_features(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        raw = frame.get("features", {})
        if interaction is None or not isinstance(raw, Mapping):
            return
        interaction.declare_features(AIcOperationInteractionFeatures(
            progress_reporting=bool(raw.get("progress_reporting", False)),
            cancellation=bool(raw.get("cancellation", False)),
            detail_level=bool(raw.get("detail_level", False)),
            reporting_interval=bool(raw.get("reporting_interval", False)),
            supported_state_result_delivery_modes=tuple(
                AInStateResultDeliveryMode(str(value))
                for value in raw.get("supported_state_result_delivery_modes", ("ON_DEMAND_COMPLETE",))
            ),
        ))

    def _handle_operation_interaction_events(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        raw_events = frame.get("events", ())
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
            self._interaction_response(frame, error={"type": "UnknownInvocation", "message": "operation interaction is no longer active"})
            return
        try:
            self._interaction_response(frame, result={"revision": interaction.state_result_changed()})
        except Exception as exc:
            self._interaction_response(frame, error={"type": type(exc).__name__, "message": str(exc)})

    def _handle_operation_interaction_update_state_result(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"type": "UnknownInvocation", "message": "operation interaction is no longer active"})
            return
        try:
            self._interaction_response(frame, result={"revision": interaction.update_state_result(frame.get("state_result"))})
        except Exception as exc:
            self._interaction_response(frame, error={"type": type(exc).__name__, "message": str(exc)})

    def _handle_operation_interaction_deliver_state_result(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"type": "UnknownInvocation", "message": "operation interaction is no longer active"})
            return
        try:
            revision = int(frame["revision"]) if frame.get("revision") is not None else None
            interaction.deliver_state_result(frame.get("state_result"), revision=revision)
            self._interaction_response(frame, result={})
        except Exception as exc:
            self._interaction_response(frame, error={"type": type(exc).__name__, "message": str(exc)})

    def _handle_operation_interaction_caller_snapshot(self, frame: Mapping[str, object]) -> None:
        interaction = self._interaction_for_frame(frame)
        if interaction is None:
            self._interaction_response(frame, error={"type": "UnknownInvocation", "message": "operation interaction is no longer active"})
            return
        self._interaction_response(frame, result={"caller": asdict(interaction.caller_snapshot())})

    def _process_failure_message(self) -> str:
        code = self._process.poll()
        tail = " | ".join(self._stderr_lines[-10:])
        return f"provider process {self.instance.id} exited with code {code}; stderr: {tail}" if tail else f"provider process {self.instance.id} exited with code {code}"

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass



def _display_text_from_raw(raw: object) -> AIcDisplayText | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError("operation interaction display text must be an object")
    return AIcDisplayText(
        text=str(raw["text"]) if raw.get("text") is not None else None,
        resource_key=str(raw["resource_key"]) if raw.get("resource_key") is not None else None,
    )


def _operation_interaction_event_from_dict(raw: Mapping[str, object]) -> AIcOperationInteractionEvent:
    details = raw.get("details", {})
    return AIcOperationInteractionEvent(
        event_type=AInOperationInteractionEventType(str(raw["event_type"])),
        progress_id=str(raw["progress_id"]) if raw.get("progress_id") is not None else None,
        parent_progress_id=str(raw["parent_progress_id"]) if raw.get("parent_progress_id") is not None else None,
        phase_id=str(raw["phase_id"]) if raw.get("phase_id") is not None else None,
        name=_display_text_from_raw(raw.get("name")),
        description=_display_text_from_raw(raw.get("description")),
        current=raw.get("current") if isinstance(raw.get("current"), (int, float)) else None,
        total=raw.get("total") if isinstance(raw.get("total"), (int, float)) else None,
        unit=str(raw["unit"]) if raw.get("unit") is not None else None,
        severity=AInOperationInteractionSeverity(str(raw.get("severity", "INFO"))),
        code=str(raw["code"]) if raw.get("code") is not None else None,
        details=dict(details) if isinstance(details, Mapping) else {},
    )


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

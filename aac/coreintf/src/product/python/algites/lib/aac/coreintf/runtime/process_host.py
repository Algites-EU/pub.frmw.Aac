from __future__ import annotations

"""Reference Python host for the AAC PROCESS runtime profile.

The host reserves stdin/stdout for the AAC JSON-lines control protocol.  Component
stdout is redirected to stderr so arbitrary provider output cannot corrupt protocol
frames.  Core may forward that diagnostic stream according to product policy.
"""

import dataclasses
from contextvars import ContextVar
import importlib
import inspect
import json
import sys
import types
from enum import Enum
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from ..contracts import AIcProvidedCapability
from ..instances import AIcBinding, AIcProviderInstance, AInProviderAccessMode, AInProviderInstanceState
from ..errors import AIxPermissionDenied
from ..entitlement import AIcEntitlementLicensingScope
from ..entitlement import (
    AIcCapabilityEntitlementContext, AIcEffectiveEntitlementPermission, AIcEntitlementContext,
    AIcEntitlementGrantProvenance,
)
from ..configuration import (
    AInConfigurationTargetKind, AInConfigurationValueSourceKind, AIcConfigurationContributionProvenance,
    AIcConfigurationPolicy, AIcConfigurationTarget, AIcEffectiveConfiguration, AIcEffectiveConfigurationPolicy,
    AIcEffectiveConfigurationValue,
)
from ..invocation import AIiCapabilityHandle, AIcInvocationInput, AIcInvocationOutput
from .provider import AIcProviderRuntimeContext, AIiProviderRuntime, AIiProviderRuntimeFactory

_CURRENT_PROCESS_INVOCATION_ID: ContextVar[str | None] = ContextVar("aac_process_invocation_id", default=None)


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

    def invoke(self, operation_id: str, arguments: Mapping[str, object] | None = None) -> AIcInvocationOutput:
        response = self._channel.core_invoke(
            self._requirement_id,
            self._handle_index,
            operation_id,
            dict(arguments or {}),
            _CURRENT_PROCESS_INVOCATION_ID.get(),
        )
        return AIcInvocationOutput(
            success=bool(response.get("success", False)),
            result=response.get("result"),
            error=response.get("error") if isinstance(response.get("error"), Mapping) else None,
        )


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
            raise ValueError("AAC process frame must be a JSON object")
        return raw

    def write(self, frame: Mapping[str, object]) -> None:
        self._protocol_writer.write(json.dumps(_jsonable(dict(frame)), sort_keys=True, separators=(",", ":")) + "\n")
        self._protocol_writer.flush()

    def respond(self, request_id: str, *, success: bool, result: object | None = None, error: Mapping[str, object] | None = None) -> None:
        self.write({"kind": "response", "request_id": request_id, "success": success, "result": result, "error": error})

    def core_invoke(self, requirement_id: str, handle_index: int, operation_id: str, arguments: Mapping[str, object], parent_invocation_id: str | None) -> Mapping[str, object]:
        self._next_id += 1
        request_id = f"child-{self._next_id}"
        self.write({
            "kind": "core_invoke",
            "request_id": request_id,
            "requirement_id": requirement_id,
            "handle_index": handle_index,
            "operation_id": operation_id,
            "arguments": dict(arguments),
            "parent_invocation_id": parent_invocation_id,
        })
        while True:
            frame = self.read()
            if frame is None:
                raise RuntimeError("Core process channel closed while waiting for nested invocation")
            if frame.get("kind") == "core_response" and frame.get("request_id") == request_id:
                return frame
            raise RuntimeError(f"unexpected AAC frame while waiting for core response: {frame.get('kind')!r}")


def main() -> int:
    channel = AIcHostChannel()
    runtime: AIiProviderRuntime | None = None
    while True:
        frame = channel.read()
        if frame is None:
            return 0
        kind = str(frame.get("kind", ""))
        request_id = str(frame.get("request_id", ""))
        try:
            if kind == "bootstrap":
                runtime = _bootstrap(frame.get("payload"), channel)
                channel.respond(request_id, success=True, result={"host": "python", "protocol": 1})
            elif kind == "lifecycle":
                if runtime is None:
                    raise RuntimeError("provider runtime has not been bootstrapped")
                result = _lifecycle(runtime, frame.get("action"), frame.get("payload"), channel)
                channel.respond(request_id, success=True, result=result)
            elif kind == "invoke":
                if runtime is None:
                    raise RuntimeError("provider runtime has not been bootstrapped")
                invocation = _invocation_from_dict(_as_mapping(frame.get("payload")))
                output = _invoke_runtime(runtime, invocation)
                channel.respond(request_id, success=True, result=_jsonable(output))
            elif kind == "shutdown":
                channel.respond(request_id, success=True)
                return 0
            else:
                raise ValueError(f"unknown AAC process frame kind {kind!r}")
        except Exception as exc:  # Host must return protocol failures, never traceback on protocol stdout.
            channel.respond(request_id, success=False, error={"type": type(exc).__name__, "message": str(exc)})


def _bootstrap(raw_payload: object, channel: AIcHostChannel) -> AIiProviderRuntime:
    payload = _as_mapping(raw_payload)
    instance = _provider_instance_from_dict(_as_mapping(payload["provider_instance"]))
    entitlement = _entitlement_context_from_dict(_as_mapping(payload.get("entitlement", {})), str(instance.component_id))
    component_configuration = _effective_configuration_from_dict(_as_mapping(payload["component_configuration"]))
    provider_instance_configuration = _effective_configuration_from_dict(_as_mapping(payload["provider_instance_configuration"]))
    context = AIcProviderRuntimeContext(
        str(payload["application_scope_id"]), instance, entitlement, component_configuration, provider_instance_configuration
    )
    factory_name = payload.get("runtime_factory_class")
    if factory_name:
        factory_class = _load_class(str(factory_name))
        factory = factory_class()
        if not isinstance(factory, AIiProviderRuntimeFactory):
            raise TypeError("runtime factory does not implement AIiProviderRuntimeFactory")
        runtime = factory.create(context)
    else:
        provider_class = _load_class(str(payload["implementation_class"]))
        effective_values = provider_instance_configuration.plain_values()
        runtime = provider_class(effective_values if effective_values else dict(instance.configuration))
    if not isinstance(runtime, AIiProviderRuntime):
        raise TypeError("provider implementation does not implement AIiProviderRuntime")
    return runtime


def _lifecycle(runtime: AIiProviderRuntime, action: object, raw_payload: object, channel: AIcHostChannel) -> object:
    action = str(action)
    payload = _as_mapping(raw_payload or {})
    if action == "entitlement_changed":
        runtime.entitlement_changed(_entitlement_context_from_dict(_as_mapping(payload.get("entitlement", {})), ""))
    elif action == "wire":
        runtime.wire(_build_handles(payload.get("bindings", {}), channel))
    elif action == "prepare_activation":
        runtime.prepare_activation()
    elif action == "readiness":
        return dataclasses.asdict(runtime.readiness())
    elif action == "activate":
        runtime.activate()
    elif action == "suspend":
        runtime.suspend(str(payload.get("reason", "")))
    elif action == "deactivate":
        runtime.deactivate(str(payload.get("reason", "")))
    else:
        raise ValueError(f"unknown provider lifecycle action {action!r}")
    return None


def _build_handles(raw_bindings: object, channel: AIcHostChannel) -> dict[str, tuple[AIiCapabilityHandle, ...]]:
    bindings = _as_mapping(raw_bindings)
    result: dict[str, tuple[AIiCapabilityHandle, ...]] = {}
    for requirement_id, raw_values in bindings.items():
        values = raw_values if isinstance(raw_values, list) else []
        handles: list[AIiCapabilityHandle] = []
        for index, raw in enumerate(values):
            binding = _binding_from_dict(_as_mapping(raw))
            handles.append(AIcProcessCapabilityHandle(binding, str(requirement_id), index, channel))
        result[str(requirement_id)] = tuple(handles)
    return result


def _generated_capability_invoker(runtime: object, capability_id: str, capability_version: int):
    """Return the generated invoker owned by the exact capability interface in the runtime MRO."""
    for candidate in type(runtime).__mro__:
        namespace = candidate.__dict__
        if (
            namespace.get("__aac_capability_id__") == capability_id
            and namespace.get("__aac_capability_version__") == capability_version
        ):
            invoker = namespace.get("__aac_invoke__")
            if invoker is not None:
                return invoker
    return None


def _invoke_runtime(runtime: AIiProviderRuntime, invocation: AIcInvocationInput) -> AIcInvocationOutput:
    try:
        generated_invoke = _generated_capability_invoker(
            runtime, invocation.capability_id, invocation.capability_version
        )
        token = _CURRENT_PROCESS_INVOCATION_ID.set(invocation.invocation_id)
        try:
            if generated_invoke is not None:
                result = generated_invoke(runtime, invocation.operation_id, dict(invocation.arguments))
            else:
                method = getattr(runtime, f"{invocation.operation_id}_{invocation.capability_version}")
                hints = get_type_hints(method)
                parameters = tuple(inspect.signature(method).parameters.values())
                if len(parameters) == 1 and parameters[0].name not in invocation.arguments:
                    parameter = parameters[0]
                    annotation = hints.get(parameter.name)
                    if parameter.name == "request" or (inspect.isclass(annotation) and dataclasses.is_dataclass(annotation)):
                        result = method(_coerce_value(annotation, dict(invocation.arguments)))
                    else:
                        kwargs = {
                            name: _coerce_value(hints.get(name), value)
                            for name, value in invocation.arguments.items()
                        }
                        result = method(**kwargs)
                else:
                    kwargs = {
                        name: _coerce_value(hints.get(name), value)
                        for name, value in invocation.arguments.items()
                    }
                    result = method(**kwargs)
        finally:
            _CURRENT_PROCESS_INVOCATION_ID.reset(token)
        return AIcInvocationOutput(True, result=_jsonable(result))
    except AIxPermissionDenied as exc:
        return AIcInvocationOutput(False, error={
            "type": "PERMISSION_DENIED",
            "message": str(exc),
            "capability_id": exc.capability_id or invocation.capability_id,
            "capability_version": exc.capability_version or invocation.capability_version,
            "permission_id": exc.permission_id,
            "retry_disposition": exc.retry_disposition.value,
            "remediation_hint": exc.remediation_hint,
        })
    except Exception as exc:
        return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})


def _coerce_value(annotation: object | None, value: object) -> object:
    if annotation is None or annotation is inspect._empty or annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _coerce_value(candidate, value)
            except (TypeError, ValueError, KeyError):
                pass
        return value
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return annotation(value)
    if inspect.isclass(annotation) and dataclasses.is_dataclass(annotation):
        raw = _as_mapping(value)
        hints = get_type_hints(annotation)
        return annotation(**{field.name: _coerce_value(hints.get(field.name), raw.get(field.name)) for field in dataclasses.fields(annotation)})
    if origin in (tuple, list) and isinstance(value, (tuple, list)):
        item_type = args[0] if args else None
        converted = [_coerce_value(item_type, item) for item in value]
        return tuple(converted) if origin is tuple else converted
    return value


def _load_class(path: str) -> type:
    module_name, separator, class_name = path.partition(":")
    if not separator:
        module_name, separator, class_name = path.rpartition(".")
    if not module_name or not class_name:
        raise ValueError(f"invalid class path {path!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, class_name)
    if not isinstance(value, type):
        raise TypeError(f"{path!r} does not identify a class")
    return value


def _provider_instance_from_dict(raw: Mapping[str, object]) -> AIcProviderInstance:
    return AIcProviderInstance(
        id=str(raw["id"]),
        component_id=str(raw["component_id"]),
        provider_definition_id=str(raw["provider_definition_id"]),
        name=str(raw["name"]),
        capabilities=tuple(
            AIcProvidedCapability(str(item["id"]), tuple(int(version) for version in item.get("versions", ())))
            for item in raw.get("capabilities", ())
            if isinstance(item, Mapping)
        ),
        implementation_class=str(raw["implementation_class"]),
        access_mode=AInProviderAccessMode(str(raw.get("access_mode", AInProviderAccessMode.READ_WRITE.value))),
        configuration=dict(_as_mapping(raw.get("configuration", {}))),
        configuration_schema=str(raw["configuration_schema"]) if raw.get("configuration_schema") is not None else None,
        state=AInProviderInstanceState(str(raw.get("state", AInProviderInstanceState.CONFIGURED.value))),
    )


def _entitlement_context_from_dict(raw: Mapping[str, object], fallback_component_id: str) -> AIcEntitlementContext:
    capability_contexts = []
    raw_capabilities = raw.get("capabilities", ())
    for raw_capability in raw_capabilities if isinstance(raw_capabilities, (list, tuple)) else ():
        if not isinstance(raw_capability, Mapping):
            continue
        permissions: dict[str, AIcEffectiveEntitlementPermission] = {}
        raw_permissions = raw_capability.get("permissions", {})
        if isinstance(raw_permissions, Mapping):
            for permission_id, raw_permission in raw_permissions.items():
                if not isinstance(raw_permission, Mapping):
                    continue
                provenance_values = []
                raw_provenance = raw_permission.get("provenance", ())
                for item in raw_provenance if isinstance(raw_provenance, (list, tuple)) else ():
                    if not isinstance(item, Mapping):
                        continue
                    scope_raw = item.get("licensing_scope", {})
                    if not isinstance(scope_raw, Mapping):
                        scope_raw = {}
                    scope_type = scope_raw.get("type")
                    if scope_type is None or not str(scope_type).strip():
                        raise ValueError("entitlement provenance licensing_scope requires a non-empty type")
                    scope = AIcEntitlementLicensingScope(
                        str(scope_type),
                        str(scope_raw["id"]) if scope_raw.get("id") is not None else None,
                    )
                    provenance_values.append(AIcEntitlementGrantProvenance(
                        str(item.get("entitlement_provider_id", "")),
                        str(item.get("entitlement_id", "")),
                        str(item.get("issuer_id", "")),
                        scope,
                        str(item.get("capability_id", raw_capability.get("capability_id", ""))),
                        int(item.get("capability_version", raw_capability.get("capability_version", 1))),
                        str(item.get("permission_id", permission_id)),
                        str(item["valid_from"]) if item.get("valid_from") is not None else None,
                        str(item["valid_until"]) if item.get("valid_until") is not None else None,
                    ))
                raw_constraints = raw_permission.get("constraints", ())
                constraints = tuple(dict(v) for v in raw_constraints if isinstance(v, Mapping)) if isinstance(raw_constraints, (list, tuple)) else ()
                permissions[str(permission_id)] = AIcEffectiveEntitlementPermission(
                    str(raw_permission.get("id", permission_id)),
                    str(raw_permission["effective_from"]) if raw_permission.get("effective_from") is not None else None,
                    str(raw_permission["effective_until"]) if raw_permission.get("effective_until") is not None else None,
                    constraints,
                    tuple(provenance_values),
                    bool(raw_permission.get("implicit", False)),
                )
        capability_contexts.append(AIcCapabilityEntitlementContext(
            str(raw_capability.get("capability_id", "")),
            int(raw_capability.get("capability_version", 1)),
            permissions,
        ))
    diagnostics_raw = raw.get("diagnostics", ())
    return AIcEntitlementContext(
        component_id=str(raw.get("component_id", fallback_component_id)),
        capabilities=tuple(capability_contexts),
        next_transition_at=str(raw["next_transition_at"]) if raw.get("next_transition_at") is not None else None,
        diagnostics=tuple(str(v) for v in diagnostics_raw) if isinstance(diagnostics_raw, (list, tuple)) else (),
    )


def _effective_configuration_from_dict(raw: Mapping[str, object]) -> AIcEffectiveConfiguration:
    target_raw = _as_mapping(raw.get("configuration_target", {}))
    target = AIcConfigurationTarget(
        AInConfigurationTargetKind(str(target_raw.get("kind", "COMPONENT"))),
        str(target_raw.get("component_id", "")),
        str(target_raw["provider_instance_id"]) if target_raw.get("provider_instance_id") is not None else None,
    )
    values: dict[str, AIcEffectiveConfigurationValue] = {}
    raw_values = raw.get("values", {})
    if isinstance(raw_values, Mapping):
        for property_id, item in raw_values.items():
            if not isinstance(item, Mapping):
                continue
            policy_raw = item.get("effective_policy", {})
            policy_map = policy_raw if isinstance(policy_raw, Mapping) else {}
            policy = AIcEffectiveConfigurationPolicy(
                lock=policy_map.get("lock"), has_lock=bool(policy_map.get("has_lock", False)),
                minimum=policy_map.get("minimum"), maximum=policy_map.get("maximum"),
                in_set=tuple(policy_map["in_set"]) if isinstance(policy_map.get("in_set"), (list, tuple)) else None,
                not_in_set=tuple(policy_map.get("not_in_set", ())) if isinstance(policy_map.get("not_in_set", ()), (list, tuple)) else (),
                provenance=(),
            )
            values[str(property_id)] = AIcEffectiveConfigurationValue(
                str(item.get("property_id", property_id)), item.get("value"),
                AInConfigurationValueSourceKind(str(item.get("source_kind", "UNDEFINED"))),
                None, policy, (),
            )
    # Resolved scope details are diagnostic here; process providers need effective values/target.
    return AIcEffectiveConfiguration(target, values, ())

def _invocation_from_dict(raw: Mapping[str, object]) -> AIcInvocationInput:
    return AIcInvocationInput(
        invocation_id=str(raw["invocation_id"]),
        parent_invocation_id=str(raw["parent_invocation_id"]) if raw.get("parent_invocation_id") is not None else None,
        capability_id=str(raw["capability_id"]),
        capability_version=int(raw["capability_version"]),
        operation_id=str(raw["operation_id"]),
        provider_instance_id=str(raw["provider_instance_id"]),
        arguments=dict(_as_mapping(raw.get("arguments", {}))),
        consumer_instance_id=str(raw["consumer_instance_id"]) if raw.get("consumer_instance_id") is not None else None,
        requirement_id=str(raw["requirement_id"]) if raw.get("requirement_id") is not None else None,
    )


def _binding_from_dict(raw: Mapping[str, object]) -> AIcBinding:
    return AIcBinding(
        consumer_instance_id=str(raw["consumer_instance_id"]),
        requirement_id=str(raw["requirement_id"]),
        provider_instance_id=str(raw["provider_instance_id"]),
        capability_id=str(raw["capability_id"]),
        capability_version=int(raw["capability_version"]),
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


if __name__ == "__main__":
    raise SystemExit(main())

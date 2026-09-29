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
    binding_qualifier_profiles_context, current_operation_interaction, invocation_locale_context, operation_interaction_context, operation_parameter_context,
)
from .provider import AIcProviderRuntimeContext, AIiProviderRuntime, AIiProviderRuntimeFactory

from .aic_process_capability_handle import AIcProcessCapabilityHandle
from .aic_host_channel import AIcHostChannel
from .aic_process_operation_interaction import AIcProcessOperationInteraction

"""Reference Python host for the AAC process runtime profile.

The host reserves stdin/stdout for the AAC json-lines control protocol.  Component
stdout is redirected to stderr so arbitrary provider output cannot corrupt protocol
frames.  Core may forward that diagnostic stream according to product policy.
"""

from ._process_context import CURRENT_PROCESS_INVOCATION_ID as _CURRENT_PROCESS_INVOCATION_ID

def main() -> int:
    channel = AIcHostChannel()
    runtime: AIiProviderRuntime | None = None
    while True:
        frame = channel.read()
        if frame is None:
            return 0
        kind = str(frame.get("Kind", ""))
        request_id = str(frame.get("RequestId", ""))
        try:
            if kind == "bootstrap":
                runtime = _bootstrap(frame.get("Payload"), channel)
                channel.respond(request_id, success=True, result={"host": "python", "protocol": 1})
            elif kind == "lifecycle":
                if runtime is None:
                    raise RuntimeError("provider runtime has not been bootstrapped")
                result = _lifecycle(runtime, frame.get("Action"), frame.get("Payload"), channel)
                channel.respond(request_id, success=True, result=result)
            elif kind == "invoke":
                if runtime is None:
                    raise RuntimeError("provider runtime has not been bootstrapped")
                invocation = _invocation_from_dict(_as_mapping(frame.get("Payload")))
                output = _invoke_runtime(runtime, invocation, channel)
                channel.respond(request_id, success=True, result=_jsonable(output))
            elif kind == "shutdown":
                channel.respond(request_id, success=True)
                return 0
            else:
                raise ValueError(f"unknown AAC process frame kind {kind!r}")
        except Exception as exc:  # Host must return protocol failures, never traceback on protocol stdout.
            channel.respond(request_id, success=False, error={"Type": type(exc).__name__, "Message": str(exc)})

def _bootstrap(raw_payload: object, channel: AIcHostChannel) -> AIiProviderRuntime:
    payload = _as_mapping(raw_payload)
    instance = _provider_instance_from_dict(_as_mapping(payload["ProviderInstance"]))
    entitlement = _entitlement_context_from_dict(_as_mapping(payload.get("Entitlement", {})), str(instance.component_id))
    component_configuration = _effective_configuration_from_dict(_as_mapping(payload["ComponentConfiguration"]))
    provider_instance_configuration = _effective_configuration_from_dict(_as_mapping(payload["ProviderInstanceConfiguration"]))
    context = AIcProviderRuntimeContext(
        str(payload["ApplicationScopeId"]), instance, entitlement, component_configuration, provider_instance_configuration
    )
    factory_name = payload.get("RuntimeFactoryClass")
    if factory_name:
        factory_class = _load_class(str(factory_name))
        factory = factory_class()
        if not isinstance(factory, AIiProviderRuntimeFactory):
            raise TypeError("runtime factory does not implement AIiProviderRuntimeFactory")
        runtime = factory.create(context)
    else:
        provider_class = _load_class(str(payload["ImplementationClass"]))
        effective_values = provider_instance_configuration.plain_values()
        runtime = provider_class(effective_values if effective_values else dict(instance.configuration))
    if not isinstance(runtime, AIiProviderRuntime):
        raise TypeError("provider implementation does not implement AIiProviderRuntime")
    return runtime

def _lifecycle(runtime: AIiProviderRuntime, action: object, raw_payload: object, channel: AIcHostChannel) -> object:
    action = str(action)
    payload = _as_mapping(raw_payload or {})
    if action == "entitlement_changed":
        runtime.entitlement_changed(_entitlement_context_from_dict(_as_mapping(payload.get("Entitlement", {})), ""))
    elif action == "wire":
        runtime.wire(_build_handles(payload.get("Bindings", {}), channel))
    elif action == "prepare_activation":
        runtime.prepare_activation()
    elif action == "readiness":
        return dataclasses.asdict(runtime.readiness())
    elif action == "activate":
        runtime.activate()
    elif action == "suspend":
        runtime.suspend(str(payload.get("Reason", "")))
    elif action == "deactivate":
        runtime.deactivate(str(payload.get("Reason", "")))
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

def _python_identifier(aExternalName: str) -> str:
    import re
    locValue = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", aExternalName)
    locValue = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", locValue)
    return locValue.replace("-", "_").lower()

def _invoke_runtime(
    runtime: AIiProviderRuntime, invocation: AIcInvocationInput, channel: AIcHostChannel | None = None
) -> AIcInvocationOutput:
    try:
        generated_invoke = _generated_capability_invoker(
            runtime, invocation.capability_id, invocation.capability_version
        )
        token = _CURRENT_PROCESS_INVOCATION_ID.set(invocation.invocation_id)
        try:
            interaction = (
                AIcProcessOperationInteraction(invocation.invocation_id, channel)
                if channel is not None else current_operation_interaction()
            )
            with binding_qualifier_profiles_context(invocation.binding_qualifier_profiles), operation_interaction_context(interaction), operation_parameter_context(
                invocation.effective_operation_parameters
            ), invocation_locale_context(invocation.locale):
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
                                _python_identifier(name): _coerce_value(hints.get(_python_identifier(name)), value)
                                for name, value in invocation.arguments.items()
                            }
                            result = method(**kwargs)
                    else:
                        kwargs = {
                            _python_identifier(name): _coerce_value(hints.get(_python_identifier(name)), value)
                            for name, value in invocation.arguments.items()
                        }
                        result = method(**kwargs)
        finally:
            _CURRENT_PROCESS_INVOCATION_ID.reset(token)
        return AIcInvocationOutput(True, result=_jsonable(result))
    except AIxOperationCancelled as exc:
        return AIcInvocationOutput(False, error={
            "Type": "OPERATION_CANCELLED",
            "Message": str(exc) or "operation cancelled",
            "HasStateResult": exc.has_state_result,
            "StateResult": exc.state_result if exc.has_state_result else None,
        })
    except AIxCapabilityOperationFailed as exc:
        failure = exc.failure
        error: dict[str, object] = {
            "Type": failure.exception_type,
            "Message": failure.system_message,
        }
        if failure.user_message is not None:
            error["UserMessage"] = dataclasses.asdict(failure.user_message)
        if failure.error_code is not None:
            error["ErrorCode"] = failure.error_code
        if failure.stack_trace is not None:
            error["StackTrace"] = failure.stack_trace
        if failure.details:
            error["Details"] = dict(failure.details)
        if failure.extension is not None:
            error["Extension"] = _jsonable(failure.extension)
        return AIcInvocationOutput(False, error=error)
    except AIxPermissionDenied as exc:
        return AIcInvocationOutput(False, error={
            "Type": "PERMISSION_DENIED",
            "Message": str(exc),
            "CapabilityId": exc.capability_id or invocation.capability_id,
            "CapabilityVersion": exc.capability_version or invocation.capability_version,
            "permission_id": exc.permission_id,
            "retry_disposition": exc.retry_disposition.value,
            "remediation_hint": exc.remediation_hint,
        })
    except Exception as exc:
        error: dict[str, object] = {
            "Type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "Message": str(exc) or type(exc).__name__,
        }
        try:
            caller = current_operation_interaction().caller_snapshot()
            if caller.failure_detail_level is AInOperationInteractionFailureDetailLevel.STACK_TRACE:
                error["StackTrace"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        except Exception:
            pass
        return AIcInvocationOutput(False, error=error)

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
        return annotation(**{field.name: _coerce_value(hints.get(field.name), raw.get("".join(part[:1].upper() + part[1:] for part in field.name.split("_")))) for field in dataclasses.fields(annotation)})
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
        id=str(raw["Id"]),
        component_id=str(raw["ComponentId"]),
        provider_definition_id=str(raw["ProviderDefinitionId"]),
        name=str(raw["Name"]),
        capabilities=tuple(
            AIcProvidedCapability(str(item["Id"]), tuple(int(version) for version in item.get("Versions", ())))
            for item in raw.get("Capabilities", ())
            if isinstance(item, Mapping)
        ),
        implementation_class=str(raw["ImplementationClass"]),
        access_mode=AInProviderAccessMode(str(raw.get("AccessMode", AInProviderAccessMode.READ_WRITE.value))),
        configuration=dict(_as_mapping(raw.get("Configuration", {}))),
        configuration_schema=str(raw["ConfigurationSchema"]) if raw.get("ConfigurationSchema") is not None else None,
        state=AInProviderInstanceState(str(raw.get("State", AInProviderInstanceState.CONFIGURED.value))),
    )

def _entitlement_context_from_dict(raw: Mapping[str, object], fallback_component_id: str) -> AIcEntitlementContext:
    capability_contexts = []
    raw_capabilities = raw.get("Capabilities", ())
    for raw_capability in raw_capabilities if isinstance(raw_capabilities, (list, tuple)) else ():
        if not isinstance(raw_capability, Mapping):
            continue
        permissions: dict[str, AIcEffectiveEntitlementPermission] = {}
        raw_permissions = raw_capability.get("Permissions", {})
        if isinstance(raw_permissions, Mapping):
            for permission_id, raw_permission in raw_permissions.items():
                if not isinstance(raw_permission, Mapping):
                    continue
                provenance_values = []
                raw_provenance = raw_permission.get("Provenance", ())
                for item in raw_provenance if isinstance(raw_provenance, (list, tuple)) else ():
                    if not isinstance(item, Mapping):
                        continue
                    scope_raw = item.get("LicensingScope", {})
                    if not isinstance(scope_raw, Mapping):
                        scope_raw = {}
                    scope_type = scope_raw.get("Type")
                    if scope_type is None or not str(scope_type).strip():
                        raise ValueError("entitlement provenance licensing_scope requires a non-empty type")
                    scope = AIcEntitlementLicensingScope(
                        str(scope_type),
                        str(scope_raw["Id"]) if scope_raw.get("Id") is not None else None,
                    )
                    provenance_values.append(AIcEntitlementGrantProvenance(
                        str(item.get("EntitlementProviderId", "")),
                        str(item.get("EntitlementId", "")),
                        str(item.get("IssuerId", "")),
                        scope,
                        str(item.get("CapabilityId", raw_capability.get("CapabilityId", ""))),
                        int(item.get("CapabilityVersion", raw_capability.get("CapabilityVersion", 1))),
                        str(item.get("PermissionId", permission_id)),
                        str(item["ValidFrom"]) if item.get("ValidFrom") is not None else None,
                        str(item["ValidUntil"]) if item.get("ValidUntil") is not None else None,
                    ))
                raw_constraints = raw_permission.get("Constraints", ())
                constraints = tuple(dict(v) for v in raw_constraints if isinstance(v, Mapping)) if isinstance(raw_constraints, (list, tuple)) else ()
                permissions[str(permission_id)] = AIcEffectiveEntitlementPermission(
                    str(raw_permission.get("Id", permission_id)),
                    str(raw_permission["EffectiveFrom"]) if raw_permission.get("EffectiveFrom") is not None else None,
                    str(raw_permission["EffectiveUntil"]) if raw_permission.get("EffectiveUntil") is not None else None,
                    constraints,
                    tuple(provenance_values),
                    bool(raw_permission.get("Implicit", False)),
                )
        capability_contexts.append(AIcCapabilityEntitlementContext(
            str(raw_capability.get("CapabilityId", "")),
            int(raw_capability.get("CapabilityVersion", 1)),
            permissions,
        ))
    diagnostics_raw = raw.get("Diagnostics", ())
    return AIcEntitlementContext(
        component_id=str(raw.get("ComponentId", fallback_component_id)),
        capabilities=tuple(capability_contexts),
        next_transition_at=str(raw["NextTransitionAt"]) if raw.get("NextTransitionAt") is not None else None,
        diagnostics=tuple(str(v) for v in diagnostics_raw) if isinstance(diagnostics_raw, (list, tuple)) else (),
    )

def _effective_configuration_from_dict(raw: Mapping[str, object]) -> AIcEffectiveConfiguration:
    target_raw = _as_mapping(raw.get("ConfigurationTarget", {}))
    target = AIcConfigurationTarget(
        AInConfigurationTargetKind(str(target_raw.get("Kind", "component"))),
        str(target_raw.get("ComponentId", "")),
        str(target_raw["ProviderInstanceId"]) if target_raw.get("ProviderInstanceId") is not None else None,
    )
    values: dict[str, AIcEffectiveConfigurationValue] = {}
    raw_values = raw.get("Values", {})
    if isinstance(raw_values, Mapping):
        for property_id, item in raw_values.items():
            if not isinstance(item, Mapping):
                continue
            policy_raw = item.get("EffectivePolicy", {})
            policy_map = policy_raw if isinstance(policy_raw, Mapping) else {}
            policy = AIcEffectiveConfigurationPolicy(
                lock=policy_map.get("Lock"), has_lock=bool(policy_map.get("HasLock", False)),
                minimum=policy_map.get("Minimum"), maximum=policy_map.get("Maximum"),
                in_set=tuple(policy_map["InSet"]) if isinstance(policy_map.get("InSet"), (list, tuple)) else None,
                not_in_set=tuple(policy_map.get("NotInSet", ())) if isinstance(policy_map.get("NotInSet", ()), (list, tuple)) else (),
                provenance=(),
            )
            values[str(property_id)] = AIcEffectiveConfigurationValue(
                str(item.get("PropertyId", property_id)), item.get("Value"),
                AInConfigurationValueSourceKind(str(item.get("SourceKind", "undefined"))),
                None, policy, (),
            )
    # Resolved scope details are diagnostic here; process providers need effective values/target.
    return AIcEffectiveConfiguration(target, values, ())

def _invocation_from_dict(raw: Mapping[str, object]) -> AIcInvocationInput:
    return AIcInvocationInput.from_mapping(raw)

def _display_text_from_dict(raw: object) -> AIcDisplayText | None:
    if raw is None:
        return None
    value = _as_mapping(raw)
    return AIcDisplayText(
        text=str(value["Text"]) if value.get("Text") is not None else None,
        resource_key=str(value["ResourceKey"]) if value.get("ResourceKey") is not None else None,
    )

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

def _binding_from_dict(raw: Mapping[str, object]) -> AIcBinding:
    return AIcBinding(
        consumer_instance_id=str(raw["ConsumerInstanceId"]),
        requirement_id=str(raw["RequirementId"]),
        provider_instance_id=str(raw["ProviderInstanceId"]),
        capability_id=str(raw["CapabilityId"]),
        capability_version=int(raw["CapabilityVersion"]),
    )

def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("AAC process payload must be an object")
    return value

def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {"".join(part[:1].upper() + part[1:] for part in field.name.split("_")): _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

if __name__ == "__main__":
    raise SystemExit(main())

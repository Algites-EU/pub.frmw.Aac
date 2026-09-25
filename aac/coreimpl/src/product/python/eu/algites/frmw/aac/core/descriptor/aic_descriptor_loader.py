from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from zipfile import ZipFile, BadZipFile, is_zipfile
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcPermissionDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcCapabilityEntitlementDescriptor,
    AIcDataEntityRequirementDescriptor,
    AIcDataEntitySupportDescriptor,
    AIcPersistedSchemaDescriptor,
    AIcSchemaMigrationStepDescriptor,
    AInDataEntityAccess,
    AIcInitialProviderInstanceDescriptor,
    AIcLifecycleHooksDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderImplementationClassDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
    AIcCapabilityProviderOperationDescriptor,
    AIcCapabilityProviderOperationInteractionDescriptor,
    AIcOperationParameterDefinitionDescriptor,
    AIcOperationParameterEnumValueDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.instances.api import AInProviderAccessMode
from eu.algites.frmw.aac.core.interaction_types import AInStateResultDeliveryMode
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.readiness.api import AInReadinessRequirementSource, AInReadinessState, AIcReadinessRequirementDescriptor

from .aic_discovered_component import AIcDiscoveredComponent

def _validate_raw_descriptor(raw: Mapping[str, Any], source: str) -> None:
    try:
        schema_text = read_core_schema("component-descriptor_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
    except Exception as exc:
        raise AIxDescriptorError(f"cannot validate descriptor schema for {source}: {exc}") from exc
    if not errors:
        return
    rendered = []
    for error in errors:
        path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
        rendered.append(f"{path}: {error.message}")
    raise AIxDescriptorError(
        f"{source}: descriptor schema validation failed: " + "; ".join(rendered)
    )

def _parse_persisted_schema(raw_schema: Any) -> AIcPersistedSchemaDescriptor | None:
    if raw_schema is None:
        return None
    if not isinstance(raw_schema, Mapping):
        raise ValueError("persisted schema declaration must be a mapping")
    migrations = tuple(
        AIcSchemaMigrationStepDescriptor(
            from_version=int(item["from"]),
            to_version=int(item["to"]),
            migrator_id=str(item["migrator"]),
        )
        for item in raw_schema.get("migrations", ())
    )
    return AIcPersistedSchemaDescriptor(
        schema_id=str(raw_schema["id"]),
        write_version=int(raw_schema["write_version"]),
        readable_versions=tuple(int(v) for v in raw_schema["readable_versions"]),
        migrations=migrations,
        resource_name=str(raw_schema["resource"]),
    )

def _parse_requirement(raw_requirement: Mapping[str, Any]) -> AIcConsumerRequirementDescriptor:
    return AIcConsumerRequirementDescriptor(
        id=raw_requirement["id"],
        capability_id=raw_requirement["capability"],
        versions=tuple(int(v) for v in raw_requirement.get("versions", ())),
        cardinality=AInConsumerCardinality(raw_requirement.get("cardinality", "SINGLE")),
        mandatory=bool(raw_requirement.get("mandatory", True)),
        requested_authorizations=tuple(str(v) for v in raw_requirement.get("requested_authorizations", ())),
        name=normalize_display_text(raw_requirement.get("name")),
        description=normalize_display_text(raw_requirement.get("description")),
    )

def _parse_component(component: Mapping[str, Any]) -> AIcComponentDescriptor:
    capability_providers = []
    for raw_provider in component.get("capability_providers", ()):
        capabilities = tuple(
            AIcProvidedCapability(
                id=str(item["id"]),
                versions=tuple(sorted({int(version) for version in item["versions"]})),
            )
            for item in raw_provider["capabilities"]
        )
        initial_instances = tuple(
            AIcInitialProviderInstanceDescriptor(
                name=item.get("name", "default"),
                configuration=item.get("configuration", {}),
                access_mode=AInProviderAccessMode(str(item.get("access_mode", "READ_WRITE"))),
            )
            for item in raw_provider.get("initial_instances", ())
        )
        requirements = tuple(_parse_requirement(item) for item in raw_provider.get("requirements", ()))
        provider_operations = tuple(
            AIcCapabilityProviderOperationDescriptor(
                capability_id=str(item["capability"]),
                capability_version=int(item["capability_version"]),
                operation_id=str(item["operation"]),
                interaction=AIcCapabilityProviderOperationInteractionDescriptor(
                    supported_state_result_delivery_modes=tuple(
                        AInStateResultDeliveryMode(str(value))
                        for value in item["interaction"]["supported_state_result_delivery_modes"]
                    ),
                    progress_reporting=bool(item["interaction"].get("progress_reporting", False)),
                    cancellation=bool(item["interaction"].get("cancellation", False)),
                    detail_level=bool(item["interaction"].get("detail_level", False)),
                    reporting_interval=bool(item["interaction"].get("reporting_interval", False)),
                ),
                parameters=tuple(
                    AIcOperationParameterDefinitionDescriptor(
                        id=str(parameter["id"]),
                        name=normalize_display_text(parameter["name"]),
                        description=normalize_display_text(parameter["description"]),
                        value_schema=dict(parameter["value_schema"]),
                        enum_values=tuple(
                            AIcOperationParameterEnumValueDescriptor(
                                value=enum_item.get("value"),
                                name=normalize_display_text(enum_item["name"]),
                                description=normalize_display_text(enum_item.get("description")),
                            )
                            for enum_item in parameter.get("enum_values", ())
                        ),
                        required=bool(parameter.get("required", False)),
                        default=parameter.get("default"),
                        has_default="default" in parameter,
                        component_configurable=bool(parameter.get("component_configurable", False)),
                        instance_configurable=bool(parameter.get("instance_configurable", False)),
                        invocation_overridable=bool(parameter.get("invocation_overridable", False)),
                    )
                    for parameter in item.get("parameters", ())
                ),
            )
            for item in raw_provider.get("operations", ())
        )
        raw_runtime = raw_provider.get("runtime", {}) or {}
        runtime = AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile(raw_runtime.get("profile", "IN_PROCESS")),
            command=tuple(str(v) for v in raw_runtime.get("command", ())),
            cwd=str(raw_runtime["cwd"]) if raw_runtime.get("cwd") is not None else None,
            environment={str(k): str(v) for k, v in raw_runtime.get("environment", {}).items()},
            timeout_seconds=float(raw_runtime.get("timeout_seconds", 30.0)),
        )
        readiness_requirements = tuple(
            AIcReadinessRequirementDescriptor(
                id=str(item["id"]),
                source=AInReadinessRequirementSource(str(item["source"])),
                key=str(item["key"]),
                missing_state=AInReadinessState(str(item.get("missing_state", "NOT_READY"))),
                message=(str(item["message"]) if item.get("message") is not None else None),
            )
            for item in raw_provider.get("readiness_requirements", ())
        )
        capability_providers.append(AIcProviderDefinitionDescriptor(
            id=raw_provider["id"],
            capabilities=capabilities,
            implementation_classes=tuple(
                AIcProviderImplementationClassDescriptor(
                    technology_kind=str(item["technology-kind"]),
                    class_name=str(item["class-name"]),
                )
                for item in raw_provider["implementation_classes"]
            ),
            name=normalize_display_text(raw_provider.get("name")),
            description=normalize_display_text(raw_provider.get("description")),
            configuration_schema=_parse_persisted_schema(raw_provider.get("configuration_schema")),
            initial_instances=initial_instances,
            requirements=requirements,
            operations=provider_operations,
            readiness_requirements=readiness_requirements,
            runtime_factory_class=raw_provider.get("runtime_factory_class"),
            runtime=runtime,
        ))

    entitlement_licensing_scopes = tuple(
        AIcEntitlementLicensingScopeDescriptor(
            type=str(item["type"]),
            name=normalize_display_text(item.get("name")),
            description=normalize_display_text(item.get("description")),
            metadata=dict(item.get("metadata", {})),
        )
        for item in component.get("entitlement_licensing_scopes", ())
    )

    provided_capability_entitlements = []
    for raw_capability in component.get("provided_capability_entitlements", ()):
        permissions = tuple(
            AIcPermissionDescriptor(
                id=item["id"],
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
                possible_licensing_scope_types=tuple(
                    str(v) for v in item.get("possible_licensing_scopes", ())
                ),
                metadata=item.get("metadata", {}),
            )
            for item in raw_capability.get("permissions", ())
        )
        provided_capability_entitlements.append(AIcCapabilityEntitlementDescriptor(
            capability_id=raw_capability["capability"]["id"],
            capability_version=int(raw_capability["capability"]["version"]),
            permissions=permissions,
            name=normalize_display_text(raw_capability.get("name")),
            description=normalize_display_text(raw_capability.get("description")),
        ))


    data_entity_support = []
    for raw_support in component.get("data_entity_support", ()):
        migrations = tuple(
            AIcSchemaMigrationStepDescriptor(
                from_version=int(item["from"]),
                to_version=int(item["to"]),
                migrator_id=str(item["migrator"]),
            )
            for item in raw_support.get("migrations", ())
        )
        requirements = tuple(
            AIcDataEntityRequirementDescriptor(
                schema_id=str(item["schema_id"]),
                access=tuple(AInDataEntityAccess(str(value)) for value in item.get("access", ())),
                readable_versions=tuple(int(value) for value in item.get("readable_versions", ())),
                writable_versions=tuple(int(value) for value in item.get("writable_versions", ())),
                required=bool(item.get("required", True)),
            )
            for item in raw_support.get("data_entity_requirements", ())
        )
        data_entity_support.append(AIcDataEntitySupportDescriptor(
            schema_id=str(raw_support["schema_id"]),
            readable_versions=tuple(int(value) for value in raw_support.get("readable_versions", ())),
            writable_versions=tuple(int(value) for value in raw_support.get("writable_versions", ())),
            preferred_write_version=(
                int(raw_support["preferred_write_version"])
                if raw_support.get("preferred_write_version") is not None else None
            ),
            migrations=migrations,
            data_entity_requirements=requirements,
            name=normalize_display_text(raw_support.get("name")),
            description=normalize_display_text(raw_support.get("description")),
            metadata=dict(raw_support.get("metadata", {})),
        ))

    raw_lifecycle = component.get("lifecycle", {}) or {}
    lifecycle = AIcLifecycleHooksDescriptor(**{
        name: raw_lifecycle.get(name)
        for name in ("provision", "validate", "unprovision")
    })
    return AIcComponentDescriptor(
        id=component["id"],
        version=int(component["version"]),
        name=normalize_display_text(component.get("name")),
        description=normalize_display_text(component.get("description")),
        capability_providers=tuple(capability_providers),
        capability_group_resources=tuple(str(v) for v in component.get("capability_groups", ())),
        contract_resources=tuple(str(v) for v in component.get("capability", ())),
        component_configuration_schema=_parse_persisted_schema(component.get("component_configuration_schema")),
        entitlement_licensing_scopes=entitlement_licensing_scopes,
        provided_capability_entitlements=tuple(provided_capability_entitlements),
        data_entity_support=tuple(data_entity_support),
        lifecycle=lifecycle,
        metadata=component.get("metadata", {}),
    )

class AIcDescriptorLoader:
    @staticmethod
    def load_file(path: str | Path) -> AIcComponentDescriptor:
        path = Path(path)
        return AIcDescriptorLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_package(package: str, resource_name: str = "component.yml") -> AIcComponentDescriptor:
        return AIcDescriptorLoader.discover_package(package, resource_name).descriptor

    @staticmethod
    def discover_package(package: str, resource_name: str = "component.yml", *, artifact_path: str | None = None) -> AIcDiscoveredComponent:
        # When an explicit wheel is supplied, descriptor discovery must not resolve through an
        # already-imported package of another version.  Read the candidate artifact directly.
        if artifact_path is not None:
            artifact = Path(artifact_path)
            if artifact.is_file() and is_zipfile(artifact):
                return AIcDescriptorLoader.discover_wheel(artifact, package, resource_name)
        try:
            text = resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise AIxDescriptorError(f"cannot read {resource_name!r} from package {package!r}") from exc
        source = f"{package}:{resource_name}"
        return AIcDiscoveredComponent(AIcDescriptorLoader.load_text(text, source=source), package, source, artifact_path)

    @staticmethod
    def discover_wheel(wheel_path: str | Path, package: str, resource_name: str = "component.yml") -> AIcDiscoveredComponent:
        wheel = Path(wheel_path)
        member = package.replace(".", "/") + "/" + resource_name
        try:
            with ZipFile(wheel) as archive:
                text = archive.read(member).decode("utf-8")
        except (OSError, BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise AIxDescriptorError(f"cannot read {member!r} from wheel {wheel}: {exc}") from exc
        source = f"{wheel}!/{member}"
        return AIcDiscoveredComponent(AIcDescriptorLoader.load_text(text, source=source), package, source, str(wheel))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcComponentDescriptor:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: descriptor root must be a mapping")
        _validate_raw_descriptor(raw, source)
        try:
            return _parse_component(raw["component"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid component descriptor: {exc}") from exc

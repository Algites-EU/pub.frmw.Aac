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
from .aic_descriptor_loader import AIcDescriptorLoader

def _validate_raw_descriptor(raw: Mapping[str, Any], source: str) -> None:
    try:
        schema_text = read_core_schema("component-descriptor_1.jsondef.schema.json")
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
            from_version=int(item["From"]),
            to_version=int(item["To"]),
            migrator_id=str(item["Migrator"]),
        )
        for item in raw_schema.get("Migrations", ())
    )
    return AIcPersistedSchemaDescriptor(
        schema_id=str(raw_schema["Id"]),
        write_version=int(raw_schema["WriteVersion"]),
        readable_versions=tuple(int(v) for v in raw_schema["ReadableVersions"]),
        migrations=migrations,
        resource_name=str(raw_schema["Resource"]),
    )

def _parse_requirement(raw_requirement: Mapping[str, Any]) -> AIcConsumerRequirementDescriptor:
    return AIcConsumerRequirementDescriptor(
        id=raw_requirement["Id"],
        capability_id=raw_requirement["Capability"],
        versions=tuple(int(v) for v in raw_requirement.get("Versions", ())),
        cardinality=AInConsumerCardinality(raw_requirement.get("Cardinality", "single")),
        mandatory=bool(raw_requirement.get("Mandatory", True)),
        requested_authorizations=tuple(str(v) for v in raw_requirement.get("RequestedAuthorizations", ())),
        name=normalize_display_text(raw_requirement.get("Name")),
        description=normalize_display_text(raw_requirement.get("Description")),
    )

def _parse_component(component: Mapping[str, Any]) -> AIcComponentDescriptor:
    capability_providers = []
    for raw_provider in component.get("CapabilityProviders", ()):
        capabilities = tuple(
            AIcProvidedCapability(
                id=str(item["Id"]),
                versions=tuple(sorted({int(version) for version in item["Versions"]})),
                binding_qualifier_profiles=tuple(dict(value) for value in item.get("BindingQualifierProfiles", ())),
            )
            for item in raw_provider["Capabilities"]
        )
        initial_instances = tuple(
            AIcInitialProviderInstanceDescriptor(
                name=item.get("Name", "default"),
                configuration=item.get("Configuration", {}),
                access_mode=AInProviderAccessMode(str(item.get("AccessMode", "read_write"))),
            )
            for item in raw_provider.get("InitialInstances", ())
        )
        requirements = tuple(_parse_requirement(item) for item in raw_provider.get("Requirements", ()))
        provider_operations = tuple(
            AIcCapabilityProviderOperationDescriptor(
                capability_id=str(item["Capability"]),
                capability_version=int(item["CapabilityVersion"]),
                operation_id=str(item["Operation"]),
                interaction=AIcCapabilityProviderOperationInteractionDescriptor(
                    supported_state_result_delivery_modes=tuple(
                        AInStateResultDeliveryMode(str(value))
                        for value in item["Interaction"]["SupportedStateResultDeliveryModes"]
                    ),
                    progress_reporting=bool(item["Interaction"].get("ProgressReporting", False)),
                    cancellation=bool(item["Interaction"].get("Cancellation", False)),
                    detail_level=bool(item["Interaction"].get("DetailLevel", False)),
                    reporting_interval=bool(item["Interaction"].get("ReportingInterval", False)),
                ),
                parameters=tuple(
                    AIcOperationParameterDefinitionDescriptor(
                        id=str(parameter["Id"]),
                        name=normalize_display_text(parameter["Name"]),
                        description=normalize_display_text(parameter["Description"]),
                        value_schema=dict(parameter["ValueSchema"]),
                        enum_values=tuple(
                            AIcOperationParameterEnumValueDescriptor(
                                value=enum_item.get("Value"),
                                name=normalize_display_text(enum_item["Name"]),
                                description=normalize_display_text(enum_item.get("Description")),
                            )
                            for enum_item in parameter.get("EnumValues", ())
                        ),
                        required=bool(parameter.get("Required", False)),
                        default=parameter.get("Default"),
                        has_default="Default" in parameter,
                        component_configurable=bool(parameter.get("ComponentConfigurable", False)),
                        instance_configurable=bool(parameter.get("InstanceConfigurable", False)),
                        invocation_overridable=bool(parameter.get("InvocationOverridable", False)),
                    )
                    for parameter in item.get("Parameters", ())
                ),
            )
            for item in raw_provider.get("Operations", ())
        )
        raw_runtime = raw_provider.get("Runtime", {}) or {}
        runtime = AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile(raw_runtime.get("Profile", "in_process")),
            command=tuple(str(v) for v in raw_runtime.get("Command", ())),
            cwd=str(raw_runtime["Cwd"]) if raw_runtime.get("Cwd") is not None else None,
            environment={str(k): str(v) for k, v in raw_runtime.get("Environment", {}).items()},
            timeout_seconds=float(raw_runtime.get("TimeoutSeconds", 30.0)),
        )
        readiness_requirements = tuple(
            AIcReadinessRequirementDescriptor(
                id=str(item["Id"]),
                source=AInReadinessRequirementSource(str(item["Source"])),
                key=str(item["Key"]),
                missing_state=AInReadinessState(str(item.get("MissingState", "not_ready"))),
                message=(str(item["Message"]) if item.get("Message") is not None else None),
            )
            for item in raw_provider.get("ReadinessRequirements", ())
        )
        capability_providers.append(AIcProviderDefinitionDescriptor(
            id=raw_provider["Id"],
            capabilities=capabilities,
            implementation_classes=tuple(
                AIcProviderImplementationClassDescriptor(
                    technology_kind=str(item["TechnologyKind"]),
                    provider_class_name=str(item["ProviderClassName"]),
                    capability_profile_matcher_class_name=(
                        str(item["CapabilityProfileMatcherClassName"])
                        if item.get("CapabilityProfileMatcherClassName") is not None else None
                    ),
                )
                for item in raw_provider["ImplementationClasses"]
            ),
            name=normalize_display_text(raw_provider.get("Name")),
            description=normalize_display_text(raw_provider.get("Description")),
            configuration_schema=_parse_persisted_schema(raw_provider.get("ConfigurationSchema")),
            initial_instances=initial_instances,
            requirements=requirements,
            operations=provider_operations,
            readiness_requirements=readiness_requirements,
            runtime_factory_class=raw_provider.get("RuntimeFactoryClass"),
            runtime=runtime,
        ))

    entitlement_licensing_scopes = tuple(
        AIcEntitlementLicensingScopeDescriptor(
            type=str(item["Type"]),
            name=normalize_display_text(item.get("Name")),
            description=normalize_display_text(item.get("Description")),
            metadata=dict(item.get("Metadata", {})),
        )
        for item in component.get("EntitlementLicensingScopes", ())
    )

    provided_capability_entitlements = []
    for raw_capability in component.get("ProvidedCapabilityEntitlements", ()):
        permissions = tuple(
            AIcPermissionDescriptor(
                id=item["Id"],
                name=normalize_display_text(item.get("Name")),
                description=normalize_display_text(item.get("Description")),
                possible_licensing_scope_types=tuple(
                    str(v) for v in item.get("PossibleLicensingScopes", ())
                ),
                metadata=item.get("Metadata", {}),
            )
            for item in raw_capability.get("Permissions", ())
        )
        provided_capability_entitlements.append(AIcCapabilityEntitlementDescriptor(
            capability_id=raw_capability["Capability"]["Id"],
            capability_version=int(raw_capability["Capability"]["Version"]),
            permissions=permissions,
            name=normalize_display_text(raw_capability.get("Name")),
            description=normalize_display_text(raw_capability.get("Description")),
        ))


    data_entity_support = []
    for raw_support in component.get("DataEntitySupport", ()):
        migrations = tuple(
            AIcSchemaMigrationStepDescriptor(
                from_version=int(item["From"]),
                to_version=int(item["To"]),
                migrator_id=str(item["Migrator"]),
            )
            for item in raw_support.get("Migrations", ())
        )
        requirements = tuple(
            AIcDataEntityRequirementDescriptor(
                schema_id=str(item["SchemaId"]),
                access=tuple(AInDataEntityAccess(str(value)) for value in item.get("Access", ())),
                readable_versions=tuple(int(value) for value in item.get("ReadableVersions", ())),
                writable_versions=tuple(int(value) for value in item.get("WritableVersions", ())),
                required=bool(item.get("Required", True)),
            )
            for item in raw_support.get("DataEntityRequirements", ())
        )
        data_entity_support.append(AIcDataEntitySupportDescriptor(
            schema_id=str(raw_support["SchemaId"]),
            readable_versions=tuple(int(value) for value in raw_support.get("ReadableVersions", ())),
            writable_versions=tuple(int(value) for value in raw_support.get("WritableVersions", ())),
            preferred_write_version=(
                int(raw_support["PreferredWriteVersion"])
                if raw_support.get("PreferredWriteVersion") is not None else None
            ),
            migrations=migrations,
            data_entity_requirements=requirements,
            name=normalize_display_text(raw_support.get("Name")),
            description=normalize_display_text(raw_support.get("Description")),
            metadata=dict(raw_support.get("Metadata", {})),
        ))

    raw_lifecycle = component.get("Lifecycle", {}) or {}
    lifecycle = AIcLifecycleHooksDescriptor(**{
        name: raw_lifecycle.get(name)
        for name in ("provision", "validate", "unprovision")
    })
    return AIcComponentDescriptor(
        id=component["Id"],
        version=int(component["Version"]),
        name=normalize_display_text(component.get("Name")),
        description=normalize_display_text(component.get("Description")),
        capability_providers=tuple(capability_providers),
        capability_group_resources=tuple(str(v) for v in component.get("CapabilityGroups", ())),
        contract_resources=tuple(str(v) for v in component.get("Capability", ())),
        component_configuration_schema=_parse_persisted_schema(component.get("ComponentConfigurationSchema")),
        entitlement_licensing_scopes=entitlement_licensing_scopes,
        provided_capability_entitlements=tuple(provided_capability_entitlements),
        data_entity_support=tuple(data_entity_support),
        lifecycle=lifecycle,
        metadata=component.get("Metadata", {}),
    )

def read_discovered_resource(discovered: AIcDiscoveredComponent, resource_name: str) -> tuple[str, str]:
    """Read a component resource from its exact candidate artifact when available."""
    if discovered.package is None:
        raise FileNotFoundError("component has no Python package identity")
    if discovered.artifact_path is not None:
        artifact = Path(discovered.artifact_path)
        if artifact.is_file() and is_zipfile(artifact):
            member = discovered.package.replace(".", "/") + "/" + resource_name.lstrip("/")
            try:
                with ZipFile(artifact) as archive:
                    return archive.read(member).decode("utf-8"), f"{artifact}!/{member}"
            except (OSError, BadZipFile, KeyError, UnicodeDecodeError) as exc:
                raise FileNotFoundError(f"cannot read {member!r} from wheel {artifact}: {exc}") from exc
    try:
        text = resources.files(discovered.package).joinpath(resource_name).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        raise FileNotFoundError(
            f"cannot read {resource_name!r} from package {discovered.package!r}"
        ) from exc
    return text, f"{discovered.package}:{resource_name}"

def iter_discovered_resources(
    discovered: AIcDiscoveredComponent, directory: str, *, suffix: str | None = None
) -> tuple[tuple[str, str, str], ...]:
    """Return ``(name, text, source)`` resources from the exact candidate package."""
    if discovered.package is None:
        return ()
    normalized_directory = directory.strip("/")
    if discovered.artifact_path is not None:
        artifact = Path(discovered.artifact_path)
        if artifact.is_file() and is_zipfile(artifact):
            prefix = discovered.package.replace(".", "/") + "/" + normalized_directory + "/"
            result: list[tuple[str, str, str]] = []
            try:
                with ZipFile(artifact) as archive:
                    for member in sorted(archive.namelist()):
                        if not member.startswith(prefix) or member.endswith("/"):
                            continue
                        relative = member[len(prefix):]
                        if "/" in relative:
                            continue
                        if suffix is not None and not relative.endswith(suffix):
                            continue
                        result.append((relative, archive.read(member).decode("utf-8"), f"{artifact}!/{member}"))
            except (OSError, BadZipFile, UnicodeDecodeError) as exc:
                raise FileNotFoundError(f"cannot enumerate {directory!r} in wheel {artifact}: {exc}") from exc
            return tuple(result)
    try:
        resource_directory = resources.files(discovered.package).joinpath(normalized_directory)
        if not resource_directory.is_dir():
            return ()
        return tuple(
            (item.name, item.read_text(encoding="utf-8"), f"{discovered.package}:{normalized_directory}/{item.name}")
            for item in sorted(resource_directory.iterdir(), key=lambda candidate: candidate.name)
            if item.is_file() and (suffix is None or item.name.endswith(suffix))
        )
    except (ModuleNotFoundError, FileNotFoundError):
        return ()

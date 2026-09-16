from __future__ import annotations

from .schema_resources import read_core_schema

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from zipfile import ZipFile, BadZipFile, is_zipfile
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import (
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcPermissionDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcCapabilityEntitlementDescriptor,
    AIcEntityExtensionDescriptor,
    AIcEntityExtensionDataDescriptor,
    AIcPersistedSchemaDescriptor,
    AIcSchemaMigrationStepDescriptor,
    AIcCoreEntitySchemaCompatibilityDescriptor,
    AInEntityExtensionDataAccess,
    AInCoreEntityAccess,
    AIcInitialProviderInstanceDescriptor,
    AIcLifecycleHooksDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
)
from algites.lib.aac.coreintf.errors import AIxDescriptorError
from algites.lib.aac.coreintf.presentation import normalize_display_text
from algites.lib.aac.coreintf.readiness import AInReadinessRequirementSource, AInReadinessState, AIcReadinessRequirementDescriptor


@dataclass(frozen=True, slots=True)
class AIcDiscoveredComponent:
    descriptor: AIcComponentDescriptor
    package: str | None
    source: str
    artifact_path: str | None = None


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
        descriptor_schema_version = _validate_raw_descriptor(raw, source)
        try:
            return _parse_component(raw["component"], descriptor_schema_version=descriptor_schema_version)
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid component descriptor: {exc}") from exc


def _validate_raw_descriptor(raw: Mapping[str, Any], source: str) -> int:
    validation_failures = []
    for schema_version in (5, 4, 3):
        try:
            schema_text = read_core_schema(f"component-descriptor_{schema_version}.json")
            schema = json.loads(schema_text)
            errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        except Exception as exc:
            raise AIxDescriptorError(f"cannot validate descriptor schema for {source}: {exc}") from exc
        if not errors:
            return schema_version
        validation_failures.append((schema_version, errors))
    rendered = []
    schema_version, errors = validation_failures[0]
    for error in errors:
        path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
        rendered.append(f"{path}: {error.message}")
    raise AIxDescriptorError(
        f"{source}: descriptor schema validation failed for current schema {schema_version}: " + "; ".join(rendered)
    )


def _parse_persisted_schema(raw_schema: Any) -> AIcPersistedSchemaDescriptor | None:
    if raw_schema is None:
        return None
    if isinstance(raw_schema, str):
        name = Path(raw_schema).name
        import re
        match = re.match(r"^(?P<id>.+)_(?P<version>[1-9][0-9]*)\.json$", name)
        if match is None:
            raise ValueError(f"schema resource {raw_schema!r} must end in _<version>.json")
        version = int(match.group("version"))
        return AIcPersistedSchemaDescriptor(
            schema_id=match.group("id"),
            write_version=version,
            readable_versions=(version,),
            resource_name=raw_schema,
        )
    if not isinstance(raw_schema, Mapping):
        raise ValueError("persisted schema declaration must be string or mapping")
    migrations = tuple(
        AIcSchemaMigrationStepDescriptor(
            from_version=int(item["from"]),
            to_version=int(item["to"]),
            migrator_id=str(item["migrator"]),
        )
        for item in raw_schema.get("migrations", ())
    )
    write_version = int(raw_schema["write_version"])
    readable = tuple(int(v) for v in raw_schema.get("readable_versions", (write_version,)))
    return AIcPersistedSchemaDescriptor(
        schema_id=str(raw_schema["id"]),
        write_version=write_version,
        readable_versions=readable,
        migrations=migrations,
        resource_name=str(raw_schema["resource"]) if raw_schema.get("resource") is not None else None,
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


def _parse_component(component: Mapping[str, Any], *, descriptor_schema_version: int = 5) -> AIcComponentDescriptor:
    providers = []
    for raw_provider in component.get("providers", ()):
        capability = raw_provider["capability"]
        versions = capability.get("versions")
        if versions is None:
            versions = (int(capability["version"]),)
        else:
            versions = tuple(sorted({int(v) for v in versions}))
        initial_instances = tuple(
            AIcInitialProviderInstanceDescriptor(
                name=item.get("name", "default"),
                configuration=item.get("configuration", {}),
            )
            for item in raw_provider.get("initial_instances", ())
        )
        requirements = tuple(_parse_requirement(item) for item in raw_provider.get("requirements", ()))
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
        providers.append(AIcProviderDefinitionDescriptor(
            id=raw_provider["id"],
            capability_id=capability["id"],
            capability_versions=tuple(versions),
            implementation_class=raw_provider["implementation_class"],
            name=normalize_display_text(raw_provider.get("name")),
            description=normalize_display_text(raw_provider.get("description")),
            configuration_schema=_parse_persisted_schema(raw_provider.get("configuration_schema")),
            initial_instances=initial_instances,
            requirements=requirements,
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
    entitlement_key = "provided_capability_entitlements" if descriptor_schema_version >= 5 else "capability_entitlements"
    for raw_capability in component.get(entitlement_key, ()):
        permissions = tuple(
            AIcPermissionDescriptor(
                id=item["id"],
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
                possible_licensing_scope_types=tuple(
                    str(v) for v in (
                        item.get("possible_licensing_scopes", ())
                        if descriptor_schema_version >= 4
                        else item.get("possible_entitlement_scopes", ())
                    )
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

    if descriptor_schema_version < 4 and not entitlement_licensing_scopes:
        legacy_scope_types = sorted({
            scope_type
            for entitlement in provided_capability_entitlements
            for permission in entitlement.permissions
            for scope_type in permission.possible_licensing_scope_types
        })
        entitlement_licensing_scopes = tuple(
            AIcEntitlementLicensingScopeDescriptor(type=scope_type) for scope_type in legacy_scope_types
        )

    entity_extensions = []
    for raw_extension in component.get("entity_extensions", ()):
        raw_data = raw_extension.get("extension_data", {}) or {}
        compatible_core_schemas = tuple(
            AIcCoreEntitySchemaCompatibilityDescriptor(
                schema_id=str(item["schema_id"]),
                readable_versions=tuple(int(v) for v in item.get("readable_versions", ())),
            )
            for item in raw_data.get("compatible_core_entity_schemas", ())
        )
        extension_data = AIcEntityExtensionDataDescriptor(
            access=AInEntityExtensionDataAccess(raw_data.get("access", "NONE")),
            component_extension_schema=_parse_persisted_schema(raw_data.get("component_extension_schema")),
            compatible_core_entity_schemas=compatible_core_schemas,
        )
        entity_extensions.append(AIcEntityExtensionDescriptor(
            entity_type_id=raw_extension["entity_type_id"],
            name=normalize_display_text(raw_extension.get("name")),
            description=normalize_display_text(raw_extension.get("description")),
            core_entity_access=tuple(AInCoreEntityAccess(str(v)) for v in raw_extension.get("core_entity_access", ("READ",))),
            extension_data=extension_data,
            ui=raw_extension.get("ui", {}),
            metadata=raw_extension.get("metadata", {}),
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
        providers=tuple(providers),
        contract_resources=tuple(str(v) for v in component.get("contracts", ())),
        component_configuration_schema=_parse_persisted_schema(component.get("component_configuration_schema")),
        entitlement_licensing_scopes=entitlement_licensing_scopes,
        provided_capability_entitlements=tuple(provided_capability_entitlements),
        entity_extensions=tuple(entity_extensions),
        lifecycle=lifecycle,
        metadata=component.get("metadata", {}),
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

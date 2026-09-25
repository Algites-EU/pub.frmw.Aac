from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.authentication.api import AIcAuthenticationMaterial
from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogArtifact,
    AIcCatalogArtifactLocator,
    AIcCatalogCapabilityOffer,
    AIcCatalogCapabilityRequirement,
    AIcCatalogComponent,
    AIcCatalogDocument,
    AIcCatalogEntry,
    AIcCatalogIcon,
    AIcCatalogPublisher,
    AIcCatalogQuery,
    AIcCatalogRelease,
    AIcCatalogPersistentSchema,
    AInCatalogPersistentSchemaKind,
    AIiCatalogProvider,
)
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxPackageManagementError
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.packages.api import AIcPackageSidecar
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService

def _render_validation_errors(errors) -> str:
    rendered = []
    for error in errors:
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
        rendered.append(f"{path}: {error.message}")
    return "; ".join(rendered)

def _resolve_relative_uri(base_uri: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme:
        return value
    base = urlparse(base_uri)
    if base.scheme in {"http", "https", "file"}:
        return urljoin(base_uri, value)
    return str((Path(base_uri).parent / value).resolve())

class AIcCatalogDocumentLoader:
    @staticmethod
    def load_text(text: str, *, source: str = "<memory>", source_uri: str | None = None) -> AIcCatalogDocument:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxPackageManagementError(f"invalid catalog document {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxPackageManagementError(f"catalog document {source} root must be an object")
        body_probe = raw.get("catalog")
        if not isinstance(body_probe, Mapping):
            raise AIxPackageManagementError(f"catalog document {source} requires catalog object")
        format_version = int(body_probe.get("format_version", 0))
        if format_version != 1:
            raise AIxPackageManagementError(f"catalog document {source} has unsupported format_version {format_version}; expected 1")
        schema_text = read_core_schema("catalog_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            raise AIxPackageManagementError(
                f"catalog document {source} schema validation failed: {_render_validation_errors(errors)}"
            )
        body = raw["catalog"]
        components: list[AIcCatalogComponent] = []
        for raw_component in body.get("components", ()):
            releases: list[AIcCatalogRelease] = []
            for raw_release in raw_component.get("releases", ()):
                provides = tuple(AIcCatalogCapabilityOffer(
                    str(item["capability"]), tuple(int(version) for version in item.get("versions", ()))
                ) for item in raw_release.get("provides", ()))
                requires = tuple(AIcCatalogCapabilityRequirement(
                    id=str(item["id"]),
                    capability_id=str(item["capability"]),
                    versions=tuple(int(version) for version in item.get("versions", ())),
                    cardinality=AInConsumerCardinality(str(item.get("cardinality", "SINGLE"))),
                    mandatory=bool(item.get("mandatory", True)),
                ) for item in raw_release.get("requires", ()))
                entitlement_licensing_scopes = tuple(
                    AIcEntitlementLicensingScopeDescriptor(
                        type=str(item["type"]),
                        name=normalize_display_text(item.get("name")),
                        description=normalize_display_text(item.get("description")),
                        metadata=dict(item.get("metadata", {})),
                    )
                    for item in raw_release.get("entitlement_licensing_scopes", ())
                )
                entitlements = []
                for raw_entitlement in raw_release.get("provided_capability_entitlements", ()):
                    permissions = tuple(AIcPermissionDescriptor(
                        id=str(item["id"]),
                        name=normalize_display_text(item.get("name")),
                        description=normalize_display_text(item.get("description")),
                        possible_licensing_scope_types=tuple(
                            str(value) for value in item.get("possible_licensing_scopes", ())
                        ),
                        metadata=dict(item.get("metadata", {})),
                    ) for item in raw_entitlement.get("permissions", ()))
                    entitlements.append(AIcCapabilityEntitlementDescriptor(
                        capability_id=str(raw_entitlement["capability"]["id"]),
                        capability_version=int(raw_entitlement["capability"]["version"]),
                        permissions=permissions,
                        name=normalize_display_text(raw_entitlement.get("name")),
                        description=normalize_display_text(raw_entitlement.get("description")),
                    ))
                artifacts = []
                for raw_artifact in raw_release.get("artifacts", ()):
                    raw_locator = raw_artifact["locator"]
                    locator_uri = str(raw_locator["uri"]) if raw_locator.get("uri") is not None else None
                    if locator_uri is not None and source_uri is not None:
                        locator_uri = _resolve_relative_uri(source_uri, locator_uri)
                    sidecars = tuple(AIcPackageSidecar(
                        uri=(_resolve_relative_uri(source_uri, str(item["uri"])) if source_uri is not None else str(item["uri"])),
                        suffix=str(item["suffix"]),
                        name=normalize_display_text(item.get("name")),
                        description=normalize_display_text(item.get("description")),
                    ) for item in raw_artifact.get("sidecars", ()))
                    artifacts.append(AIcCatalogArtifact(
                        id=str(raw_artifact["id"]),
                        locator=AIcCatalogArtifactLocator(
                            type=str(raw_locator["type"]),
                            uri=locator_uri,
                            repository_id=(str(raw_locator["repository_id"]) if raw_locator.get("repository_id") is not None else None),
                            coordinates=dict(raw_locator.get("coordinates", {})),
                        ),
                        artifact_filename=str(raw_artifact["artifact_filename"]),
                        package_format=str(raw_artifact["package_format"]),
                        descriptor_path=str(raw_artifact["descriptor_path"]),
                        sha256=str(raw_artifact["sha256"]),
                        runtime_package=(str(raw_artifact["runtime_package"]) if raw_artifact.get("runtime_package") is not None else None),
                        verifier_id=(str(raw_artifact["verifier_id"]) if raw_artifact.get("verifier_id") is not None else None),
                        authentication_profile_id=(str(raw_artifact["authentication_profile_id"]) if raw_artifact.get("authentication_profile_id") is not None else None),
                        sidecars=sidecars,
                        platforms=tuple(str(value) for value in raw_artifact.get("platforms", ())),
                        architectures=tuple(str(value) for value in raw_artifact.get("architectures", ())),
                        metadata=dict(raw_artifact.get("metadata", {})),
                    ))
                persistent_schemas = []
                for item in raw_release.get("persistent_schemas", ()):
                    kind = AInCatalogPersistentSchemaKind(str(item["kind"]))
                    persistent_schemas.append(AIcCatalogPersistentSchema(
                        kind=kind,
                        schema_id=str(item["schema_id"]),
                        write_version=(int(item["write_version"]) if item.get("write_version") is not None else None),
                        provider_id=(str(item["provider_id"]) if item.get("provider_id") is not None else None),
                        readable_versions=tuple(int(value) for value in item.get("readable_versions", ())),
                        writable_versions=tuple(int(value) for value in item.get("writable_versions", ())),
                        preferred_write_version=(
                            int(item["preferred_write_version"])
                            if item.get("preferred_write_version") is not None else None
                        ),
                    ))
                persistent_schemas = tuple(persistent_schemas)
                releases.append(AIcCatalogRelease(
                    version=int(raw_release["version"]),
                    provides=provides,
                    requires=requires,
                    entitlement_licensing_scopes=entitlement_licensing_scopes,
                    provided_capability_entitlements=tuple(entitlements),
                    persistent_schemas=persistent_schemas,
                    artifacts=tuple(artifacts),
                    published_at=(str(raw_release["published_at"]) if raw_release.get("published_at") is not None else None),
                    release_notes_url=(str(raw_release["release_notes_url"]) if raw_release.get("release_notes_url") is not None else None),
                    metadata=dict(raw_release.get("metadata", {})),
                ))
            raw_publisher = raw_component.get("publisher")
            raw_icon = raw_component.get("icon")
            components.append(AIcCatalogComponent(
                component_id=str(raw_component["component_id"]),
                releases=tuple(releases),
                name=normalize_display_text(raw_component.get("name")),
                description=normalize_display_text(raw_component.get("description")),
                publisher=(AIcCatalogPublisher(
                    str(raw_publisher["id"]), normalize_display_text(raw_publisher.get("name"))
                ) if isinstance(raw_publisher, Mapping) else None),
                homepage_url=(str(raw_component["homepage_url"]) if raw_component.get("homepage_url") is not None else None),
                documentation_url=(str(raw_component["documentation_url"]) if raw_component.get("documentation_url") is not None else None),
                support_url=(str(raw_component["support_url"]) if raw_component.get("support_url") is not None else None),
                entitlement_info_url=(str(raw_component["entitlement_info_url"]) if raw_component.get("entitlement_info_url") is not None else None),
                icon=(AIcCatalogIcon(str(raw_icon["url"])) if isinstance(raw_icon, Mapping) else None),
                categories=tuple(str(value) for value in raw_component.get("categories", ())),
                tags=tuple(str(value) for value in raw_component.get("tags", ())),
                metadata=dict(raw_component.get("metadata", {})),
            ))
        return AIcCatalogDocument(
            format_version=int(body["format_version"]),
            product_id=str(body["product_id"]),
            technology_id=str(body["technology_id"]),
            components=tuple(components),
            generated_at=(str(body["generated_at"]) if body.get("generated_at") is not None else None),
            metadata=dict(body.get("metadata", {})),
        )

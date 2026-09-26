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
        body_probe = raw.get("Catalog")
        if not isinstance(body_probe, Mapping):
            raise AIxPackageManagementError(f"catalog document {source} requires catalog object")
        format_version = int(body_probe.get("FormatVersion", 0))
        if format_version != 1:
            raise AIxPackageManagementError(f"catalog document {source} has unsupported format_version {format_version}; expected 1")
        schema_text = read_core_schema("catalog_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            raise AIxPackageManagementError(
                f"catalog document {source} schema validation failed: {_render_validation_errors(errors)}"
            )
        body = raw["Catalog"]
        components: list[AIcCatalogComponent] = []
        for raw_component in body.get("Components", ()):
            releases: list[AIcCatalogRelease] = []
            for raw_release in raw_component.get("Releases", ()):
                provides = tuple(AIcCatalogCapabilityOffer(
                    str(item["Capability"]), tuple(int(version) for version in item.get("Versions", ()))
                ) for item in raw_release.get("Provides", ()))
                requires = tuple(AIcCatalogCapabilityRequirement(
                    id=str(item["Id"]),
                    capability_id=str(item["Capability"]),
                    versions=tuple(int(version) for version in item.get("Versions", ())),
                    cardinality=AInConsumerCardinality(str(item.get("Cardinality", "single"))),
                    mandatory=bool(item.get("Mandatory", True)),
                ) for item in raw_release.get("Requires", ()))
                entitlement_licensing_scopes = tuple(
                    AIcEntitlementLicensingScopeDescriptor(
                        type=str(item["Type"]),
                        name=normalize_display_text(item.get("Name")),
                        description=normalize_display_text(item.get("Description")),
                        metadata=dict(item.get("Metadata", {})),
                    )
                    for item in raw_release.get("EntitlementLicensingScopes", ())
                )
                entitlements = []
                for raw_entitlement in raw_release.get("ProvidedCapabilityEntitlements", ()):
                    permissions = tuple(AIcPermissionDescriptor(
                        id=str(item["Id"]),
                        name=normalize_display_text(item.get("Name")),
                        description=normalize_display_text(item.get("Description")),
                        possible_licensing_scope_types=tuple(
                            str(value) for value in item.get("PossibleLicensingScopes", ())
                        ),
                        metadata=dict(item.get("Metadata", {})),
                    ) for item in raw_entitlement.get("Permissions", ()))
                    entitlements.append(AIcCapabilityEntitlementDescriptor(
                        capability_id=str(raw_entitlement["Capability"]["Id"]),
                        capability_version=int(raw_entitlement["Capability"]["Version"]),
                        permissions=permissions,
                        name=normalize_display_text(raw_entitlement.get("Name")),
                        description=normalize_display_text(raw_entitlement.get("Description")),
                    ))
                artifacts = []
                for raw_artifact in raw_release.get("Artifacts", ()):
                    raw_locator = raw_artifact["Locator"]
                    locator_uri = str(raw_locator["Uri"]) if raw_locator.get("Uri") is not None else None
                    if locator_uri is not None and source_uri is not None:
                        locator_uri = _resolve_relative_uri(source_uri, locator_uri)
                    sidecars = tuple(AIcPackageSidecar(
                        uri=(_resolve_relative_uri(source_uri, str(item["Uri"])) if source_uri is not None else str(item["Uri"])),
                        suffix=str(item["Suffix"]),
                        name=normalize_display_text(item.get("Name")),
                        description=normalize_display_text(item.get("Description")),
                    ) for item in raw_artifact.get("Sidecars", ()))
                    artifacts.append(AIcCatalogArtifact(
                        id=str(raw_artifact["Id"]),
                        locator=AIcCatalogArtifactLocator(
                            type=str(raw_locator["Type"]),
                            uri=locator_uri,
                            repository_id=(str(raw_locator["RepositoryId"]) if raw_locator.get("RepositoryId") is not None else None),
                            coordinates=dict(raw_locator.get("Coordinates", {})),
                        ),
                        artifact_filename=str(raw_artifact["ArtifactFilename"]),
                        package_format=str(raw_artifact["PackageFormat"]),
                        descriptor_path=str(raw_artifact["DescriptorPath"]),
                        sha256=str(raw_artifact["Sha256"]),
                        runtime_package=(str(raw_artifact["RuntimePackage"]) if raw_artifact.get("RuntimePackage") is not None else None),
                        verifier_id=(str(raw_artifact["VerifierId"]) if raw_artifact.get("VerifierId") is not None else None),
                        authentication_profile_id=(str(raw_artifact["AuthenticationProfileId"]) if raw_artifact.get("AuthenticationProfileId") is not None else None),
                        sidecars=sidecars,
                        platforms=tuple(str(value) for value in raw_artifact.get("Platforms", ())),
                        architectures=tuple(str(value) for value in raw_artifact.get("Architectures", ())),
                        metadata=dict(raw_artifact.get("Metadata", {})),
                    ))
                persistent_schemas = []
                for item in raw_release.get("PersistentSchemas", ()):
                    kind = AInCatalogPersistentSchemaKind(str(item["Kind"]))
                    persistent_schemas.append(AIcCatalogPersistentSchema(
                        kind=kind,
                        schema_id=str(item["SchemaId"]),
                        write_version=(int(item["WriteVersion"]) if item.get("WriteVersion") is not None else None),
                        provider_id=(str(item["ProviderId"]) if item.get("ProviderId") is not None else None),
                        readable_versions=tuple(int(value) for value in item.get("ReadableVersions", ())),
                        writable_versions=tuple(int(value) for value in item.get("WritableVersions", ())),
                        preferred_write_version=(
                            int(item["PreferredWriteVersion"])
                            if item.get("PreferredWriteVersion") is not None else None
                        ),
                    ))
                persistent_schemas = tuple(persistent_schemas)
                releases.append(AIcCatalogRelease(
                    version=int(raw_release["Version"]),
                    provides=provides,
                    requires=requires,
                    entitlement_licensing_scopes=entitlement_licensing_scopes,
                    provided_capability_entitlements=tuple(entitlements),
                    persistent_schemas=persistent_schemas,
                    artifacts=tuple(artifacts),
                    published_at=(str(raw_release["PublishedAt"]) if raw_release.get("PublishedAt") is not None else None),
                    release_notes_url=(str(raw_release["ReleaseNotesUrl"]) if raw_release.get("ReleaseNotesUrl") is not None else None),
                    metadata=dict(raw_release.get("Metadata", {})),
                ))
            raw_publisher = raw_component.get("Publisher")
            raw_icon = raw_component.get("Icon")
            components.append(AIcCatalogComponent(
                component_id=str(raw_component["ComponentId"]),
                releases=tuple(releases),
                name=normalize_display_text(raw_component.get("Name")),
                description=normalize_display_text(raw_component.get("Description")),
                publisher=(AIcCatalogPublisher(
                    str(raw_publisher["Id"]), normalize_display_text(raw_publisher.get("Name"))
                ) if isinstance(raw_publisher, Mapping) else None),
                homepage_url=(str(raw_component["HomepageUrl"]) if raw_component.get("HomepageUrl") is not None else None),
                documentation_url=(str(raw_component["DocumentationUrl"]) if raw_component.get("DocumentationUrl") is not None else None),
                support_url=(str(raw_component["SupportUrl"]) if raw_component.get("SupportUrl") is not None else None),
                entitlement_info_url=(str(raw_component["EntitlementInfoUrl"]) if raw_component.get("EntitlementInfoUrl") is not None else None),
                icon=(AIcCatalogIcon(str(raw_icon["Url"])) if isinstance(raw_icon, Mapping) else None),
                categories=tuple(str(value) for value in raw_component.get("Categories", ())),
                tags=tuple(str(value) for value in raw_component.get("Tags", ())),
                metadata=dict(raw_component.get("Metadata", {})),
            ))
        return AIcCatalogDocument(
            format_version=int(body["FormatVersion"]),
            product_id=str(body["ProductId"]),
            technology_id=str(body["TechnologyId"]),
            components=tuple(components),
            generated_at=(str(body["GeneratedAt"]) if body.get("GeneratedAt") is not None else None),
            metadata=dict(body.get("Metadata", {})),
        )

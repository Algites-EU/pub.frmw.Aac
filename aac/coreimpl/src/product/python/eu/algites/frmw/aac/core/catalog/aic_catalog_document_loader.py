from __future__ import annotations

from eu.algites.frmw.aac.core.catalog.aiig_catalog_1 import AIigCatalog_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_artifact_1 import AIigCatalogDefinitionArtifact_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_artifact_locator_1 import AIigCatalogDefinitionArtifactLocator_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_artifact_sidecars_items_1 import AIigCatalogDefinitionArtifactSidecarsItems_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_capability_entitlement_1 import AIigCatalogDefinitionCapabilityEntitlement_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_capability_entitlement_capability_1 import AIigCatalogDefinitionCapabilityEntitlementCapability_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_catalog_1 import AIigCatalogCatalog_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_component_1 import AIigCatalogDefinitionComponent_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_component_icon_1 import AIigCatalogDefinitionComponentIcon_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_component_publisher_1 import AIigCatalogDefinitionComponentPublisher_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_permission_1 import AIigCatalogDefinitionPermission_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_persistent_schema_1 import AIigCatalogDefinitionPersistentSchema_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_release_1 import AIigCatalogDefinitionRelease_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_release_entitlement_licensing_scopes_items_1 import AIigCatalogDefinitionReleaseEntitlementLicensingScopesItems_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_release_provides_items_1 import AIigCatalogDefinitionReleaseProvidesItems_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_definition_release_requires_items_1 import AIigCatalogDefinitionReleaseRequiresItems_1
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
        body_probe = raw.get(AIigCatalog_1.SCHEMA_FIELD_NAME__CATALOG)
        if not isinstance(body_probe, Mapping):
            raise AIxPackageManagementError(f"catalog document {source} requires catalog object")
        format_version = int(body_probe.get(AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__FORMAT_VERSION, 0))
        if format_version != 1:
            raise AIxPackageManagementError(f"catalog document {source} has unsupported format_version {format_version}; expected 1")
        schema_text = read_core_schema("catalog_1.jsondef.schema.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            raise AIxPackageManagementError(
                f"catalog document {source} schema validation failed: {_render_validation_errors(errors)}"
            )
        body = raw[AIigCatalog_1.SCHEMA_FIELD_NAME__CATALOG]
        components: list[AIcCatalogComponent] = []
        for raw_component in body.get(AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__COMPONENTS, ()):
            releases: list[AIcCatalogRelease] = []
            for raw_release in raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__RELEASES, ()):
                provides = tuple(AIcCatalogCapabilityOffer(
                    str(item[AIigCatalogDefinitionReleaseProvidesItems_1.SCHEMA_FIELD_NAME__CAPABILITY]), tuple(int(version) for version in item.get(AIigCatalogDefinitionReleaseProvidesItems_1.SCHEMA_FIELD_NAME__VERSIONS, ()))
                ) for item in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__PROVIDES, ()))
                requires = tuple(AIcCatalogCapabilityRequirement(
                    id=str(item[AIigCatalogDefinitionReleaseRequiresItems_1.SCHEMA_FIELD_NAME__ID]),
                    capability_id=str(item[AIigCatalogDefinitionReleaseRequiresItems_1.SCHEMA_FIELD_NAME__CAPABILITY]),
                    versions=tuple(int(version) for version in item.get(AIigCatalogDefinitionReleaseRequiresItems_1.SCHEMA_FIELD_NAME__VERSIONS, ())),
                    cardinality=AInConsumerCardinality(str(item.get(AIigCatalogDefinitionReleaseRequiresItems_1.SCHEMA_FIELD_NAME__CARDINALITY, "single"))),
                    mandatory=bool(item.get(AIigCatalogDefinitionReleaseRequiresItems_1.SCHEMA_FIELD_NAME__MANDATORY, True)),
                ) for item in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__REQUIRES, ()))
                entitlement_licensing_scopes = tuple(
                    AIcEntitlementLicensingScopeDescriptor(
                        type=str(item[AIigCatalogDefinitionReleaseEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__TYPE]),
                        name=normalize_display_text(item.get(AIigCatalogDefinitionReleaseEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__NAME)),
                        description=normalize_display_text(item.get(AIigCatalogDefinitionReleaseEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                        metadata=dict(item.get(AIigCatalogDefinitionReleaseEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__METADATA, {})),
                    )
                    for item in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__ENTITLEMENT_LICENSING_SCOPES, ())
                )
                entitlements = []
                for raw_entitlement in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__PROVIDED_CAPABILITY_ENTITLEMENTS, ()):
                    permissions = tuple(AIcPermissionDescriptor(
                        id=str(item[AIigCatalogDefinitionPermission_1.SCHEMA_FIELD_NAME__ID]),
                        name=normalize_display_text(item.get(AIigCatalogDefinitionPermission_1.SCHEMA_FIELD_NAME__NAME)),
                        description=normalize_display_text(item.get(AIigCatalogDefinitionPermission_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                        possible_licensing_scope_types=tuple(
                            str(value) for value in item.get(AIigCatalogDefinitionPermission_1.SCHEMA_FIELD_NAME__POSSIBLE_LICENSING_SCOPES, ())
                        ),
                        metadata=dict(item.get(AIigCatalogDefinitionPermission_1.SCHEMA_FIELD_NAME__METADATA, {})),
                    ) for item in raw_entitlement.get(AIigCatalogDefinitionCapabilityEntitlement_1.SCHEMA_FIELD_NAME__PERMISSIONS, ()))
                    entitlements.append(AIcCapabilityEntitlementDescriptor(
                        capability_id=str(raw_entitlement[AIigCatalogDefinitionCapabilityEntitlement_1.SCHEMA_FIELD_NAME__CAPABILITY][AIigCatalogDefinitionCapabilityEntitlementCapability_1.SCHEMA_FIELD_NAME__ID]),
                        capability_version=int(raw_entitlement[AIigCatalogDefinitionCapabilityEntitlement_1.SCHEMA_FIELD_NAME__CAPABILITY][AIigCatalogDefinitionCapabilityEntitlementCapability_1.SCHEMA_FIELD_NAME__VERSION]),
                        permissions=permissions,
                        name=normalize_display_text(raw_entitlement.get(AIigCatalogDefinitionCapabilityEntitlement_1.SCHEMA_FIELD_NAME__NAME)),
                        description=normalize_display_text(raw_entitlement.get(AIigCatalogDefinitionCapabilityEntitlement_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                    ))
                artifacts = []
                for raw_artifact in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__ARTIFACTS, ()):
                    raw_locator = raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__LOCATOR]
                    locator_uri = str(raw_locator[AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__URI]) if raw_locator.get(AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__URI) is not None else None
                    if locator_uri is not None and source_uri is not None:
                        locator_uri = _resolve_relative_uri(source_uri, locator_uri)
                    sidecars = tuple(AIcPackageSidecar(
                        uri=(_resolve_relative_uri(source_uri, str(item[AIigCatalogDefinitionArtifactSidecarsItems_1.SCHEMA_FIELD_NAME__URI])) if source_uri is not None else str(item[AIigCatalogDefinitionArtifactSidecarsItems_1.SCHEMA_FIELD_NAME__URI])),
                        suffix=str(item[AIigCatalogDefinitionArtifactSidecarsItems_1.SCHEMA_FIELD_NAME__SUFFIX]),
                        name=normalize_display_text(item.get(AIigCatalogDefinitionArtifactSidecarsItems_1.SCHEMA_FIELD_NAME__NAME)),
                        description=normalize_display_text(item.get(AIigCatalogDefinitionArtifactSidecarsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                    ) for item in raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__SIDECARS, ()))
                    artifacts.append(AIcCatalogArtifact(
                        id=str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__ID]),
                        locator=AIcCatalogArtifactLocator(
                            type=str(raw_locator[AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__TYPE]),
                            uri=locator_uri,
                            repository_id=(str(raw_locator[AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__REPOSITORY_ID]) if raw_locator.get(AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__REPOSITORY_ID) is not None else None),
                            coordinates=dict(raw_locator.get(AIigCatalogDefinitionArtifactLocator_1.SCHEMA_FIELD_NAME__COORDINATES, {})),
                        ),
                        artifact_filename=str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__ARTIFACT_FILENAME]),
                        package_format=str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__PACKAGE_FORMAT]),
                        descriptor_path=str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__DESCRIPTOR_PATH]),
                        sha256=str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__SHA256]),
                        runtime_package=(str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__RUNTIME_PACKAGE]) if raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__RUNTIME_PACKAGE) is not None else None),
                        verifier_id=(str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__VERIFIER_ID]) if raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__VERIFIER_ID) is not None else None),
                        authentication_profile_id=(str(raw_artifact[AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID]) if raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID) is not None else None),
                        sidecars=sidecars,
                        platforms=tuple(str(value) for value in raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__PLATFORMS, ())),
                        architectures=tuple(str(value) for value in raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__ARCHITECTURES, ())),
                        metadata=dict(raw_artifact.get(AIigCatalogDefinitionArtifact_1.SCHEMA_FIELD_NAME__METADATA, {})),
                    ))
                persistent_schemas = []
                for item in raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__PERSISTENT_SCHEMAS, ()):
                    kind = AInCatalogPersistentSchemaKind(str(item[AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__KIND]))
                    persistent_schemas.append(AIcCatalogPersistentSchema(
                        kind=kind,
                        schema_id=str(item[AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__SCHEMA_ID]),
                        write_version=(int(item[AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__WRITE_VERSION]) if item.get(AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__WRITE_VERSION) is not None else None),
                        provider_id=(str(item[AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__PROVIDER_ID]) if item.get(AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__PROVIDER_ID) is not None else None),
                        readable_versions=tuple(int(value) for value in item.get(AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__READABLE_VERSIONS, ())),
                        writable_versions=tuple(int(value) for value in item.get(AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__WRITABLE_VERSIONS, ())),
                        preferred_write_version=(
                            int(item[AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__PREFERRED_WRITE_VERSION])
                            if item.get(AIigCatalogDefinitionPersistentSchema_1.SCHEMA_FIELD_NAME__PREFERRED_WRITE_VERSION) is not None else None
                        ),
                    ))
                persistent_schemas = tuple(persistent_schemas)
                releases.append(AIcCatalogRelease(
                    version=int(raw_release[AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__VERSION]),
                    provides=provides,
                    requires=requires,
                    entitlement_licensing_scopes=entitlement_licensing_scopes,
                    provided_capability_entitlements=tuple(entitlements),
                    persistent_schemas=persistent_schemas,
                    artifacts=tuple(artifacts),
                    published_at=(str(raw_release[AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__PUBLISHED_AT]) if raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__PUBLISHED_AT) is not None else None),
                    release_notes_url=(str(raw_release[AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__RELEASE_NOTES_URL]) if raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__RELEASE_NOTES_URL) is not None else None),
                    metadata=dict(raw_release.get(AIigCatalogDefinitionRelease_1.SCHEMA_FIELD_NAME__METADATA, {})),
                ))
            raw_publisher = raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__PUBLISHER)
            raw_icon = raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__ICON)
            components.append(AIcCatalogComponent(
                component_id=str(raw_component[AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__COMPONENT_ID]),
                releases=tuple(releases),
                name=normalize_display_text(raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__NAME)),
                description=normalize_display_text(raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                publisher=(AIcCatalogPublisher(
                    str(raw_publisher[AIigCatalogDefinitionComponentPublisher_1.SCHEMA_FIELD_NAME__ID]), normalize_display_text(raw_publisher.get(AIigCatalogDefinitionComponentPublisher_1.SCHEMA_FIELD_NAME__NAME))
                ) if isinstance(raw_publisher, Mapping) else None),
                homepage_url=(str(raw_component[AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__HOMEPAGE_URL]) if raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__HOMEPAGE_URL) is not None else None),
                documentation_url=(str(raw_component[AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__DOCUMENTATION_URL]) if raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__DOCUMENTATION_URL) is not None else None),
                support_url=(str(raw_component[AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__SUPPORT_URL]) if raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__SUPPORT_URL) is not None else None),
                entitlement_info_url=(str(raw_component[AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__ENTITLEMENT_INFO_URL]) if raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__ENTITLEMENT_INFO_URL) is not None else None),
                icon=(AIcCatalogIcon(str(raw_icon[AIigCatalogDefinitionComponentIcon_1.SCHEMA_FIELD_NAME__URL])) if isinstance(raw_icon, Mapping) else None),
                categories=tuple(str(value) for value in raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__CATEGORIES, ())),
                tags=tuple(str(value) for value in raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__TAGS, ())),
                metadata=dict(raw_component.get(AIigCatalogDefinitionComponent_1.SCHEMA_FIELD_NAME__METADATA, {})),
            ))
        return AIcCatalogDocument(
            format_version=int(body[AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__FORMAT_VERSION]),
            product_id=str(body[AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__PRODUCT_ID]),
            technology_id=str(body[AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__TECHNOLOGY_ID]),
            components=tuple(components),
            generated_at=(str(body[AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__GENERATED_AT]) if body.get(AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__GENERATED_AT) is not None else None),
            metadata=dict(body.get(AIigCatalogCatalog_1.SCHEMA_FIELD_NAME__METADATA, {})),
        )

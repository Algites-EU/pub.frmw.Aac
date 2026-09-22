from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..contracts import AInConsumerCardinality
from ..descriptor import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation import AIcDisplayText
from ..packages import AIcPackageSidecar


@dataclass(frozen=True, slots=True)
class AIcCatalogQuery:
    """Technology-scoped catalog query.

    ``product_id`` and ``technology_id`` are mandatory AAC catalog dimensions.
    Component ids and versions are interpreted only inside that scope.
    """

    product_id: str
    technology_id: str
    component_id: str | None = None
    versions: tuple[int, ...] = ()
    text: str | None = None
    provides_capability_id: str | None = None
    requires_capability_id: str | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.product_id or not self.technology_id:
            raise ValueError("catalog query requires product_id and technology_id")
        if any(version < 1 for version in self.versions):
            raise ValueError("catalog query versions must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcCatalogPublisher:
    id: str
    name: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("catalog publisher id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcCatalogIcon:
    url: str

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("catalog icon url must not be empty")


@dataclass(frozen=True, slots=True)
class AIcCatalogCapabilityOffer:
    capability_id: str
    versions: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.capability_id or not self.versions or any(version < 1 for version in self.versions):
            raise ValueError("catalog capability offer requires id and versions >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("catalog capability offer versions must be unique")


@dataclass(frozen=True, slots=True)
class AIcCatalogCapabilityRequirement:
    id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: AInConsumerCardinality = AInConsumerCardinality.SINGLE
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.capability_id:
            raise ValueError("catalog capability requirement requires id/capability")
        if any(version < 1 for version in self.versions):
            raise ValueError("catalog capability requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("catalog capability requirement versions must be unique")




class AInCatalogPersistentSchemaKind(str, Enum):
    COMPONENT_CONFIGURATION = "COMPONENT_CONFIGURATION"
    PROVIDER_CONFIGURATION = "PROVIDER_CONFIGURATION"
    DATA_ENTITY = "DATA_ENTITY"


@dataclass(frozen=True, slots=True)
class AIcCatalogPersistentSchema:
    kind: AInCatalogPersistentSchemaKind
    schema_id: str
    write_version: int | None = None
    provider_id: str | None = None
    readable_versions: tuple[int, ...] = ()
    writable_versions: tuple[int, ...] = ()
    preferred_write_version: int | None = None

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("catalog persistent schema requires schema_id")
        if self.kind is AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION:
            if self.write_version is None or self.write_version < 1:
                raise ValueError("component configuration schema requires write_version >= 1")
            if self.provider_id is not None or self.readable_versions or self.writable_versions or self.preferred_write_version is not None:
                raise ValueError("component configuration schema must not declare provider/data-entity fields")
        elif self.kind is AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION:
            if self.write_version is None or self.write_version < 1 or not self.provider_id:
                raise ValueError("provider configuration schema requires provider_id and write_version >= 1")
            if self.readable_versions or self.writable_versions or self.preferred_write_version is not None:
                raise ValueError("provider configuration schema must not declare data-entity fields")
        elif self.kind is AInCatalogPersistentSchemaKind.DATA_ENTITY:
            if self.write_version is not None or self.provider_id is not None:
                raise ValueError("data entity schema must not declare configuration write_version/provider_id")
            if not self.readable_versions and not self.writable_versions:
                raise ValueError("data entity schema support requires readable_versions or writable_versions")
            if any(version < 1 for version in self.readable_versions + self.writable_versions):
                raise ValueError("data entity schema versions must be >= 1")
            if len(self.readable_versions) != len(set(self.readable_versions)) or len(self.writable_versions) != len(set(self.writable_versions)):
                raise ValueError("data entity schema versions must be unique")
            if self.writable_versions:
                if self.preferred_write_version not in self.writable_versions:
                    raise ValueError("data entity preferred_write_version must be one of writable_versions")
            elif self.preferred_write_version is not None:
                raise ValueError("read-only data entity support must not declare preferred_write_version")

    @property
    def identity(self) -> tuple[str, str | None]:
        if self.kind is AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION:
            return self.kind.value, self.provider_id
        if self.kind is AInCatalogPersistentSchemaKind.DATA_ENTITY:
            return self.kind.value, self.schema_id
        return self.kind.value, None


@dataclass(frozen=True, slots=True)
class AIcCatalogArtifactLocator:
    type: str
    uri: str | None = None
    repository_id: str | None = None
    coordinates: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("catalog artifact locator type must not be empty")
        if self.type.upper() == "URI" and not self.uri:
            raise ValueError("URI catalog artifact locator requires uri")
        if self.type.upper() == "REPOSITORY" and not self.repository_id:
            raise ValueError("REPOSITORY catalog artifact locator requires repository_id")


@dataclass(frozen=True, slots=True)
class AIcCatalogArtifact:
    id: str
    locator: AIcCatalogArtifactLocator
    artifact_filename: str
    package_format: str
    descriptor_path: str
    sha256: str
    runtime_package: str | None = None
    verifier_id: str | None = None
    authentication_profile_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()
    platforms: tuple[str, ...] = ()
    architectures: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.artifact_filename or not self.package_format or not self.descriptor_path:
            raise ValueError("catalog artifact requires id/filename/package_format/descriptor_path")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("catalog artifact sha256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)
        if len(self.platforms) != len(set(self.platforms)) or len(self.architectures) != len(set(self.architectures)):
            raise ValueError("catalog artifact platform/architecture selectors must be unique")


@dataclass(frozen=True, slots=True)
class AIcCatalogRelease:
    version: int
    provides: tuple[AIcCatalogCapabilityOffer, ...] = ()
    requires: tuple[AIcCatalogCapabilityRequirement, ...] = ()
    entitlement_licensing_scopes: tuple[AIcEntitlementLicensingScopeDescriptor, ...] = ()
    provided_capability_entitlements: tuple[AIcCapabilityEntitlementDescriptor, ...] = ()
    persistent_schemas: tuple[AIcCatalogPersistentSchema, ...] = ()
    artifacts: tuple[AIcCatalogArtifact, ...] = ()
    published_at: str | None = None
    release_notes_url: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("catalog release version must be >= 1")
        licensing_scope_types = [item.type for item in self.entitlement_licensing_scopes]
        if len(licensing_scope_types) != len(set(licensing_scope_types)):
            raise ValueError("catalog entitlement licensing scope declarations must be unique by type")
        declared_licensing_scope_types = set(licensing_scope_types)
        referenced_licensing_scope_types = {
            scope_type
            for entitlement in self.provided_capability_entitlements
            for permission in entitlement.permissions
            for scope_type in permission.possible_licensing_scope_types
        }
        undeclared = sorted(referenced_licensing_scope_types - declared_licensing_scope_types)
        if undeclared:
            raise ValueError(
                "catalog capability entitlement declarations reference undeclared entitlement licensing scopes: "
                f"{undeclared!r}"
            )
        artifact_ids = [artifact.id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("catalog artifact ids must be unique inside one release")
        requirement_ids = [requirement.id for requirement in self.requires]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("catalog requirement ids must be unique inside one release")
        schema_ids = [item.identity for item in self.persistent_schemas]
        if len(schema_ids) != len(set(schema_ids)):
            raise ValueError("catalog persistent schemas must be unique by kind/provider-or-entity identity")


@dataclass(frozen=True, slots=True)
class AIcCatalogComponent:
    component_id: str
    releases: tuple[AIcCatalogRelease, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    publisher: AIcCatalogPublisher | None = None
    homepage_url: str | None = None
    documentation_url: str | None = None
    support_url: str | None = None
    entitlement_info_url: str | None = None
    icon: AIcCatalogIcon | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("catalog component_id must not be empty")
        versions = [release.version for release in self.releases]
        if len(versions) != len(set(versions)):
            raise ValueError("catalog releases must be unique by version")


@dataclass(frozen=True, slots=True)
class AIcCatalogDocument:
    format_version: int
    product_id: str
    technology_id: str
    components: tuple[AIcCatalogComponent, ...]
    generated_at: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.format_version < 1 or not self.product_id or not self.technology_id:
            raise ValueError("catalog document requires format_version/product_id/technology_id")
        ids = [component.component_id for component in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog components must be unique by component_id")


@dataclass(frozen=True, slots=True)
class AIcCatalogEntry:
    source_id: str
    product_id: str
    technology_id: str
    component: AIcCatalogComponent
    release: AIcCatalogRelease

    def __post_init__(self) -> None:
        if not self.source_id or not self.product_id or not self.technology_id:
            raise ValueError("catalog entry requires source/product/technology")

    @property
    def component_id(self) -> str:
        return self.component.component_id

    @property
    def component_version(self) -> int:
        return self.release.version


@dataclass(frozen=True, slots=True)
class AIcCatalogSourceRegistration:
    id: str
    type: str
    uri: str
    authentication_profile_id: str | None = None
    priority: int = 0
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type or not self.uri:
            raise ValueError("catalog source registration requires id/type/uri")


@dataclass(frozen=True, slots=True)
class AIcCatalogBootstrap:
    schema_version: int
    product_id: str
    technology_id: str
    sources: tuple[AIcCatalogSourceRegistration, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1 or not self.product_id or not self.technology_id:
            raise ValueError("catalog bootstrap requires schema_version/product_id/technology_id")
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog source ids must be unique")

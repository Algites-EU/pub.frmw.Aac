from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .ain_catalog_persistent_schema_kind import AInCatalogPersistentSchemaKind

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

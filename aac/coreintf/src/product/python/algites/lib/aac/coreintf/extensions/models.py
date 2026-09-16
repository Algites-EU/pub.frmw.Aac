from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AIcCoreEntityRef:
    entity_type_id: str
    entity_id: str

    def __post_init__(self) -> None:
        if not self.entity_type_id or not self.entity_id:
            raise ValueError("core entity reference type/id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcCoreEntityContext:
    entity: AIcCoreEntityRef
    core_entity_schema_id: str
    core_entity_schema_version: int
    normalized_snapshot: object | None = None

    def __post_init__(self) -> None:
        if not self.core_entity_schema_id or self.core_entity_schema_version < 1:
            raise ValueError("Core entity context requires schema id/version >= 1")


@dataclass(frozen=True, slots=True)
class AIcEntityExtensionDataEnvelope:
    owner_component_id: str
    component_extension_schema_id: str
    component_extension_schema_version: int
    written_by_component_version: int
    core_entity: AIcCoreEntityRef
    payload: object
    payload_format: str = "NORMALIZED"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.owner_component_id or not self.component_extension_schema_id:
            raise ValueError("component-extension envelope owner/schema id must not be empty")
        if self.component_extension_schema_version < 1 or self.written_by_component_version < 1:
            raise ValueError("component-extension schema/component versions must be >= 1")
        if not self.payload_format:
            raise ValueError("payload_format must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntityExtensionDataRecord:
    record_revision: int | str
    envelope: AIcEntityExtensionDataEnvelope

    def __post_init__(self) -> None:
        if isinstance(self.record_revision, int):
            if self.record_revision < 1:
                raise ValueError("integer extension-data record_revision must be >= 1")
        elif isinstance(self.record_revision, str):
            if not self.record_revision:
                raise ValueError("string extension-data record_revision must not be empty")
        else:
            raise TypeError("extension-data record_revision must be an integer or opaque string")


@dataclass(frozen=True, slots=True)
class AIcEntityExtensionMigrationRequest:
    entity_context: AIcCoreEntityContext
    source: AIcEntityExtensionDataEnvelope
    target_component_extension_schema_version: int

    def __post_init__(self) -> None:
        if self.source.core_entity != self.entity_context.entity:
            raise ValueError("component-extension migration source must belong to entity_context.entity")
        if self.target_component_extension_schema_version < 1:
            raise ValueError("target component-extension schema version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcEntityExtensionMigrationResult:
    component_extension_schema_id: str
    component_extension_schema_version: int
    payload: object
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.component_extension_schema_id or self.component_extension_schema_version < 1:
            raise ValueError("component-extension migration result requires schema id/version >= 1")

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_data_entity_requirement_descriptor import AIcDataEntityRequirementDescriptor
from .aic_schema_migration_step_descriptor import AIcSchemaMigrationStepDescriptor

@dataclass(frozen=True, slots=True)
class AIcDataEntitySupportDescriptor:
    schema_id: str
    readable_versions: tuple[int, ...] = ()
    writable_versions: tuple[int, ...] = ()
    preferred_write_version: int | None = None
    migrations: tuple[AIcSchemaMigrationStepDescriptor, ...] = ()
    data_entity_requirements: tuple[AIcDataEntityRequirementDescriptor, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("data entity support schema_id must not be empty")
        if not self.readable_versions and not self.writable_versions:
            raise ValueError("data entity support must declare at least one readable or writable version")
        if any(version < 1 for version in self.readable_versions + self.writable_versions):
            raise ValueError("data entity support versions must be >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("data entity support readable_versions must be unique")
        if len(self.writable_versions) != len(set(self.writable_versions)):
            raise ValueError("data entity support writable_versions must be unique")
        if self.writable_versions:
            if self.preferred_write_version is None:
                raise ValueError("data entity support with writable_versions requires preferred_write_version")
            if self.preferred_write_version not in self.writable_versions:
                raise ValueError("preferred_write_version must be one of writable_versions")
        elif self.preferred_write_version is not None:
            raise ValueError("read-only data entity support must not declare preferred_write_version")
        migration_pairs = [(item.from_version, item.to_version) for item in self.migrations]
        if len(migration_pairs) != len(set(migration_pairs)):
            raise ValueError("data entity migration from/to pairs must be unique")
        requirement_ids = [item.schema_id for item in self.data_entity_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("data entity requirements must be unique by schema_id")

    def can_read(self, schema_version: int) -> bool:
        return schema_version in self.readable_versions

    def can_write(self, schema_version: int) -> bool:
        return schema_version in self.writable_versions

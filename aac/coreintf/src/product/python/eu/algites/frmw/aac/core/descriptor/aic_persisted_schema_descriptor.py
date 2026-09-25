from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_schema_migration_step_descriptor import AIcSchemaMigrationStepDescriptor

@dataclass(frozen=True, slots=True)
class AIcPersistedSchemaDescriptor:
    schema_id: str
    write_version: int
    readable_versions: tuple[int, ...]
    migrations: tuple[AIcSchemaMigrationStepDescriptor, ...] = ()
    resource_name: str | None = None

    def __post_init__(self) -> None:
        if not self.schema_id or self.write_version < 1:
            raise ValueError("persisted schema requires schema_id and write_version >= 1")
        if not self.readable_versions or any(v < 1 for v in self.readable_versions):
            raise ValueError("persisted schema must declare readable_versions >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("persisted schema readable_versions must be unique")
        if self.write_version not in self.readable_versions:
            raise ValueError("persisted schema write_version must also be readable")
        if self.resource_name is not None and not self.resource_name:
            raise ValueError("persisted schema resource_name must not be empty")
        identities = [(m.from_version, m.to_version) for m in self.migrations]
        if len(identities) != len(set(identities)):
            raise ValueError("persisted schema migration from/to pairs must be unique")

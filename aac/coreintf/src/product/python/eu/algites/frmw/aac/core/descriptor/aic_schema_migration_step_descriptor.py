from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

@dataclass(frozen=True, slots=True)
class AIcSchemaMigrationStepDescriptor:
    from_version: int
    to_version: int
    migrator_id: str

    def __post_init__(self) -> None:
        if self.from_version < 1 or self.to_version < 1:
            raise ValueError("schema migration versions must be >= 1")
        if self.from_version == self.to_version:
            raise ValueError("schema migration must change the schema version")
        if not self.migrator_id:
            raise ValueError("schema migration migrator_id must not be empty")

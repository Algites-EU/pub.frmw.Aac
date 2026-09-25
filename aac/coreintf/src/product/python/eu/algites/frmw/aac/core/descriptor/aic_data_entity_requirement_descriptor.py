from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .ain_data_entity_access import AInDataEntityAccess

@dataclass(frozen=True, slots=True)
class AIcDataEntityRequirementDescriptor:
    schema_id: str
    access: tuple[AInDataEntityAccess, ...] = (AInDataEntityAccess.READ,)
    readable_versions: tuple[int, ...] = ()
    writable_versions: tuple[int, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("data entity requirement schema_id must not be empty")
        if not self.access or len(self.access) != len(set(self.access)):
            raise ValueError("data entity requirement access entries must be non-empty and unique")
        if any(version < 1 for version in self.readable_versions + self.writable_versions):
            raise ValueError("data entity requirement versions must be >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("data entity requirement readable_versions must be unique")
        if len(self.writable_versions) != len(set(self.writable_versions)):
            raise ValueError("data entity requirement writable_versions must be unique")
        if AInDataEntityAccess.READ in self.access and not self.readable_versions:
            raise ValueError("READ data entity requirement requires readable_versions")
        if AInDataEntityAccess.WRITE in self.access and not self.writable_versions:
            raise ValueError("WRITE data entity requirement requires writable_versions")

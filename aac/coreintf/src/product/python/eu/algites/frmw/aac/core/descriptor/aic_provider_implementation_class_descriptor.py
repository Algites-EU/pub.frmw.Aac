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
class AIcProviderImplementationClassDescriptor:
    technology_kind: str
    class_name: str

    def __post_init__(self) -> None:
        if not self.technology_kind.strip():
            raise ValueError("provider implementation technology_kind must not be empty")
        if not self.class_name.strip():
            raise ValueError("provider implementation class_name must not be empty")

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
class AIcInitialProviderInstanceDescriptor:
    name: str = "default"
    configuration: Mapping[str, object] = field(default_factory=dict)
    access_mode: AInProviderAccessMode = AInProviderAccessMode.READ_WRITE

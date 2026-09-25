from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

class AInProviderRuntimeProfile(str, Enum):
    IN_PROCESS = "IN_PROCESS"
    PROCESS = "PROCESS"
    SUBINTERPRETER = "SUBINTERPRETER"

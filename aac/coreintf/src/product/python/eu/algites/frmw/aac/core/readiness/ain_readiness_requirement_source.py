from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class AInReadinessRequirementSource(str, Enum):
    COMPONENT_CONFIGURATION = "COMPONENT_CONFIGURATION"
    PROVIDER_CONFIGURATION = "PROVIDER_CONFIGURATION"
    CONTEXT = "CONTEXT"

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

class AInTargetStateRequestMode(str, Enum):
    EXACT = "EXACT"
    ONE_OF = "ONE_OF"
    LATEST_COMPATIBLE = "LATEST_COMPATIBLE"

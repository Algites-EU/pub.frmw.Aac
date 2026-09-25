from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class AInReadinessState(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"

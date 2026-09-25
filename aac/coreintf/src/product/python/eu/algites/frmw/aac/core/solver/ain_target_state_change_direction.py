from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

class AInTargetStateChangeDirection(str, Enum):
    INSTALL = "INSTALL"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    UNCHANGED = "UNCHANGED"

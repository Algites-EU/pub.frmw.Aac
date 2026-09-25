from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

class AInPackageUpdatePolicy(str, Enum):
    MANUAL = "MANUAL"
    NOTIFY = "NOTIFY"
    AUTO_COMPATIBLE = "AUTO_COMPATIBLE"
    AUTO_LOCKED = "AUTO_LOCKED"

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

class AInStoredPackageState(str, Enum):
    DOWNLOADED = "DOWNLOADED"
    INSTALLED = "INSTALLED"
    OBSOLETE = "OBSOLETE"

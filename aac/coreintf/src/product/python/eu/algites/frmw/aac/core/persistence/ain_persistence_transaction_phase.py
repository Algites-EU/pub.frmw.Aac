from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

class AInPersistenceTransactionPhase(str, Enum):
    PREPARED = "PREPARED"
    COMMIT_STARTED = "COMMIT_STARTED"
    COMMITTED = "COMMITTED"
    CLEANUP_COMPLETED = "CLEANUP_COMPLETED"
    ABORTED = "ABORTED"

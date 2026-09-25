from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from ..descriptor.api import AIcSchemaMigrationStepDescriptor

class AInPersistenceConvergenceStatus(str, Enum):
    """Whether a persisted representation can be safely converged to the target write version."""

    NOT_NEEDED = "NOT_NEEDED"
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"

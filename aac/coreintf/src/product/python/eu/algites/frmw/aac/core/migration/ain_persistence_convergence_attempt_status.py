from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from ..descriptor.api import AIcSchemaMigrationStepDescriptor

class AInPersistenceConvergenceAttemptStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"

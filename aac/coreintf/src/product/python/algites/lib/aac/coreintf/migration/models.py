from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..descriptor import AIcSchemaMigrationStepDescriptor


class AInSchemaRuntimeInterpretation(str, Enum):
    """How an active component can consume one persisted schema representation.

    Runtime interpretation is deliberately independent from whether the stored representation is
    already the component's preferred write version and from whether a persistence-convergence
    migration happens to exist.
    """

    DIRECT = "DIRECT"
    TRANSFORMED = "TRANSFORMED"
    UNSUPPORTED = "UNSUPPORTED"


class AInPersistenceConvergenceStatus(str, Enum):
    """Whether a persisted representation can be safely converged to the target write version."""

    NOT_NEEDED = "NOT_NEEDED"
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class AInPersistenceConvergenceAttemptStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"


@dataclass(frozen=True, slots=True)
class AIcSchemaCompatibilityAssessment:
    schema_id: str
    source_version: int
    target_write_version: int
    at_target_write_version: bool
    runtime_interpretation: AInSchemaRuntimeInterpretation
    migration_path: tuple[AIcSchemaMigrationStepDescriptor, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @property
    def directly_readable(self) -> bool:
        return self.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT

    @property
    def requires_runtime_transformation(self) -> bool:
        return self.runtime_interpretation is AInSchemaRuntimeInterpretation.TRANSFORMED

    @property
    def runtime_supported(self) -> bool:
        return self.runtime_interpretation is not AInSchemaRuntimeInterpretation.UNSUPPORTED

    def persistence_convergence_status(self, *, safe_persistence_available: bool) -> AInPersistenceConvergenceStatus:
        if self.at_target_write_version:
            return AInPersistenceConvergenceStatus.NOT_NEEDED
        if self.migration_path and safe_persistence_available:
            return AInPersistenceConvergenceStatus.SUPPORTED
        return AInPersistenceConvergenceStatus.NOT_SUPPORTED

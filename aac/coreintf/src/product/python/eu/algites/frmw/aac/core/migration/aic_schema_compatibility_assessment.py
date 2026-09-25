from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from ..descriptor.api import AIcSchemaMigrationStepDescriptor

from .ain_persistence_convergence_status import AInPersistenceConvergenceStatus
from .ain_schema_runtime_interpretation import AInSchemaRuntimeInterpretation

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

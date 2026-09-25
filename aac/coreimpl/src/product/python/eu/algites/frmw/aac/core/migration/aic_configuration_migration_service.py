from __future__ import annotations
from collections import deque
from typing import Mapping
from eu.algites.frmw.aac.core.configuration.api import (
    AIcConfigurationMigrationRequest,
    AIcConfigurationPersistedPayload,
    AIiConfigurationMigrator,
)
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcDataEntitySupportDescriptor, AIcPersistedSchemaDescriptor, AIcSchemaMigrationStepDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxPersistedSchemaIncompatible
from eu.algites.frmw.aac.core.dataentity.api import (
    AIcDataEntityEnvelope,
    AIcDataEntityMigrationRequest,
    AIiDataEntityMigrator,
)
from eu.algites.frmw.aac.core.migration.api import AInSchemaRuntimeInterpretation, AIcSchemaCompatibilityAssessment
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistedPayloadMigrationError

from .aic_schema_compatibility_evaluator import AIcSchemaCompatibilityEvaluator

class AIcConfigurationMigrationService:
    def __init__(self, migrators: Mapping[str, AIiConfigurationMigrator] | None = None) -> None:
        self._migrators = dict(migrators or {})
        self.compatibility = AIcSchemaCompatibilityEvaluator()

    def register(self, migrator_id: str, migrator: AIiConfigurationMigrator) -> None:
        if not migrator_id:
            raise ValueError("migrator_id must not be empty")
        self._migrators[migrator_id] = migrator

    def migrate_to_write_version(
        self,
        payload: AIcConfigurationPersistedPayload,
        declaration: AIcPersistedSchemaDescriptor,
        *,
        written_by_component_version: int,
    ) -> AIcConfigurationPersistedPayload:
        assessment = self.compatibility.assess(
            payload.configuration_schema_id, payload.configuration_schema_version, declaration
        )
        if assessment.at_target_write_version:
            return payload
        if not assessment.migration_path:
            raise AIxPersistedSchemaIncompatible(
                payload.configuration_schema_id,
                payload.configuration_schema_version,
                declaration.write_version,
                "; ".join(assessment.diagnostics) or None,
            )
        current = payload
        for step in assessment.migration_path:
            migrator = self._migrators.get(step.migrator_id)
            if migrator is None:
                raise AIxPersistedPayloadMigrationError(f"configuration migrator {step.migrator_id!r} is not registered")
            result = migrator.migrate(AIcConfigurationMigrationRequest(current, step.to_version))
            if result.configuration_schema_id != declaration.schema_id or result.configuration_schema_version != step.to_version:
                raise AIxPersistedPayloadMigrationError(
                    f"configuration migrator {step.migrator_id!r} returned unexpected schema "
                    f"{result.configuration_schema_id}/{result.configuration_schema_version}; expected "
                    f"{declaration.schema_id}/{step.to_version}"
                )
            current = AIcConfigurationPersistedPayload(
                configuration_target=current.configuration_target,
                configuration_schema_id=result.configuration_schema_id,
                configuration_schema_version=result.configuration_schema_version,
                written_by_component_version=written_by_component_version,
                values=dict(result.values),
                policies={key: tuple(value) for key, value in result.policies.items()},
                metadata=dict(current.metadata),
            )
        return current

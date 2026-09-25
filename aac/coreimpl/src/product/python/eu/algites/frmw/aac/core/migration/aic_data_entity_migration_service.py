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

def _migration_path(
    source_version: int,
    target_version: int,
    steps: tuple[AIcSchemaMigrationStepDescriptor, ...],
) -> tuple[AIcSchemaMigrationStepDescriptor, ...]:
    if source_version == target_version:
        return ()
    by_source: dict[int, list[AIcSchemaMigrationStepDescriptor]] = {}
    for step in steps:
        by_source.setdefault(step.from_version, []).append(step)
    for values in by_source.values():
        values.sort(key=lambda item: (item.to_version, item.migrator_id))
    queue = deque([(source_version, ())])
    seen = {source_version}
    while queue:
        version, path = queue.popleft()
        for step in by_source.get(version, ()):
            candidate = path + (step,)
            if step.to_version == target_version:
                return candidate
            if step.to_version not in seen:
                seen.add(step.to_version)
                queue.append((step.to_version, candidate))
    return ()

class AIcDataEntityMigrationService:
    def __init__(self, migrators: Mapping[str, AIiDataEntityMigrator] | None = None) -> None:
        self._migrators = dict(migrators or {})

    def register(self, migrator_id: str, migrator: AIiDataEntityMigrator) -> None:
        if not migrator_id:
            raise ValueError("migrator_id must not be empty")
        self._migrators[migrator_id] = migrator

    def assess(
        self,
        envelope: AIcDataEntityEnvelope,
        support: AIcDataEntitySupportDescriptor,
    ) -> AIcSchemaCompatibilityAssessment:
        if envelope.schema_id != support.schema_id:
            return AIcSchemaCompatibilityAssessment(
                envelope.schema_id, envelope.schema_version,
                support.preferred_write_version or envelope.schema_version, False,
                AInSchemaRuntimeInterpretation.UNSUPPORTED, (),
                (f"stored schema id {envelope.schema_id!r} differs from supported {support.schema_id!r}",),
            )
        target = support.preferred_write_version or envelope.schema_version
        at_target = support.preferred_write_version is not None and envelope.schema_version == target
        path = _migration_path(envelope.schema_version, target, support.migrations) if support.preferred_write_version is not None else ()
        if envelope.schema_version in support.readable_versions:
            return AIcSchemaCompatibilityAssessment(
                envelope.schema_id, envelope.schema_version, target, at_target,
                AInSchemaRuntimeInterpretation.DIRECT, path, (),
            )
        if path:
            return AIcSchemaCompatibilityAssessment(
                envelope.schema_id, envelope.schema_version, target, False,
                AInSchemaRuntimeInterpretation.TRANSFORMED, path, (),
            )
        return AIcSchemaCompatibilityAssessment(
            envelope.schema_id, envelope.schema_version, target, False,
            AInSchemaRuntimeInterpretation.UNSUPPORTED, (),
            (f"stored data entity schema version {envelope.schema_version} is not readable and no explicit transformation path exists",),
        )

    def migrate_to_preferred_write_version(
        self,
        envelope: AIcDataEntityEnvelope,
        support: AIcDataEntitySupportDescriptor,
    ) -> AIcDataEntityEnvelope:
        target = support.preferred_write_version
        if target is None:
            raise AIxPersistedSchemaIncompatible(
                envelope.schema_id, envelope.schema_version, envelope.schema_version,
                "data entity support is read-only and declares no preferred write version",
            )
        assessment = self.assess(envelope, support)
        if assessment.at_target_write_version:
            return envelope
        if not assessment.migration_path:
            raise AIxPersistedSchemaIncompatible(
                envelope.schema_id, envelope.schema_version, target,
                "; ".join(assessment.diagnostics) or None,
            )
        current = envelope
        for step in assessment.migration_path:
            migrator = self._migrators.get(step.migrator_id)
            if migrator is None:
                raise AIxPersistedPayloadMigrationError(f"data entity migrator {step.migrator_id!r} is not registered")
            result = migrator.migrate(AIcDataEntityMigrationRequest(current, step.to_version))
            if result.schema_id != support.schema_id or result.schema_version != step.to_version:
                raise AIxPersistedPayloadMigrationError(
                    f"data entity migrator {step.migrator_id!r} returned unexpected schema "
                    f"{result.schema_id}/{result.schema_version}; expected {support.schema_id}/{step.to_version}"
                )
            current = AIcDataEntityEnvelope(
                uid=current.uid,
                schema_id=result.schema_id,
                schema_version=result.schema_version,
                record_revision=current.record_revision,
                state=current.state,
                payload=result.payload,
            )
        return current

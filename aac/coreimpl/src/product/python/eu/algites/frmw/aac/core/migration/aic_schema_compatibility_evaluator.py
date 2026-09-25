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

class AIcSchemaCompatibilityEvaluator:
    def assess(
        self,
        schema_id: str,
        schema_version: int,
        declaration: AIcPersistedSchemaDescriptor,
    ) -> AIcSchemaCompatibilityAssessment:
        at_write = schema_id == declaration.schema_id and schema_version == declaration.write_version
        if schema_id != declaration.schema_id:
            return AIcSchemaCompatibilityAssessment(
                schema_id, schema_version, declaration.write_version, False,
                AInSchemaRuntimeInterpretation.UNSUPPORTED, (),
                (f"stored schema id {schema_id!r} differs from declared {declaration.schema_id!r}",),
            )

        # Migration availability is independent from direct runtime readability.  A directly
        # readable old representation may also have a migration path used only for optional
        # persistence convergence.
        path = _migration_path(schema_version, declaration.write_version, declaration.migrations)
        if schema_version in declaration.readable_versions:
            return AIcSchemaCompatibilityAssessment(
                schema_id, schema_version, declaration.write_version, at_write,
                AInSchemaRuntimeInterpretation.DIRECT, path, (),
            )
        if path:
            return AIcSchemaCompatibilityAssessment(
                schema_id, schema_version, declaration.write_version, False,
                AInSchemaRuntimeInterpretation.TRANSFORMED, path, (),
            )
        direction = "newer" if schema_version > declaration.write_version else "unsupported"
        return AIcSchemaCompatibilityAssessment(
            schema_id, schema_version, declaration.write_version, False,
            AInSchemaRuntimeInterpretation.UNSUPPORTED, (),
            (f"stored schema version {schema_version} is {direction} and no safe direct reader or explicit transformation path exists",),
        )

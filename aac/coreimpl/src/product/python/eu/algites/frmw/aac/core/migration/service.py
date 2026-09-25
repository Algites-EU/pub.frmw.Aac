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
from .aic_configuration_migration_service import AIcConfigurationMigrationService
from .aic_data_entity_migration_service import AIcDataEntityMigrationService

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

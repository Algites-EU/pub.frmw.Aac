from __future__ import annotations

from collections import deque
from typing import Mapping

from algites.lib.aac.coreintf.configuration import (
    AIcConfigurationMigrationRequest,
    AIcConfigurationPersistedPayload,
    AIiConfigurationMigrator,
)
from algites.lib.aac.coreintf.descriptor import (
    AIcEntityExtensionDataDescriptor, AIcPersistedSchemaDescriptor, AIcSchemaMigrationStepDescriptor,
)
from algites.lib.aac.coreintf.errors import AIxPersistedSchemaIncompatible
from algites.lib.aac.coreintf.extensions import (
    AIcCoreEntityContext,
    AIcEntityExtensionDataEnvelope,
    AIcEntityExtensionMigrationRequest,
    AIiEntityExtensionDataMigrator,
)
from algites.lib.aac.coreintf.migration import AInSchemaRuntimeInterpretation, AIcSchemaCompatibilityAssessment

from .errors import AIxPersistedPayloadMigrationError


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


class AIcEntityExtensionMigrationService:
    def __init__(self, migrators: Mapping[str, AIiEntityExtensionDataMigrator] | None = None) -> None:
        self._migrators = dict(migrators or {})
        self.compatibility = AIcSchemaCompatibilityEvaluator()

    def register(self, migrator_id: str, migrator: AIiEntityExtensionDataMigrator) -> None:
        if not migrator_id:
            raise ValueError("migrator_id must not be empty")
        self._migrators[migrator_id] = migrator

    def assess(
        self,
        entity_context: AIcCoreEntityContext,
        envelope: AIcEntityExtensionDataEnvelope,
        extension_data: AIcEntityExtensionDataDescriptor,
    ) -> AIcSchemaCompatibilityAssessment:
        declaration = extension_data.component_extension_schema
        if declaration is None:
            return AIcSchemaCompatibilityAssessment(
                envelope.component_extension_schema_id, envelope.component_extension_schema_version,
                envelope.component_extension_schema_version, False, AInSchemaRuntimeInterpretation.UNSUPPORTED,
                (), ("entity extension does not declare component-extension data",),
            )
        if not extension_data.supports_core_entity_schema(
            entity_context.core_entity_schema_id, entity_context.core_entity_schema_version
        ):
            return AIcSchemaCompatibilityAssessment(
                envelope.component_extension_schema_id, envelope.component_extension_schema_version,
                declaration.write_version, False, AInSchemaRuntimeInterpretation.UNSUPPORTED,
                (),
                (f"current Core entity schema {entity_context.core_entity_schema_id}/{entity_context.core_entity_schema_version} "
                 "is not declared compatible by the component",),
            )
        return self.compatibility.assess(
            envelope.component_extension_schema_id, envelope.component_extension_schema_version, declaration
        )

    def migrate_to_write_version(
        self,
        entity_context: AIcCoreEntityContext,
        envelope: AIcEntityExtensionDataEnvelope,
        extension_data: AIcEntityExtensionDataDescriptor,
        *,
        written_by_component_version: int,
    ) -> AIcEntityExtensionDataEnvelope:
        declaration = extension_data.component_extension_schema
        if declaration is None:
            raise AIxPersistedSchemaIncompatible(
                envelope.component_extension_schema_id, envelope.component_extension_schema_version,
                envelope.component_extension_schema_version, "entity extension does not declare component-extension data"
            )
        assessment = self.assess(entity_context, envelope, extension_data)
        if assessment.at_target_write_version:
            return envelope
        if not assessment.migration_path:
            raise AIxPersistedSchemaIncompatible(
                envelope.component_extension_schema_id,
                envelope.component_extension_schema_version,
                declaration.write_version,
                "; ".join(assessment.diagnostics) or None,
            )
        current = envelope
        for step in assessment.migration_path:
            migrator = self._migrators.get(step.migrator_id)
            if migrator is None:
                raise AIxPersistedPayloadMigrationError(f"component-extension migrator {step.migrator_id!r} is not registered")
            result = migrator.migrate(AIcEntityExtensionMigrationRequest(entity_context, current, step.to_version))
            if result.component_extension_schema_id != declaration.schema_id or result.component_extension_schema_version != step.to_version:
                raise AIxPersistedPayloadMigrationError(
                    f"component-extension migrator {step.migrator_id!r} returned unexpected schema "
                    f"{result.component_extension_schema_id}/{result.component_extension_schema_version}; expected "
                    f"{declaration.schema_id}/{step.to_version}"
                )
            current = AIcEntityExtensionDataEnvelope(
                owner_component_id=current.owner_component_id,
                component_extension_schema_id=result.component_extension_schema_id,
                component_extension_schema_version=result.component_extension_schema_version,
                written_by_component_version=written_by_component_version,
                core_entity=current.core_entity,
                payload=result.payload,
                payload_format=current.payload_format,
                metadata=dict(current.metadata),
            )
        return current

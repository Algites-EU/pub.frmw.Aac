import pytest

from algites.lib.aac.coreintf.configuration import (
    AInConfigurationPolicyMode,
    AInConfigurationTargetKind,
    AIcConfigurationMigrationResult,
    AIcConfigurationPersistedPayload,
    AIcConfigurationPolicy,
    AIcConfigurationTarget,
    AIiConfigurationMigrator,
)
from algites.lib.aac.coreintf.dataentity import (
    AInDataEntityState,
    AIcDataEntityEnvelope,
    AIcDataEntityMigrationResult,
    AIiDataEntityMigrator,
)
from algites.lib.aac.coreintf.descriptor import (
    AIcDataEntitySupportDescriptor,
    AIcPersistedSchemaDescriptor,
    AIcSchemaMigrationStepDescriptor,
)
from algites.lib.aac.coreintf.errors import AIxPersistedSchemaIncompatible
from algites.lib.aac.coreintf.migration import AInPersistenceConvergenceStatus, AInSchemaRuntimeInterpretation
from algites.lib.aac.coreimpl import (
    AIcConfigurationMigrationService,
    AIcDataEntityMigrationService,
    AIcSchemaCompatibilityEvaluator,
)


class TestConfigMigrator(AIiConfigurationMigrator):
    __test__ = False

    def migrate(self, request):
        values = dict(request.source.values)
        values["new_name"] = values.pop("old_name")
        policies = dict(request.source.policies)
        policies["new_name"] = policies.pop("old_name")
        return AIcConfigurationMigrationResult(
            request.source.configuration_schema_id,
            request.target_configuration_schema_version,
            values,
            policies,
        )


class TestDataEntityMigrator(AIiDataEntityMigrator):
    __test__ = False

    def migrate(self, request):
        payload = dict(request.source.payload)
        payload["migrated_to"] = request.target_schema_version
        return AIcDataEntityMigrationResult(
            request.source.schema_id,
            request.target_schema_version,
            payload,
        )


def schema_decl(*, write=2, readable=(1, 2), steps=()):
    return AIcPersistedSchemaDescriptor("vendor.foo.schema", write, readable, tuple(steps))


def data_entity_support(*, readable=(1, 2), writable=(1, 2), preferred=2, steps=()):
    return AIcDataEntitySupportDescriptor(
        "vendor.foo.data", tuple(readable), tuple(writable), preferred, tuple(steps)
    )


def test_runtime_interpretation_is_independent_from_write_version_and_migration_path():
    evaluator = AIcSchemaCompatibilityEvaluator()
    declaration = schema_decl(write=2, readable=(1, 2))

    current = evaluator.assess("vendor.foo.schema", 2, declaration)
    assert current.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT
    assert current.at_target_write_version

    old_direct = evaluator.assess("vendor.foo.schema", 1, declaration)
    assert old_direct.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT
    assert not old_direct.at_target_write_version

    too_new = evaluator.assess("vendor.foo.schema", 3, declaration)
    assert too_new.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED

    transformable = schema_decl(
        write=2,
        readable=(2,),
        steps=(AIcSchemaMigrationStepDescriptor(3, 2, "down"),),
    )
    assessed = evaluator.assess("vendor.foo.schema", 3, transformable)
    assert assessed.runtime_interpretation is AInSchemaRuntimeInterpretation.TRANSFORMED
    assert [step.migrator_id for step in assessed.migration_path] == ["down"]

    directly_readable_with_optional_convergence = schema_decl(
        write=2,
        readable=(1, 2),
        steps=(AIcSchemaMigrationStepDescriptor(1, 2, "up"),),
    )
    assessed = evaluator.assess("vendor.foo.schema", 1, directly_readable_with_optional_convergence)
    assert assessed.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT
    assert [step.migrator_id for step in assessed.migration_path] == ["up"]
    assert assessed.persistence_convergence_status(safe_persistence_available=True) is AInPersistenceConvergenceStatus.SUPPORTED
    assert assessed.persistence_convergence_status(safe_persistence_available=False) is AInPersistenceConvergenceStatus.NOT_SUPPORTED


def test_configuration_migration_transforms_values_and_policies_together():
    target = AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, "vendor.foo", "instance-1")
    payload = AIcConfigurationPersistedPayload(
        target, "vendor.foo.schema", 1, 1,
        values={"old_name": 30},
        policies={"old_name": (AIcConfigurationPolicy(AInConfigurationPolicyMode.MAX, 60),)},
    )
    declaration = schema_decl(
        write=2,
        readable=(1, 2),
        steps=(AIcSchemaMigrationStepDescriptor(1, 2, "rename"),),
    )
    service = AIcConfigurationMigrationService({"rename": TestConfigMigrator()})
    migrated = service.migrate_to_write_version(payload, declaration, written_by_component_version=2)
    assert migrated.configuration_schema_version == 2
    assert migrated.values == {"new_name": 30}
    assert migrated.policies["new_name"][0].mode is AInConfigurationPolicyMode.MAX
    assert migrated.written_by_component_version == 2


def test_unsupported_newer_configuration_is_preserved_by_contract_as_incompatible():
    target = AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, "vendor.foo")
    payload = AIcConfigurationPersistedPayload(target, "vendor.foo.schema", 3, 2, values={"future": True})
    service = AIcConfigurationMigrationService()
    with pytest.raises(AIxPersistedSchemaIncompatible):
        service.migrate_to_write_version(payload, schema_decl(write=2, readable=(1, 2)), written_by_component_version=1)
    assert payload.values == {"future": True}


def test_data_entity_migration_preserves_identity_revision_and_tombstone_state():
    envelope = AIcDataEntityEnvelope(
        "node-1", "vendor.foo.data", 1, "rev-7", AInDataEntityState.TOMBSTONE, {"setting": "x"}
    )
    support = data_entity_support(
        readable=(1, 2),
        writable=(1, 2),
        preferred=2,
        steps=(AIcSchemaMigrationStepDescriptor(1, 2, "entity"),),
    )
    service = AIcDataEntityMigrationService({"entity": TestDataEntityMigrator()})
    migrated = service.migrate_to_preferred_write_version(envelope, support)
    assert migrated.uid == "node-1"
    assert migrated.schema_id == "vendor.foo.data"
    assert migrated.schema_version == 2
    assert migrated.record_revision == "rev-7"
    assert migrated.state is AInDataEntityState.TOMBSTONE
    assert migrated.payload == {"setting": "x", "migrated_to": 2}


def test_directly_readable_data_entity_can_have_optional_migration_path():
    envelope = AIcDataEntityEnvelope(
        "node-1", "vendor.foo.data", 1, 1, AInDataEntityState.ACTIVE, {"x": 1}
    )
    support = data_entity_support(
        steps=(AIcSchemaMigrationStepDescriptor(1, 2, "entity"),),
    )
    service = AIcDataEntityMigrationService({"entity": TestDataEntityMigrator()})
    assessment = service.assess(envelope, support)
    assert assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT
    assert [step.migrator_id for step in assessment.migration_path] == ["entity"]


def test_unsupported_data_entity_schema_is_rejected_without_mutating_payload():
    envelope = AIcDataEntityEnvelope(
        "node-1", "vendor.foo.data", 3, 9, AInDataEntityState.ACTIVE, {"future": True}
    )
    support = data_entity_support(readable=(1, 2), writable=(2,), preferred=2)
    service = AIcDataEntityMigrationService()
    assessment = service.assess(envelope, support)
    assert assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED
    with pytest.raises(AIxPersistedSchemaIncompatible):
        service.migrate_to_preferred_write_version(envelope, support)
    assert envelope.payload == {"future": True}

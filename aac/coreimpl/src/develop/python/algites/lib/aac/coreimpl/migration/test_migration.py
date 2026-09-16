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
from algites.lib.aac.coreintf.descriptor import (
    AInEntityExtensionDataAccess, AIcCoreEntitySchemaCompatibilityDescriptor,
    AIcEntityExtensionDataDescriptor, AIcPersistedSchemaDescriptor, AIcSchemaMigrationStepDescriptor,
)
from algites.lib.aac.coreintf.errors import AIxPersistedSchemaIncompatible
from algites.lib.aac.coreintf.extensions import (
    AIcCoreEntityContext,
    AIcCoreEntityRef,
    AIcEntityExtensionDataEnvelope,
    AIcEntityExtensionMigrationResult,
    AIiEntityExtensionDataMigrator,
)
from algites.lib.aac.coreintf.migration import AInPersistenceConvergenceStatus, AInSchemaRuntimeInterpretation
from algites.lib.aac.coreimpl import (
    AIcConfigurationMigrationService,
    AIcEntityExtensionMigrationService,
    AIcInMemoryEntityExtensionDataStore,
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


class TestExtensionMigrator(AIiEntityExtensionDataMigrator):
    __test__ = False

    def __init__(self):
        self.seen_core_schema = None

    def migrate(self, request):
        self.seen_core_schema = (
            request.entity_context.core_entity_schema_id,
            request.entity_context.core_entity_schema_version,
        )
        payload = dict(request.source.payload)
        payload["node_schema_version_seen"] = request.entity_context.core_entity_schema_version
        return AIcEntityExtensionMigrationResult(
            request.source.component_extension_schema_id,
            request.target_component_extension_schema_version,
            payload,
        )


def schema_decl(*, write=2, readable=(1, 2), steps=()):
    return AIcPersistedSchemaDescriptor("vendor.foo.schema", write, readable, tuple(steps))


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


def test_component_extension_migration_receives_current_core_entity_schema_context():
    entity = AIcCoreEntityRef("_AO.NodeDefinition", "node-1")
    entity_context = AIcCoreEntityContext(entity, "_AO.NodeDefinition", 5, {"id": "node-1"})
    envelope = AIcEntityExtensionDataEnvelope(
        "vendor.foo", "vendor.foo.schema", 1, 1, entity, {"setting": "x"}
    )
    declaration = schema_decl(
        write=2,
        readable=(1, 2),
        steps=(AIcSchemaMigrationStepDescriptor(1, 2, "ext"),),
    )
    extension_data = AIcEntityExtensionDataDescriptor(
        AInEntityExtensionDataAccess.READ_WRITE, declaration,
        (AIcCoreEntitySchemaCompatibilityDescriptor("_AO.NodeDefinition", (4, 5)),),
    )
    migrator = TestExtensionMigrator()
    service = AIcEntityExtensionMigrationService({"ext": migrator})
    migrated = service.migrate_to_write_version(
        entity_context, envelope, extension_data, written_by_component_version=2
    )
    assert migrator.seen_core_schema == ("_AO.NodeDefinition", 5)
    assert migrated.component_extension_schema_version == 2
    assert migrated.payload["node_schema_version_seen"] == 5
    assert migrated.core_entity == entity


def test_one_core_entity_can_store_many_components_but_only_one_payload_per_component():
    store = AIcInMemoryEntityExtensionDataStore()
    entity = AIcCoreEntityRef("_AO.NodeDefinition", "node-1")
    store.put(AIcEntityExtensionDataEnvelope("vendor.foo", "foo.ext", 1, 1, entity, {"v": 1}))
    store.put(AIcEntityExtensionDataEnvelope("vendor.bar", "bar.ext", 1, 1, entity, {"v": 2}))
    assert {item.owner_component_id for item in store.enumerate(entity)} == {"vendor.foo", "vendor.bar"}
    current = store.get_record(entity, "vendor.foo")
    store.put(
        AIcEntityExtensionDataEnvelope("vendor.foo", "foo.ext", 2, 2, entity, {"v": 3}),
        expected_record_revision=current.record_revision,
    )
    assert len(store.enumerate(entity)) == 2
    assert store.get(entity, "vendor.foo").payload == {"v": 3}


def test_component_extension_is_incompatible_when_current_core_entity_schema_is_unsupported():
    entity = AIcCoreEntityRef("_AO.NodeDefinition", "node-1")
    entity_context = AIcCoreEntityContext(entity, "_AO.NodeDefinition", 6, {"id": "node-1"})
    envelope = AIcEntityExtensionDataEnvelope("vendor.foo", "vendor.foo.schema", 2, 2, entity, {"x": 1})
    extension_data = AIcEntityExtensionDataDescriptor(
        AInEntityExtensionDataAccess.READ_WRITE, schema_decl(write=2, readable=(2,)),
        (AIcCoreEntitySchemaCompatibilityDescriptor("_AO.NodeDefinition", (4, 5)),),
    )
    service = AIcEntityExtensionMigrationService()
    assessment = service.assess(entity_context, envelope, extension_data)
    assert assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED
    with pytest.raises(AIxPersistedSchemaIncompatible):
        service.migrate_to_write_version(entity_context, envelope, extension_data, written_by_component_version=2)

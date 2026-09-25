import pytest

from algites.frmw.aac.coreintf.configuration import (
    AInConfigurationMutationOperation,
    AInConfigurationPolicyMode,
    AInConfigurationTargetKind,
    AIcConfigurationChange,
    AIcConfigurationChangeSet,
    AIcConfigurationPolicy,
    AIcConfigurationProviderRequest,
    AIcConfigurationTarget,
)
from algites.frmw.aac.coreintf.context import AIcConfigurationScope
from algites.frmw.aac.coreintf.persistence import AInPersistenceCapability
from algites.frmw.aac.coreimpl.configuration_providers import AIcFileSystemConfigurationProvider
from algites.frmw.aac.coreimpl.errors import AIxConfigurationRevisionConflict


def _target():
    return AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, "vendor.foo", "i-1")


def _change_set(expected=None, value="https://one"):
    return AIcConfigurationChangeSet(
        AIcConfigurationScope("WORKSPACE", "w-1"), "fs", _target(),
        (
            AIcConfigurationChange("url", AInConfigurationMutationOperation.SET_VALUE, value, True),
            AIcConfigurationChange("timeout", AInConfigurationMutationOperation.SET_POLICY,
                                   policy_modes=(AIcConfigurationPolicy(AInConfigurationPolicyMode.MAX, 30),)),
        ),
        expected_record_revision=expected,
        configuration_schema_id="foo-config",
        configuration_schema_version=1,
        written_by_component_version=2,
        actor_context={"component_id": "vendor.foo"},
    )


def test_filesystem_provider_atomic_change_set_roundtrip(tmp_path):
    provider = AIcFileSystemConfigurationProvider(tmp_path)
    result = provider.apply_changes(_change_set())
    assert result.record_revision == 1
    request = AIcConfigurationProviderRequest(_target(), AIcConfigurationScope("WORKSPACE", "w-1"))
    snapshot = provider.snapshot(request)
    assert snapshot is not None
    assert snapshot.payload.values["url"] == "https://one"
    assert snapshot.payload.policies["timeout"][0].mode is AInConfigurationPolicyMode.MAX
    assert snapshot.payload.configuration_schema_id == "foo-config"

    second = provider.apply_changes(_change_set(1, "https://two"))
    assert second.record_revision == 2
    assert provider.snapshot(request).payload.values["url"] == "https://two"


def test_filesystem_provider_rejects_stale_revision(tmp_path):
    provider = AIcFileSystemConfigurationProvider(tmp_path)
    provider.apply_changes(_change_set())
    with pytest.raises(AIxConfigurationRevisionConflict):
        provider.apply_changes(_change_set(0, "https://stale"))


def test_read_only_filesystem_provider_exposes_no_write_capability(tmp_path):
    provider = AIcFileSystemConfigurationProvider(tmp_path, read_only=True)
    caps = {item.value for item in provider.capabilities(AIcConfigurationProviderRequest(_target(), AIcConfigurationScope("SYSTEM")))}
    assert caps == {"READ"}


def test_versioned_snapshot_is_migrated_and_rewritten_atomically(tmp_path):
    from algites.frmw.aac.coreintf.configuration import (
        AIcConfigurationMigrationResult, AIiConfigurationMigrator,
    )
    from algites.frmw.aac.coreintf.descriptor import AIcPersistedSchemaDescriptor, AIcSchemaMigrationStepDescriptor
    from algites.frmw.aac.coreimpl.configuration import AIcConfigurationProviderRegistry, AIcConfigurationReadService
    from algites.frmw.aac.coreimpl.migration import AIcConfigurationMigrationService
    from algites.frmw.aac.coreimpl.schemas import AIcSchemaRegistry

    class AIcTestMigrator(AIiConfigurationMigrator):
        def migrate(self, request):
            values = dict(request.source.values)
            values["new_name"] = values.pop("old_name")
            return AIcConfigurationMigrationResult("foo-config", 2, values, request.source.policies)

    provider = AIcFileSystemConfigurationProvider(tmp_path)
    target = _target()
    scope = AIcConfigurationScope("WORKSPACE", "w-1")
    provider.apply_changes(AIcConfigurationChangeSet(
        scope, "fs", target,
        (AIcConfigurationChange("old_name", AInConfigurationMutationOperation.SET_VALUE, "x", True),),
        configuration_schema_id="foo-config", configuration_schema_version=1, written_by_component_version=1,
    ))
    registry = AIcConfigurationProviderRegistry(); registry.register("fs", provider)
    migrations = AIcConfigurationMigrationService({"1-to-2": AIcTestMigrator()})
    schemas = AIcSchemaRegistry()
    schemas.register("foo-config_2.json", {"x-aac-schema-id": "foo-config", "x-aac-schema-version": 2, "type": "object", "properties": {"new_name": {"type": "string"}}, "required": ["new_name"]})
    declaration = AIcPersistedSchemaDescriptor(
        "foo-config", 2, (2,), (AIcSchemaMigrationStepDescriptor(1, 2, "1-to-2"),), "foo-config_2.json"
    )
    service = AIcConfigurationReadService(registry, migrations, lambda target: (declaration, 2), schemas)
    contributions = service.contributions("fs", AIcConfigurationProviderRequest(target, scope))
    assert [(item.property_id, item.value) for item in contributions] == [("new_name", "x")]
    migrated = provider.snapshot(AIcConfigurationProviderRequest(target, scope))
    assert migrated.payload.configuration_schema_version == 2
    assert migrated.payload.written_by_component_version == 2
    assert migrated.record_revision == 2


def test_directly_readable_old_snapshot_is_not_migrated_on_read_even_when_path_exists(tmp_path):
    from algites.frmw.aac.coreintf.configuration import (
        AIcConfigurationMigrationResult, AIiConfigurationMigrator,
    )
    from algites.frmw.aac.coreintf.descriptor import AIcPersistedSchemaDescriptor, AIcSchemaMigrationStepDescriptor
    from algites.frmw.aac.coreimpl.configuration import AIcConfigurationProviderRegistry, AIcConfigurationReadService
    from algites.frmw.aac.coreimpl.migration import AIcConfigurationMigrationService
    from algites.frmw.aac.coreimpl.schemas import AIcSchemaRegistry

    class SameShapeMigrator(AIiConfigurationMigrator):
        def migrate(self, request):
            return AIcConfigurationMigrationResult("foo-config", 2, dict(request.source.values), request.source.policies)

    provider = AIcFileSystemConfigurationProvider(tmp_path)
    target = _target(); scope = AIcConfigurationScope("WORKSPACE", "w-1")
    provider.apply_changes(AIcConfigurationChangeSet(
        scope, "fs", target,
        (AIcConfigurationChange("url", AInConfigurationMutationOperation.SET_VALUE, "https://old", True),),
        configuration_schema_id="foo-config", configuration_schema_version=1, written_by_component_version=1,
    ))
    registry = AIcConfigurationProviderRegistry(); registry.register("fs", provider)
    migrations = AIcConfigurationMigrationService({"1-to-2": SameShapeMigrator()})
    schemas = AIcSchemaRegistry()
    schemas.register("foo-config_1.json", {"x-aac-schema-id": "foo-config", "x-aac-schema-version": 1, "type": "object", "properties": {"url": {"type": "string"}}})
    schemas.register("foo-config_2.json", {"x-aac-schema-id": "foo-config", "x-aac-schema-version": 2, "type": "object", "properties": {"url": {"type": "string"}}})
    declaration = AIcPersistedSchemaDescriptor(
        "foo-config", 2, (1, 2), (AIcSchemaMigrationStepDescriptor(1, 2, "1-to-2"),), "foo-config_2.json"
    )
    service = AIcConfigurationReadService(registry, migrations, lambda target: (declaration, 2), schemas)
    contributions = service.contributions("fs", AIcConfigurationProviderRequest(target, scope))
    assert [(item.property_id, item.value) for item in contributions] == [("url", "https://old")]
    stored = provider.snapshot(AIcConfigurationProviderRequest(target, scope))
    assert stored.payload.configuration_schema_version == 1
    assert stored.record_revision == 1


def test_filesystem_provider_persistence_capabilities_are_record_level(tmp_path):
    request = AIcConfigurationProviderRequest(_target(), AIcConfigurationScope("WORKSPACE", "w-1"))
    writable = AIcFileSystemConfigurationProvider(tmp_path / "rw")
    read_only = AIcFileSystemConfigurationProvider(tmp_path / "ro", read_only=True)
    assert writable.persistence_capabilities(request) == (
        AInPersistenceCapability.READ,
        AInPersistenceCapability.SINGLE_RECORD_CAS,
    )
    assert read_only.persistence_capabilities(request) == (AInPersistenceCapability.READ,)


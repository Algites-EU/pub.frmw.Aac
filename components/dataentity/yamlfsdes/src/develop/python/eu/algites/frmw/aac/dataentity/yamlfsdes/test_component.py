from importlib import resources

from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader


def test_component_descriptor_declares_one_provider_with_all_nine_data_entity_capabilities():
    descriptor = AIcDescriptorLoader.load_package("eu.algites.frmw.aac.dataentity.yamlfsdes")
    assert descriptor.id == "_AAC.component.dataentity.yamlfsdes"
    assert len(descriptor.capability_providers) == 1
    provider = descriptor.capability_providers[0]
    assert provider.id == "yamlfsdes"
    assert {capability.id for capability in provider.capabilities} == {
        "_AAC.data-entity.get-record",
        "_AAC.data-entity.query-records",
        "_AAC.data-entity.apply-direct-record-changes",
        "_AAC.data-entity.inspect-storage-support",
        "_AAC.data-entity.ensure-storage-support",
        "_AAC.data-entity.retire-storage-support",
        "_AAC.data-entity.create-storage-backup",
        "_AAC.data-entity.inspect-storage-backup",
        "_AAC.data-entity.restore-storage-backup",
    }
    assert all(capability.versions == (1,) for capability in provider.capabilities)
    assert provider.initial_instances == ()


def test_component_descriptor_and_configuration_schema_are_packaged_resources():
    package = resources.files("eu.algites.frmw.aac.dataentity.yamlfsdes")
    assert package.joinpath("component.yml").is_file()
    assert package.joinpath("schemas/yamlfsdes-config_1.json").is_file()


def test_provider_results_conform_to_builtin_capability_contract_schemas(tmp_path):
    from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
    from eu.algites.frmw.aac.core.invocation.dispatcher import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
    from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
    from eu.algites.frmw.aac.dataentity.yamlfsdes import AIcYamlFsDataEntityStorageProvider

    runtime = AIcYamlFsDataEntityStorageProvider({"RootDirectory": str(tmp_path / "data")})
    endpoint = AIcObjectCapabilityEndpoint(runtime)
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    dispatcher = AIcInvocationDispatcher(catalog)

    def invoke(capability_id, operation_id, arguments):
        output = dispatcher.invoke(endpoint, AIcInvocationInput(
            invocation_id=f"{operation_id}-1",
            parent_invocation_id=None,
            capability_id=capability_id,
            capability_version=1,
            operation_id=operation_id,
            provider_instance_id="yamlfsdes-1",
            arguments=arguments,
        ))
        assert output.success, output.error
        return output.result

    ensure_result = invoke(
        "_AAC.data-entity.ensure-storage-support",
        "ensure",
        {
            "SchemaId": "test.entity",
            "SchemaVersion": 1,
            "CanonicalSchema": {"type": "object", "properties": {"Name": {"type": "string"}}},
            "References": [],
        },
    )
    assert ensure_result["Status"] == "ready"
    apply_result = invoke(
        "_AAC.data-entity.apply-direct-record-changes",
        "apply",
        {"Changes": [{
            "ChangeId": "create-1",
            "Type": "create_record",
            "SchemaId": "test.entity",
            "Uid": "u1",
            "SchemaVersion": 1,
            "State": "active",
            "Payload": {"Name": "A"},
        }]},
    )
    assert apply_result["Changes"][0]["RecordRevision"] == 1
    get_result = invoke(
        "_AAC.data-entity.get-record",
        "get",
        {"SchemaId": "test.entity", "Uid": "u1"},
    )
    assert get_result["Record"]["Payload"] == {"Name": "A"}
    query_result = invoke(
        "_AAC.data-entity.query-records",
        "query",
        {"SchemaId": "test.entity", "StoredSchemaVersionFilter": [1]},
    )
    assert len(query_result["Records"]) == 1
    backup_file = tmp_path / "dispatcher-backup.zip"
    backup_result = invoke(
        "_AAC.data-entity.create-storage-backup",
        "create_backup",
        {"BackupFile": str(backup_file)},
    )
    assert backup_result["Format"] == "zip"
    inspect_backup_result = invoke(
        "_AAC.data-entity.inspect-storage-backup",
        "inspect_backup",
        {"BackupFile": str(backup_file)},
    )
    assert inspect_backup_result["Status"] == "valid"

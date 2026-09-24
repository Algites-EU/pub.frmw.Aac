from importlib import resources

from algites.lib.aac.coreimpl.descriptor import AIcDescriptorLoader


def test_component_descriptor_declares_one_provider_with_all_nine_data_entity_capabilities():
    descriptor = AIcDescriptorLoader.load_package("algites.lib.aac.dataentity.yamlfsdes")
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
    package = resources.files("algites.lib.aac.dataentity.yamlfsdes")
    assert package.joinpath("component.yml").is_file()
    assert package.joinpath("schemas/yamlfsdes-config_1.json").is_file()


def test_provider_results_conform_to_builtin_capability_contract_schemas(tmp_path):
    from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
    from algites.lib.aac.coreimpl.invocation import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
    from algites.lib.aac.coreintf.invocation import AIcInvocationInput
    from algites.lib.aac.dataentity.yamlfsdes import AIcYamlFsDataEntityStorageProvider

    runtime = AIcYamlFsDataEntityStorageProvider({"root_directory": str(tmp_path / "data")})
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
            "schema_id": "test.entity",
            "schema_version": 1,
            "canonical_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "references": [],
        },
    )
    assert ensure_result["status"] == "READY"
    apply_result = invoke(
        "_AAC.data-entity.apply-direct-record-changes",
        "apply",
        {"changes": [{
            "change_id": "create-1",
            "type": "CREATE_RECORD",
            "schema_id": "test.entity",
            "uid": "u1",
            "schema_version": 1,
            "state": "ACTIVE",
            "payload": {"name": "A"},
        }]},
    )
    assert apply_result["changes"][0]["record_revision"] == 1
    get_result = invoke(
        "_AAC.data-entity.get-record",
        "get",
        {"schema_id": "test.entity", "uid": "u1"},
    )
    assert get_result["record"]["payload"] == {"name": "A"}
    query_result = invoke(
        "_AAC.data-entity.query-records",
        "query",
        {"schema_id": "test.entity", "stored_schema_version_filter": [1]},
    )
    assert len(query_result["records"]) == 1
    backup_file = tmp_path / "dispatcher-backup.zip"
    backup_result = invoke(
        "_AAC.data-entity.create-storage-backup",
        "create_backup",
        {"backup_file": str(backup_file)},
    )
    assert backup_result["format"] == "ZIP"
    inspect_backup_result = invoke(
        "_AAC.data-entity.inspect-storage-backup",
        "inspect_backup",
        {"backup_file": str(backup_file)},
    )
    assert inspect_backup_result["status"] == "VALID"

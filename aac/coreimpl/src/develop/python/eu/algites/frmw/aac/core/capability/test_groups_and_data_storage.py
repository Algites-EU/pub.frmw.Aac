import pytest

from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog, AIcCapabilityGroupCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxContractAdmissionError, AIxContractConflictError


def test_builtin_capability_groups_are_nested_and_all_builtin_contracts_are_grouped():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    assert catalog.groups.get("_AAC.data-entity.loading").parent_group_id == "_AAC.data-entity"
    assert catalog.groups.get("_AAC.runtime.observation").parent_group_id == "_AAC.runtime"
    expected = {
        "_AAC.capability.observation": "_AAC.runtime.observation",
        "_AAC.data-entity.get-record": "_AAC.data-entity.loading",
        "_AAC.data-entity.query-records": "_AAC.data-entity.loading",
        "_AAC.data-entity.apply-direct-record-changes": "_AAC.data-entity.storing",
        "_AAC.data-entity.inspect-storage-support": "_AAC.data-entity.storage-management",
        "_AAC.data-entity.ensure-storage-support": "_AAC.data-entity.storage-management",
        "_AAC.data-entity.retire-storage-support": "_AAC.data-entity.storage-management",
    }
    for capability_id, group_id in expected.items():
        assert catalog.get(capability_id, 1).group_id == group_id


def test_group_definition_deduplicates_but_conflicting_definition_is_rejected():
    groups = AIcCapabilityGroupCatalog()
    text = """
Group:
  Id: vendor.storage
  Name: Vendor storage
"""
    first = groups.admit_text(text, source="a")
    second = groups.admit_text(text, source="b")
    assert first.fingerprint == second.fingerprint
    with pytest.raises(AIxContractConflictError):
        groups.admit_text("""
Group:
  Id: vendor.storage
  Name: Different name
""", source="c")


def test_contract_with_unknown_group_is_rejected():
    catalog = AIcActiveContractCatalog()
    with pytest.raises(AIxContractAdmissionError, match="unknown group"):
        catalog.admit_text("""
Capability:
  Id: vendor.capability
  Version: 1
  GroupId: vendor.missing
Operations:
  - Id: run
""")


def test_direct_changes_schema_enforces_expected_revision_for_replace_and_delete():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    schema = "data-entity-apply-direct-record-changes-request_1.json"
    valid = {"Changes": [{
        "ChangeId": "c1", "Type": "replace_record", "SchemaId": "x", "Uid": "u1",
        "SchemaVersion": 2, "State": "active", "Payload": {"v": 1}, "ExpectedRecordRevision": 4
    }]}
    assert catalog.schema_registry.normalize(schema, valid, apply_defaults=False) == valid
    invalid = {"Changes": [{
        "ChangeId": "c1", "Type": "delete_record", "SchemaId": "x", "Uid": "u1"
    }]}
    with pytest.raises(Exception):
        catalog.schema_registry.normalize(schema, invalid, apply_defaults=False)


def test_query_schema_applies_portable_defaults():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    value = catalog.schema_registry.normalize("data-entity-query-records-request_1.json", {"SchemaId": "x"})
    assert value["States"] == ["active"]
    assert value["ReferenceMatch"] == "all"
    assert value["Order"] == "uid_asc"
    assert "limit" not in value


def test_builtin_data_storage_contracts_generate_python_bindings():
    from eu.algites.frmw.aac.codegen import AIcPythonCapabilityBindingGenerator

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    generator = AIcPythonCapabilityBindingGenerator(catalog.schema_registry)
    capability_ids = (
        "_AAC.data-entity.get-record",
        "_AAC.data-entity.query-records",
        "_AAC.data-entity.apply-direct-record-changes",
        "_AAC.data-entity.inspect-storage-support",
        "_AAC.data-entity.ensure-storage-support",
        "_AAC.data-entity.retire-storage-support",
    )
    for capability_id in capability_ids:
        source = generator.generate(catalog.get(capability_id, 1))
        namespace = {}
        exec(source, namespace)
        assert any(name.startswith("AIig") for name in namespace)

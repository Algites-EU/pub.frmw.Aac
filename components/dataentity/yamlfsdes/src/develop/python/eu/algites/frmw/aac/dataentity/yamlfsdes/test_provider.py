from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

import pytest
import yaml

from eu.algites.frmw.aac.dataentity.yamlfsdes import AIcYamlFsDataEntityStorageProvider


SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "x-aac-schema-id": "test.entity",
    "x-aac-schema-version": 1,
    "type": "object",
    "properties": {
        "Name": {"type": "string"},
        "site_uid": {
            "type": "string",
            "x-aac-data-entity-reference": {"SchemaId": "test.site"},
        },
    },
}
SCHEMA_V2 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "x-aac-schema-id": "test.entity",
    "x-aac-schema-version": 2,
    "type": "object",
    "properties": {
        "Name": {"type": "string"},
        "site_uid": {
            "type": "string",
            "x-aac-data-entity-reference": {"SchemaId": "test.site"},
        },
        "Description": {"type": "string"},
    },
}
REFERENCES = [{"SchemaPath": ["properties", "site_uid"], "TargetSchemaId": "test.site"}]


def provider(tmp_path: Path) -> AIcYamlFsDataEntityStorageProvider:
    return AIcYamlFsDataEntityStorageProvider({"RootDirectory": str(tmp_path / "storage")})


def ensure(value: AIcYamlFsDataEntityStorageProvider, version: int, schema=None):
    return value.ensure_1({
        "SchemaId": "test.entity",
        "SchemaVersion": version,
        "CanonicalSchema": schema or (SCHEMA_V1 if version == 1 else SCHEMA_V2),
        "References": REFERENCES,
    })


def create(value: AIcYamlFsDataEntityStorageProvider, uid: str, *, version: int = 1, site_uid: str = "site-1"):
    return value.apply_1({
        "Changes": [{
            "ChangeId": f"create-{uid}",
            "Type": "create_record",
            "SchemaId": "test.entity",
            "Uid": uid,
            "SchemaVersion": version,
            "State": "active",
            "Payload": {"Name": uid, "site_uid": site_uid},
        }]
    })


def test_ensure_create_get_and_self_describing_yaml_layout(tmp_path):
    value = provider(tmp_path)
    assert ensure(value, 1)["Status"] == "ready"
    result = create(value, "u1")
    assert result["Changes"][0]["RecordRevision"] == 1

    path = tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw == {
        "Uid": "u1",
        "SchemaId": "test.entity",
        "SchemaVersion": 1,
        "RecordRevision": 1,
        "State": "active",
        "Payload": {"Name": "u1", "site_uid": "site-1"},
    }
    assert value.get_1({"SchemaId": "test.entity", "Uid": "u1"})["Record"] == raw


def test_replace_can_move_record_between_stored_schema_versions_and_increments_revision(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    ensure(value, 2)
    create(value, "u1")

    result = value.apply_1({"Changes": [{
        "ChangeId": "upgrade-u1",
        "Type": "replace_record",
        "SchemaId": "test.entity",
        "Uid": "u1",
        "SchemaVersion": 2,
        "State": "active",
        "Payload": {"Name": "u1-new", "site_uid": "site-1", "Description": "v2"},
        "ExpectedRecordRevision": 1,
    }]})
    assert result["Changes"][0]["RecordRevision"] == 2
    assert not (tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml").exists()
    assert (tmp_path / "storage" / "data" / "test.entity" / "2" / "u1.yml").is_file()
    record = value.get_1({"SchemaId": "test.entity", "Uid": "u1"})["Record"]
    assert record["SchemaVersion"] == 2
    assert record["RecordRevision"] == 2


def test_stale_revision_rejects_complete_changeset_without_partial_create(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "existing")

    with pytest.raises(RuntimeError, match="revision conflict"):
        value.apply_1({"Changes": [
            {
                "ChangeId": "create-new",
                "Type": "create_record",
                "SchemaId": "test.entity",
                "Uid": "new",
                "SchemaVersion": 1,
                "State": "active",
                "Payload": {"Name": "new", "site_uid": "site-1"},
            },
            {
                "ChangeId": "stale",
                "Type": "replace_record",
                "SchemaId": "test.entity",
                "Uid": "existing",
                "SchemaVersion": 1,
                "State": "active",
                "Payload": {"Name": "changed", "site_uid": "site-1"},
                "ExpectedRecordRevision": 999,
            },
        ]})
    assert value.get_1({"SchemaId": "test.entity", "Uid": "new"}) == {"Record": None}
    assert value.get_1({"SchemaId": "test.entity", "Uid": "existing"})["Record"]["RecordRevision"] == 1


def test_incomplete_committing_transaction_is_completed_before_next_provider_read(tmp_path, monkeypatch):
    value = provider(tmp_path)
    ensure(value, 1)
    original_copy = value._atomic_copy

    def fail_second_record(source, target):
        if target.name == "u2.yml":
            raise OSError("simulated commit interruption")
        original_copy(source, target)

    monkeypatch.setattr(value, "_atomic_copy", fail_second_record)
    with pytest.raises(OSError, match="simulated"):
        value.apply_1({"Changes": [
            {
                "ChangeId": "c1", "Type": "create_record", "SchemaId": "test.entity", "Uid": "u1",
                "SchemaVersion": 1, "State": "active", "Payload": {"Name": "u1", "site_uid": "site-1"},
            },
            {
                "ChangeId": "c2", "Type": "create_record", "SchemaId": "test.entity", "Uid": "u2",
                "SchemaVersion": 1, "State": "active", "Payload": {"Name": "u2", "site_uid": "site-1"},
            },
        ]})

    monkeypatch.setattr(value, "_atomic_copy", original_copy)
    result = value.query_1({"SchemaId": "test.entity"})
    assert [record["Uid"] for record in result["Records"]] == ["u1", "u2"]
    transactions = tmp_path / "storage" / "journal" / "record-changes"
    assert not transactions.exists() or not any(transactions.iterdir())


def test_query_supports_stored_version_uid_state_reference_order_and_pagination_filters(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    ensure(value, 2)
    create(value, "u1", version=1, site_uid="site-a")
    create(value, "u2", version=2, site_uid="site-b")
    create(value, "u3", version=2, site_uid="site-a")

    filtered = value.query_1({
        "SchemaId": "test.entity",
        "StoredSchemaVersionFilter": [2],
        "References": [{"Target": {"SchemaId": "test.site", "Uid": "site-a"}}],
    })
    assert [record["Uid"] for record in filtered["Records"]] == ["u3"]

    first = value.query_1({"SchemaId": "test.entity", "Order": "uid_desc", "Limit": 2})
    assert [record["Uid"] for record in first["Records"]] == ["u3", "u2"]
    assert first["ContinuationToken"] is not None
    second = value.query_1({
        "SchemaId": "test.entity",
        "Order": "uid_desc",
        "Limit": 2,
        "ContinuationToken": first["ContinuationToken"],
    })
    assert [record["Uid"] for record in second["Records"]] == ["u1"]
    assert second["ContinuationToken"] is None


def test_storage_support_retire_reactivate_and_conflicting_canonical_schema(tmp_path):
    value = provider(tmp_path)
    first = ensure(value, 1)
    assert first["Changed"] is True
    assert ensure(value, 1)["Changed"] is False
    retired = value.retire_1({"SchemaId": "test.entity", "SchemaVersion": 1})
    assert retired["Status"] == "retired"
    assert retired["Changed"] is True
    assert value.inspect_1({"SchemaId": "test.entity", "SchemaVersion": 1})["Status"] == "retired"
    with pytest.raises(RuntimeError, match="retired"):
        create(value, "u1")
    assert ensure(value, 1)["Status"] == "ready"

    conflicting = dict(SCHEMA_V1)
    conflicting["title"] = "Different canonical definition"
    result = ensure(value, 1, conflicting)
    assert result["Status"] == "incompatible"
    assert result["Changed"] is False


def test_duplicate_uid_across_physical_versions_is_detected_as_corruption(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    ensure(value, 2)
    create(value, "u1")
    source = tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml"
    duplicate = tmp_path / "storage" / "data" / "test.entity" / "2" / "u1.yml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    raw["SchemaVersion"] = 2
    duplicate.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicate stored Data Entity identity"):
        value.get_1({"SchemaId": "test.entity", "Uid": "u1"})


def test_path_segments_reject_traversal(tmp_path):
    value = provider(tmp_path)
    with pytest.raises(ValueError, match="portable filesystem"):
        value.get_1({"SchemaId": "../escape", "Uid": "u1"})



def test_schema_metadata_is_durable_beside_records_and_runtime_metadata_is_rebuildable(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "u1")
    schema_file = tmp_path / "storage" / "data" / "test.entity" / "1" / ".schema.yml"
    schema_metadata = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    assert schema_metadata["CanonicalSchema"] == SCHEMA_V1
    assert schema_metadata["canonical_digest"]

    runtime_metadata = tmp_path / "storage" / ".yamlfsdes"
    shutil.rmtree(runtime_metadata)
    assert value.get_1({"SchemaId": "test.entity", "Uid": "u1"})["Record"]["Uid"] == "u1"
    assert value.inspect_1({"SchemaId": "test.entity", "SchemaVersion": 1})["Status"] == "ready"
    assert runtime_metadata.is_dir()


def test_missing_durable_schema_metadata_with_records_is_incompatible_and_ensure_will_not_relabel_data(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "u1")
    schema_file = tmp_path / "storage" / "data" / "test.entity" / "1" / ".schema.yml"
    schema_file.unlink()
    assert value.inspect_1({"SchemaId": "test.entity", "SchemaVersion": 1})["Status"] == "incompatible"
    result = ensure(value, 1)
    assert result["Status"] == "incompatible"
    assert not schema_file.exists()


def test_backup_zip_contains_self_contained_data_tree_and_can_restore_empty_storage(tmp_path):
    source = provider(tmp_path)
    ensure(source, 1)
    create(source, "u1")
    backup = tmp_path / "backup.zip"
    result = source.create_backup_1({"BackupFile": str(backup)})
    assert result["Format"] == "zip"
    assert result["RecordCount"] == 1
    with zipfile.ZipFile(backup) as archive:
        names = set(archive.namelist())
        assert "backup.yml" in names
        assert "data/test.entity/1/.schema.yml" in names
        assert "data/test.entity/1/u1.yml" in names
        assert not any(name.startswith("journal/") or name.startswith(".yamlfsdes/") for name in names)
    assert source.inspect_backup_1({"BackupFile": str(backup)})["Status"] == "valid"

    target_root = tmp_path / "restored"
    target = AIcYamlFsDataEntityStorageProvider({"RootDirectory": str(target_root)})
    restored = target.restore_backup_1({"BackupFile": str(backup)})
    assert restored["Mode"] == "empty_only"
    assert target.get_1({"SchemaId": "test.entity", "Uid": "u1"})["Record"]["Payload"]["Name"] == "u1"
    assert (target_root / "data" / "test.entity" / "1" / ".schema.yml").is_file()


def test_restore_empty_only_refuses_existing_data_and_replace_all_replaces_it(tmp_path):
    source_root = tmp_path / "source"
    source = AIcYamlFsDataEntityStorageProvider({"RootDirectory": str(source_root)})
    ensure(source, 1)
    create(source, "source-record")
    backup = tmp_path / "replace.zip"
    source.create_backup_1({"BackupFile": str(backup)})

    target_root = tmp_path / "target"
    target = AIcYamlFsDataEntityStorageProvider({"RootDirectory": str(target_root)})
    ensure(target, 1)
    create(target, "old-record")
    with pytest.raises(RuntimeError, match="empty_only"):
        target.restore_backup_1({"BackupFile": str(backup)})
    assert target.get_1({"SchemaId": "test.entity", "Uid": "old-record"})["Record"] is not None

    target.restore_backup_1({"BackupFile": str(backup), "Mode": "replace_all"})
    assert target.get_1({"SchemaId": "test.entity", "Uid": "old-record"})["Record"] is None
    assert target.get_1({"SchemaId": "test.entity", "Uid": "source-record"})["Record"] is not None
    restore_journal = target_root / "journal" / "restore"
    assert not restore_journal.exists() or not any(restore_journal.iterdir())


def test_full_backup_validation_rejects_semantically_invalid_record_even_when_integrity_matches(tmp_path):
    import hashlib

    source = provider(tmp_path)
    ensure(source, 1)
    create(source, "u1")
    backup = tmp_path / "semantic-invalid.zip"
    source.create_backup_1({"BackupFile": str(backup)})

    with zipfile.ZipFile(backup, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    record = yaml.safe_load(files["data/test.entity/1/u1.yml"].decode("utf-8"))
    record["Payload"]["Name"] = 123
    files["data/test.entity/1/u1.yml"] = yaml.safe_dump(record, sort_keys=False).encode("utf-8")
    manifest = yaml.safe_load(files["backup.yml"].decode("utf-8"))
    for entry in manifest["files"]:
        if entry["Path"] == "data/test.entity/1/u1.yml":
            content = files[entry["Path"]]
            entry["size"] = len(content)
            entry["Sha256"] = hashlib.sha256(content).hexdigest()
    files["backup.yml"] = yaml.safe_dump(manifest, sort_keys=False).encode("utf-8")
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    assert source.inspect_backup_1({"BackupFile": str(backup), "ValidationLevel": "integrity"})["Status"] == "valid"
    full = source.inspect_backup_1({"BackupFile": str(backup), "ValidationLevel": "full"})
    assert full["Status"] == "invalid"
    assert "canonical schema" in full["Diagnostics"][0]


def test_query_without_limit_returns_all_matching_records(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    changes = [
        {
            "ChangeId": f"create-u{index:03d}",
            "Type": "create_record",
            "SchemaId": "test.entity",
            "Uid": f"u{index:03d}",
            "SchemaVersion": 1,
            "State": "active",
            "Payload": {"Name": f"u{index:03d}", "site_uid": "site-1"},
        }
        for index in range(105)
    ]
    value.apply_1({"Changes": changes})
    result = value.query_1({"SchemaId": "test.entity"})
    assert len(result["Records"]) == 105
    assert result["ContinuationToken"] is None


def test_on_demand_delta_replays_every_unacknowledged_delta_on_new_request():
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController
    from eu.algites.frmw.aac.core.invocation.api import (
        AInStateResultDeliveryMode,
        AIcOperationInteractionCallerToProviderMessage,
        operation_interaction_context,
    )
    from eu.algites.frmw.aac.dataentity.yamlfsdes.provider import AIcOperationStateResultPublisher

    messages = []
    controller = AIcOperationInteractionController(
        messages.append,
        caller_state=AIcOperationInteractionCallerToProviderMessage(
            state_result_delivery_mode=AInStateResultDeliveryMode.ON_DEMAND_DELTA,
        ),
    )
    with operation_interaction_context(controller):
        publisher = AIcOperationStateResultPublisher()
        publisher.publish(complete={"Values": [1]}, delta={"Values": [1]})
        publisher.publish(complete={"Values": [1, 2]}, delta={"Values": [2]})
        controller.request_state_result()
        publisher.publish(complete={"Values": [1, 2, 3]}, delta={"Values": [3]})
        delivered = [
            (message.state_result_payload_revision, message.state_result)
            for message in messages
            if message.state_result_payload_revision is not None
        ]
        assert delivered[-3:] == [
            (1, {"Values": [1]}),
            (2, {"Values": [2]}),
            (3, {"Values": [3]}),
        ]

        controller.accept_state_result_revision(2)
        controller.request_state_result()
        publisher.publish(complete={"Values": [1, 2, 3, 4]}, delta={"Values": [4]})
        delivered = [
            (message.state_result_payload_revision, message.state_result)
            for message in messages
            if message.state_result_payload_revision is not None
        ]
        assert delivered[-2:] == [
            (3, {"Values": [3]}),
            (4, {"Values": [4]}),
        ]

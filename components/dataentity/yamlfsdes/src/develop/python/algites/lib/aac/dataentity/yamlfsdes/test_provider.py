from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

import pytest
import yaml

from algites.lib.aac.dataentity.yamlfsdes import AIcYamlFsDataEntityStorageProvider


SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "x-aac-schema-id": "test.entity",
    "x-aac-schema-version": 1,
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "site_uid": {
            "type": "string",
            "x-aac-data-entity-reference": {"schema_id": "test.site"},
        },
    },
}
SCHEMA_V2 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "x-aac-schema-id": "test.entity",
    "x-aac-schema-version": 2,
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "site_uid": {
            "type": "string",
            "x-aac-data-entity-reference": {"schema_id": "test.site"},
        },
        "description": {"type": "string"},
    },
}
REFERENCES = [{"schema_path": ["properties", "site_uid"], "target_schema_id": "test.site"}]


def provider(tmp_path: Path) -> AIcYamlFsDataEntityStorageProvider:
    return AIcYamlFsDataEntityStorageProvider({"root_directory": str(tmp_path / "storage")})


def ensure(value: AIcYamlFsDataEntityStorageProvider, version: int, schema=None):
    return value.ensure_1({
        "schema_id": "test.entity",
        "schema_version": version,
        "canonical_schema": schema or (SCHEMA_V1 if version == 1 else SCHEMA_V2),
        "references": REFERENCES,
    })


def create(value: AIcYamlFsDataEntityStorageProvider, uid: str, *, version: int = 1, site_uid: str = "site-1"):
    return value.apply_1({
        "changes": [{
            "change_id": f"create-{uid}",
            "type": "CREATE_RECORD",
            "schema_id": "test.entity",
            "uid": uid,
            "schema_version": version,
            "state": "ACTIVE",
            "payload": {"name": uid, "site_uid": site_uid},
        }]
    })


def test_ensure_create_get_and_self_describing_yaml_layout(tmp_path):
    value = provider(tmp_path)
    assert ensure(value, 1)["status"] == "READY"
    result = create(value, "u1")
    assert result["changes"][0]["record_revision"] == 1

    path = tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw == {
        "uid": "u1",
        "schema_id": "test.entity",
        "schema_version": 1,
        "record_revision": 1,
        "state": "ACTIVE",
        "payload": {"name": "u1", "site_uid": "site-1"},
    }
    assert value.get_1({"schema_id": "test.entity", "uid": "u1"})["record"] == raw


def test_replace_can_move_record_between_stored_schema_versions_and_increments_revision(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    ensure(value, 2)
    create(value, "u1")

    result = value.apply_1({"changes": [{
        "change_id": "upgrade-u1",
        "type": "REPLACE_RECORD",
        "schema_id": "test.entity",
        "uid": "u1",
        "schema_version": 2,
        "state": "ACTIVE",
        "payload": {"name": "u1-new", "site_uid": "site-1", "description": "v2"},
        "expected_record_revision": 1,
    }]})
    assert result["changes"][0]["record_revision"] == 2
    assert not (tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml").exists()
    assert (tmp_path / "storage" / "data" / "test.entity" / "2" / "u1.yml").is_file()
    record = value.get_1({"schema_id": "test.entity", "uid": "u1"})["record"]
    assert record["schema_version"] == 2
    assert record["record_revision"] == 2


def test_stale_revision_rejects_complete_changeset_without_partial_create(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "existing")

    with pytest.raises(RuntimeError, match="revision conflict"):
        value.apply_1({"changes": [
            {
                "change_id": "create-new",
                "type": "CREATE_RECORD",
                "schema_id": "test.entity",
                "uid": "new",
                "schema_version": 1,
                "state": "ACTIVE",
                "payload": {"name": "new", "site_uid": "site-1"},
            },
            {
                "change_id": "stale",
                "type": "REPLACE_RECORD",
                "schema_id": "test.entity",
                "uid": "existing",
                "schema_version": 1,
                "state": "ACTIVE",
                "payload": {"name": "changed", "site_uid": "site-1"},
                "expected_record_revision": 999,
            },
        ]})
    assert value.get_1({"schema_id": "test.entity", "uid": "new"}) == {"record": None}
    assert value.get_1({"schema_id": "test.entity", "uid": "existing"})["record"]["record_revision"] == 1


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
        value.apply_1({"changes": [
            {
                "change_id": "c1", "type": "CREATE_RECORD", "schema_id": "test.entity", "uid": "u1",
                "schema_version": 1, "state": "ACTIVE", "payload": {"name": "u1", "site_uid": "site-1"},
            },
            {
                "change_id": "c2", "type": "CREATE_RECORD", "schema_id": "test.entity", "uid": "u2",
                "schema_version": 1, "state": "ACTIVE", "payload": {"name": "u2", "site_uid": "site-1"},
            },
        ]})

    monkeypatch.setattr(value, "_atomic_copy", original_copy)
    result = value.query_1({"schema_id": "test.entity"})
    assert [record["uid"] for record in result["records"]] == ["u1", "u2"]
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
        "schema_id": "test.entity",
        "stored_schema_version_filter": [2],
        "references": [{"target": {"schema_id": "test.site", "uid": "site-a"}}],
    })
    assert [record["uid"] for record in filtered["records"]] == ["u3"]

    first = value.query_1({"schema_id": "test.entity", "order": "UID_DESC", "limit": 2})
    assert [record["uid"] for record in first["records"]] == ["u3", "u2"]
    assert first["continuation_token"] is not None
    second = value.query_1({
        "schema_id": "test.entity",
        "order": "UID_DESC",
        "limit": 2,
        "continuation_token": first["continuation_token"],
    })
    assert [record["uid"] for record in second["records"]] == ["u1"]
    assert second["continuation_token"] is None


def test_storage_support_retire_reactivate_and_conflicting_canonical_schema(tmp_path):
    value = provider(tmp_path)
    first = ensure(value, 1)
    assert first["changed"] is True
    assert ensure(value, 1)["changed"] is False
    retired = value.retire_1({"schema_id": "test.entity", "schema_version": 1})
    assert retired["status"] == "RETIRED"
    assert retired["changed"] is True
    assert value.inspect_1({"schema_id": "test.entity", "schema_version": 1})["status"] == "RETIRED"
    with pytest.raises(RuntimeError, match="RETIRED"):
        create(value, "u1")
    assert ensure(value, 1)["status"] == "READY"

    conflicting = dict(SCHEMA_V1)
    conflicting["title"] = "Different canonical definition"
    result = ensure(value, 1, conflicting)
    assert result["status"] == "INCOMPATIBLE"
    assert result["changed"] is False


def test_duplicate_uid_across_physical_versions_is_detected_as_corruption(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    ensure(value, 2)
    create(value, "u1")
    source = tmp_path / "storage" / "data" / "test.entity" / "1" / "u1.yml"
    duplicate = tmp_path / "storage" / "data" / "test.entity" / "2" / "u1.yml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    duplicate.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicate stored Data Entity identity"):
        value.get_1({"schema_id": "test.entity", "uid": "u1"})


def test_path_segments_reject_traversal(tmp_path):
    value = provider(tmp_path)
    with pytest.raises(ValueError, match="portable filesystem"):
        value.get_1({"schema_id": "../escape", "uid": "u1"})



def test_schema_metadata_is_durable_beside_records_and_runtime_metadata_is_rebuildable(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "u1")
    schema_file = tmp_path / "storage" / "data" / "test.entity" / "1" / ".schema.yml"
    schema_metadata = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    assert schema_metadata["canonical_schema"] == SCHEMA_V1
    assert schema_metadata["canonical_digest"]

    runtime_metadata = tmp_path / "storage" / ".yamlfsdes"
    shutil.rmtree(runtime_metadata)
    assert value.get_1({"schema_id": "test.entity", "uid": "u1"})["record"]["uid"] == "u1"
    assert value.inspect_1({"schema_id": "test.entity", "schema_version": 1})["status"] == "READY"
    assert runtime_metadata.is_dir()


def test_missing_durable_schema_metadata_with_records_is_incompatible_and_ensure_will_not_relabel_data(tmp_path):
    value = provider(tmp_path)
    ensure(value, 1)
    create(value, "u1")
    schema_file = tmp_path / "storage" / "data" / "test.entity" / "1" / ".schema.yml"
    schema_file.unlink()
    assert value.inspect_1({"schema_id": "test.entity", "schema_version": 1})["status"] == "INCOMPATIBLE"
    result = ensure(value, 1)
    assert result["status"] == "INCOMPATIBLE"
    assert not schema_file.exists()


def test_backup_zip_contains_self_contained_data_tree_and_can_restore_empty_storage(tmp_path):
    source = provider(tmp_path)
    ensure(source, 1)
    create(source, "u1")
    backup = tmp_path / "backup.zip"
    result = source.create_backup_1({"backup_file": str(backup)})
    assert result["format"] == "ZIP"
    assert result["record_count"] == 1
    with zipfile.ZipFile(backup) as archive:
        names = set(archive.namelist())
        assert "backup.yml" in names
        assert "data/test.entity/1/.schema.yml" in names
        assert "data/test.entity/1/u1.yml" in names
        assert not any(name.startswith("journal/") or name.startswith(".yamlfsdes/") for name in names)
    assert source.inspect_backup_1({"backup_file": str(backup)})["status"] == "VALID"

    target_root = tmp_path / "restored"
    target = AIcYamlFsDataEntityStorageProvider({"root_directory": str(target_root)})
    restored = target.restore_backup_1({"backup_file": str(backup)})
    assert restored["mode"] == "EMPTY_ONLY"
    assert target.get_1({"schema_id": "test.entity", "uid": "u1"})["record"]["payload"]["name"] == "u1"
    assert (target_root / "data" / "test.entity" / "1" / ".schema.yml").is_file()


def test_restore_empty_only_refuses_existing_data_and_replace_all_replaces_it(tmp_path):
    source_root = tmp_path / "source"
    source = AIcYamlFsDataEntityStorageProvider({"root_directory": str(source_root)})
    ensure(source, 1)
    create(source, "source-record")
    backup = tmp_path / "replace.zip"
    source.create_backup_1({"backup_file": str(backup)})

    target_root = tmp_path / "target"
    target = AIcYamlFsDataEntityStorageProvider({"root_directory": str(target_root)})
    ensure(target, 1)
    create(target, "old-record")
    with pytest.raises(RuntimeError, match="EMPTY_ONLY"):
        target.restore_backup_1({"backup_file": str(backup)})
    assert target.get_1({"schema_id": "test.entity", "uid": "old-record"})["record"] is not None

    target.restore_backup_1({"backup_file": str(backup), "mode": "REPLACE_ALL"})
    assert target.get_1({"schema_id": "test.entity", "uid": "old-record"})["record"] is None
    assert target.get_1({"schema_id": "test.entity", "uid": "source-record"})["record"] is not None
    restore_journal = target_root / "journal" / "restore"
    assert not restore_journal.exists() or not any(restore_journal.iterdir())


def test_full_backup_validation_rejects_semantically_invalid_record_even_when_integrity_matches(tmp_path):
    import hashlib

    source = provider(tmp_path)
    ensure(source, 1)
    create(source, "u1")
    backup = tmp_path / "semantic-invalid.zip"
    source.create_backup_1({"backup_file": str(backup)})

    with zipfile.ZipFile(backup, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    record = yaml.safe_load(files["data/test.entity/1/u1.yml"].decode("utf-8"))
    record["payload"]["name"] = 123
    files["data/test.entity/1/u1.yml"] = yaml.safe_dump(record, sort_keys=False).encode("utf-8")
    manifest = yaml.safe_load(files["backup.yml"].decode("utf-8"))
    for entry in manifest["files"]:
        if entry["path"] == "data/test.entity/1/u1.yml":
            content = files[entry["path"]]
            entry["size"] = len(content)
            entry["sha256"] = hashlib.sha256(content).hexdigest()
    files["backup.yml"] = yaml.safe_dump(manifest, sort_keys=False).encode("utf-8")
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    assert source.inspect_backup_1({"backup_file": str(backup), "validation_level": "INTEGRITY"})["status"] == "VALID"
    full = source.inspect_backup_1({"backup_file": str(backup), "validation_level": "FULL"})
    assert full["status"] == "INVALID"
    assert "canonical schema" in full["diagnostics"][0]

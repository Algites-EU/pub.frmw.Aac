import pytest

from eu.algites.frmw.aac.core.persistence.api import AIcPersistenceReadExpectation, AIcStateMutation
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceRevisionConflict
from eu.algites.frmw.aac.core.persistence.aic_json_file_state_store import AIcJsonFileStateStore


def test_stale_writer_cannot_overwrite_newer_record(tmp_path):
    path = tmp_path / "state.json"
    first = AIcJsonFileStateStore(path)
    second = AIcJsonFileStateStore(path)

    created = first.put("n", "a", {"Value": 1})
    stale = first.get_record("n", "a")
    assert stale.record_revision == created.record_revision == 1

    second.put("n", "a", {"Value": 2})

    with pytest.raises(AIxPersistenceRevisionConflict):
        first.apply((AIcStateMutation.put(
            "n", "a", {"Value": 3}, expected_record_revision=stale.record_revision
        ),))

    assert first.get("n", "a") == {"Value": 2}
    assert first.get_record("n", "a").record_revision == 2


def test_multi_record_read_set_conflict_aborts_entire_write_set(tmp_path):
    path = tmp_path / "state.json"
    first = AIcJsonFileStateStore(path)
    second = AIcJsonFileStateStore(path)

    first.put("n", "a", {"Value": 1})
    first.put("n", "b", {"Value": 1})
    a = first.get_record("n", "a")
    b = first.get_record("n", "b")

    second.put("n", "b", {"Value": 2})

    with pytest.raises(AIxPersistenceRevisionConflict):
        first.apply(
            (AIcStateMutation.put(
                "n", "a", {"Value": 9}, expected_record_revision=a.record_revision
            ),),
            read_expectations=(AIcPersistenceReadExpectation(
                "n", "b", expected_record_revision=b.record_revision
            ),),
        )

    assert first.get("n", "a") == {"Value": 1}
    assert first.get("n", "b") == {"Value": 2}


def test_legacy_state_store_without_current_format_is_rejected(tmp_path):
    from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceError

    path = tmp_path / "state.json"
    path.write_text('{"n":{"a":{"Value":1}}}', encoding="utf-8")
    store = AIcJsonFileStateStore(path)

    with pytest.raises(AIxPersistenceError, match="format_version 1"):
        store.get_record("n", "a")


def test_current_state_store_writes_format_version_one(tmp_path):
    path = tmp_path / "state.json"
    store = AIcJsonFileStateStore(path)
    store.put("n", "a", {"Value": 1})
    store.put("n", "a", {"Value": 2})

    raw = path.read_text(encoding="utf-8")
    assert '"FormatVersion": 1' in raw
    assert '"RecordRevision": 2' in raw

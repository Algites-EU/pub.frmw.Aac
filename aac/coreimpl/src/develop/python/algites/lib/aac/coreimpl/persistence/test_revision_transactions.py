import pytest

from algites.lib.aac.coreintf.persistence import AIcPersistenceReadExpectation, AIcStateMutation
from algites.lib.aac.coreimpl.errors import AIxPersistenceRevisionConflict
from algites.lib.aac.coreimpl.persistence import AIcJsonFileStateStore


def test_stale_writer_cannot_overwrite_newer_record(tmp_path):
    path = tmp_path / "state.json"
    first = AIcJsonFileStateStore(path)
    second = AIcJsonFileStateStore(path)

    created = first.put("n", "a", {"value": 1})
    stale = first.get_record("n", "a")
    assert stale.record_revision == created.record_revision == 1

    second.put("n", "a", {"value": 2})

    with pytest.raises(AIxPersistenceRevisionConflict):
        first.apply((AIcStateMutation.put(
            "n", "a", {"value": 3}, expected_record_revision=stale.record_revision
        ),))

    assert first.get("n", "a") == {"value": 2}
    assert first.get_record("n", "a").record_revision == 2


def test_multi_record_read_set_conflict_aborts_entire_write_set(tmp_path):
    path = tmp_path / "state.json"
    first = AIcJsonFileStateStore(path)
    second = AIcJsonFileStateStore(path)

    first.put("n", "a", {"value": 1})
    first.put("n", "b", {"value": 1})
    a = first.get_record("n", "a")
    b = first.get_record("n", "b")

    second.put("n", "b", {"value": 2})

    with pytest.raises(AIxPersistenceRevisionConflict):
        first.apply(
            (AIcStateMutation.put(
                "n", "a", {"value": 9}, expected_record_revision=a.record_revision
            ),),
            read_expectations=(AIcPersistenceReadExpectation(
                "n", "b", expected_record_revision=b.record_revision
            ),),
        )

    assert first.get("n", "a") == {"value": 1}
    assert first.get("n", "b") == {"value": 2}


def test_legacy_state_store_is_upgraded_to_revisioned_envelopes(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"n":{"a":{"value":1}}}', encoding="utf-8")
    store = AIcJsonFileStateStore(path)

    record = store.get_record("n", "a")
    assert record.record_revision == 1
    store.put("n", "a", {"value": 2})

    raw = path.read_text(encoding="utf-8")
    assert '"format_version": 2' in raw
    assert '"record_revision": 2' in raw

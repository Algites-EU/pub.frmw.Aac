import pytest
from algites.frmw.aac.coreintf.persistence import AIcStateMutation, AInStateMutationKind
from algites.frmw.aac.coreimpl.errors import AIxPersistenceError
from algites.frmw.aac.coreimpl.persistence import AIcInMemoryStateStore


def test_apply_is_atomic_when_later_mutation_fails():
    store = AIcInMemoryStateStore()
    with pytest.raises(AIxPersistenceError):
        store.apply((
            AIcStateMutation.put("n", "a", {"v": 1}, expect_absent=True),
            AIcStateMutation.put("n", "b", {"v": 2}),
        ))
    assert store.list("n") == {}

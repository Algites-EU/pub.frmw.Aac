import pytest
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AInStateMutationKind
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceError
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore


def test_apply_is_atomic_when_later_mutation_fails():
    store = AIcInMemoryStateStore()
    with pytest.raises(AIxPersistenceError):
        store.apply((
            AIcStateMutation.put("n", "a", {"v": 1}, expect_absent=True),
            AIcStateMutation.put("n", "b", {"v": 2}),
        ))
    assert store.list("n") == {}

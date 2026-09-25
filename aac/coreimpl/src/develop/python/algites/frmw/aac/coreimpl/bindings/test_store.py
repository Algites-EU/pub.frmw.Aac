import pytest

from algites.frmw.aac.coreintf.instances import AIcBinding
from algites.frmw.aac.coreimpl.bindings import AIcBindingStore
from algites.frmw.aac.coreimpl.errors import AIxBindingCycleError
from algites.frmw.aac.coreimpl.persistence import AIcInMemoryStateStore


def b(a, requirement, p):
    return AIcBinding(a, requirement, p, "x", 1)


def test_bindings_are_persistent_and_queryable_by_consumer():
    backing = AIcInMemoryStateStore()
    first = AIcBindingStore(backing)
    first.put(b("A", "r", "B"))
    second = AIcBindingStore(backing)
    assert second.for_consumer("A") == (b("A", "r", "B"),)


def test_binding_store_rejects_cycle_before_commit():
    store = AIcBindingStore()
    store.put(b("A", "r1", "B"))
    with pytest.raises(AIxBindingCycleError):
        store.put(b("B", "r2", "A"))

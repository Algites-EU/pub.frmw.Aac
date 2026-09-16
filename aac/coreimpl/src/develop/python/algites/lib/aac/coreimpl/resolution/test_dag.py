import pytest

from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreimpl.errors import AIxBindingCycleError
from algites.lib.aac.coreimpl.resolution import validate_instance_dag


def binding(a, b):
    return AIcBinding(a, "r", b, "x", 1)


def test_acyclic_instance_graph_is_allowed():
    order = validate_instance_dag([binding("A1", "B1"), binding("B2", "A2")])
    assert set(order) == {"A1", "A2", "B1", "B2"}


def test_direct_self_binding_is_rejected_as_cycle_length_one():
    with pytest.raises(AIxBindingCycleError) as exc:
        validate_instance_dag([binding("A1", "A1")])
    assert exc.value.cycle == ("A1", "A1")


def test_indirect_instance_cycle_is_rejected():
    with pytest.raises(AIxBindingCycleError):
        validate_instance_dag([binding("A1", "B1"), binding("B1", "A1")])

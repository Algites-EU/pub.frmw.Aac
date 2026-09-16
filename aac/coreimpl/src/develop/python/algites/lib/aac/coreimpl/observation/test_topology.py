import pytest
from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.lib.aac.coreintf.observation import AIcObservationBinding, AIcObservationSelector
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.observation import AIcObservationTopologyStore
from algites.lib.aac.coreimpl.persistence import AIcInMemoryStateStore


def test_observation_topology_is_core_owned_and_persistent():
    store = AIcInMemoryStateStore(); catalog = AIcActiveContractCatalog()
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", 1), (AIcCapabilityOperation("run", "In", "Out"),)))
    first = AIcObservationTopologyStore(store, catalog)
    binding = AIcObservationBinding("observer", (AIcObservationSelector("x.cap", (1,), ("run",)),))
    first.put(binding)
    assert AIcObservationTopologyStore(store, catalog).get("observer") == binding


def test_observation_topology_validates_exact_operation_ids():
    catalog = AIcActiveContractCatalog(); catalog.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", 1), (AIcCapabilityOperation("run", "In", "Out"),)))
    topology = AIcObservationTopologyStore(AIcInMemoryStateStore(), catalog)
    with pytest.raises(ValueError, match="unknown operations"):
        topology.put(AIcObservationBinding("observer", (AIcObservationSelector("x.cap", (1,), ("missing",)),)))

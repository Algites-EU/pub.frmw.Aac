import pytest
from algites.frmw.aac.coreintf.capability import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.frmw.aac.coreintf.observation import AIcObservationBinding, AIcObservationSelector
from algites.frmw.aac.coreimpl.capability import AIcActiveContractCatalog
from algites.frmw.aac.coreimpl.observation import AIcObservationTopologyStore
from algites.frmw.aac.coreimpl.persistence import AIcInMemoryStateStore


def test_observation_topology_is_core_owned_and_persistent():
    store = AIcInMemoryStateStore(); catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", 1), "_AAC.runtime", (AIcCapabilityOperation("run"),)))
    first = AIcObservationTopologyStore(store, catalog)
    binding = AIcObservationBinding("observer", (AIcObservationSelector("x.cap", (1,), ("run",)),))
    first.put(binding)
    assert AIcObservationTopologyStore(store, catalog).get("observer") == binding


def test_observation_topology_validates_exact_operation_ids():
    catalog = AIcActiveContractCatalog(); catalog.admit_builtin_contracts(); catalog.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", 1), "_AAC.runtime", (AIcCapabilityOperation("run"),)))
    topology = AIcObservationTopologyStore(AIcInMemoryStateStore(), catalog)
    with pytest.raises(ValueError, match="unknown operations"):
        topology.put(AIcObservationBinding("observer", (AIcObservationSelector("x.cap", (1,), ("missing",)),)))

import pytest

from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.errors import AIxContractConflictError, AIxContractNegotiationError


def contract(version, output="Out"):
    return AIcCapabilityContract(AIcCapabilityRef("x.cap", version), (AIcCapabilityOperation("run", "In", output),))


def test_builtin_observation_contract_is_admitted():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    assert catalog.versions("_AAC.capability.observation") == (1,)
    assert catalog.operation("_AAC.capability.observation", 1, "observe").input_type == "AIcObservationInput"


def test_identical_contract_is_deduplicated_but_conflict_is_rejected():
    catalog = AIcActiveContractCatalog()
    first = catalog.admit(contract(1), source="a")
    second = catalog.admit(contract(1), source="b")
    assert first.fingerprint == second.fingerprint
    with pytest.raises(AIxContractConflictError):
        catalog.admit(contract(1, output="Different"), source="c")


def test_negotiation_uses_highest_common_active_version():
    catalog = AIcActiveContractCatalog()
    for version in (1, 2, 3):
        catalog.admit(contract(version))
    assert catalog.negotiate("x.cap", (2, 3, 4), (1, 3, 4)) == 3
    with pytest.raises(AIxContractNegotiationError):
        catalog.negotiate("x.cap", (4,), (4,))

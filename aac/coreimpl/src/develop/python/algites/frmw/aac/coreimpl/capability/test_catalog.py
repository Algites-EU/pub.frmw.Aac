import pytest

from algites.frmw.aac.coreintf.capability import AInCapabilityOperationInteractionKind, AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.frmw.aac.coreimpl.capability import AIcActiveContractCatalog
from algites.frmw.aac.coreimpl.errors import AIxContractConflictError, AIxContractNegotiationError


def contract(version, output="Out"):
    return AIcCapabilityContract(
        AIcCapabilityRef("x.cap", version), "_AAC.runtime",
        (AIcCapabilityOperation("run", metadata={"test_output_marker": output}),),
    )


def test_builtin_observation_contract_is_admitted():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit_builtin_contracts()
    assert catalog.versions("_AAC.capability.observation") == (1,)
    operation = catalog.operation("_AAC.capability.observation", 1, "observe")
    interaction = operation.interaction(AInCapabilityOperationInteractionKind.INPUT)
    assert interaction is not None
    assert interaction.schema.id == "_AAC.schema.observation-input"


def test_identical_contract_is_deduplicated_but_conflict_is_rejected():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    first = catalog.admit(contract(1), source="a")
    second = catalog.admit(contract(1), source="b")
    assert first.fingerprint == second.fingerprint
    with pytest.raises(AIxContractConflictError):
        catalog.admit(contract(1, output="Different"), source="c")


def test_negotiation_uses_highest_common_active_version():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    for version in (1, 2, 3):
        catalog.admit(contract(version))
    assert catalog.negotiate("x.cap", (2, 3, 4), (1, 3, 4)) == 3
    with pytest.raises(AIxContractNegotiationError):
        catalog.negotiate("x.cap", (4,), (4,))

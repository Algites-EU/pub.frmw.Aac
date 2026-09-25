import pytest

from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef, AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingResolutionError
from eu.algites.frmw.aac.core.resolution.bindings import AIcBindingResolver


def candidate(instance_id, versions=(1, 2)):
    return AIcProviderInstance(instance_id, "c", "p", instance_id, (AIcProvidedCapability("x.cap", versions),), "m:C", state=AInProviderInstanceState.CONFIGURED)


def catalog():
    result = AIcActiveContractCatalog()
    result.admit_builtin_contracts()
    for version in (1, 2):
        result.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", version), "_AAC.runtime", (AIcCapabilityOperation("run"),)))
    return result


def test_binding_stores_negotiated_version_not_provider_max_by_assumption():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1,))
    binding = AIcBindingResolver(catalog()).resolve_single("consumer", requirement, [candidate("p1")])
    assert binding.capability_version == 1


def test_single_is_ambiguous_when_multiple_provider_instances_are_valid():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1, 2))
    with pytest.raises(AIxBindingResolutionError, match="ambiguous"):
        AIcBindingResolver(catalog()).resolve_single("consumer", requirement, [candidate("p1"), candidate("p2")])


def test_multiple_returns_all_compatible_instances():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1, 2), cardinality=AInConsumerCardinality.MULTIPLE)
    bindings = AIcBindingResolver(catalog()).resolve_multiple("consumer", requirement, [candidate("p2"), candidate("p1")])
    assert [binding.provider_instance_id for binding in bindings] == ["p1", "p2"]

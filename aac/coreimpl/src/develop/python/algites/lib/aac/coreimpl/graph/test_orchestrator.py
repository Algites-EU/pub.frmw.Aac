import pytest

from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor, AIcConsumerRequirementDescriptor, AIcProviderDefinitionDescriptor
from algites.lib.aac.coreintf.instances import AIcBindingPreference
from algites.lib.aac.coreimpl.bindings import AIcBindingPreferenceStore, AIcBindingStore
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.errors import AIxBindingCycleError
from algites.lib.aac.coreimpl.graph import AIcApplicationGraphOrchestrator
from algites.lib.aac.coreimpl.instances import AIcProviderInstanceRegistry
from algites.lib.aac.coreimpl.resolution import AIcBindingResolver


def contract(catalog, capability):
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef(capability, 1), (AIcCapabilityOperation("run", "In", "Out"),)))


def test_provider_scoped_requirement_resolves_and_persists():
    catalog = AIcActiveContractCatalog()
    contract(catalog, "cap.x")
    registry = AIcProviderInstanceRegistry()
    provider_x = AIcProviderDefinitionDescriptor("px", "cap.x", (1,), "x:PX")
    consumer = AIcProviderDefinitionDescriptor(
        "pc", "cap.consumer", (1,), "x:PC",
        requirements=(AIcConsumerRequirementDescriptor("x", "cap.x", (1,)),),
    )
    x = registry.create("provider", provider_x)
    c = registry.create("consumer", consumer)
    store = AIcBindingStore(registry.store)
    graph = AIcApplicationGraphOrchestrator(registry, AIcBindingResolver(catalog), store, AIcBindingPreferenceStore(registry.store))
    resolved = graph.resolve({"provider": AIcComponentDescriptor("provider", 1, (provider_x,)), "consumer": AIcComponentDescriptor("consumer", 1, (consumer,))})
    assert resolved.bindings[0].consumer_instance_id == c.id
    assert resolved.bindings[0].provider_instance_id == x.id
    assert store.all() == resolved.bindings


def test_explicit_preferences_can_make_declarative_component_cycle_instance_acyclic():
    catalog = AIcActiveContractCatalog()
    contract(catalog, "cap.x"); contract(catalog, "cap.y")
    rx = AIcConsumerRequirementDescriptor("needs-y", "cap.y", (1,), mandatory=False)
    ry = AIcConsumerRequirementDescriptor("needs-x", "cap.x", (1,), mandatory=False)
    pa = AIcProviderDefinitionDescriptor("pa", "cap.x", (1,), "x:A", requirements=(rx,))
    pb = AIcProviderDefinitionDescriptor("pb", "cap.y", (1,), "x:B", requirements=(ry,))
    registry = AIcProviderInstanceRegistry()
    a1 = registry.create("A", pa, name="a1"); a2 = registry.create("A", pa, name="a2")
    b1 = registry.create("B", pb, name="b1"); b2 = registry.create("B", pb, name="b2")
    preferences = AIcBindingPreferenceStore(registry.store)
    preferences.put(AIcBindingPreference(a1.id, "needs-y", (b1.id,)))
    preferences.put(AIcBindingPreference(b2.id, "needs-x", (a2.id,)))
    graph = AIcApplicationGraphOrchestrator(registry, AIcBindingResolver(catalog), AIcBindingStore(registry.store), preferences)
    resolved = graph.resolve({"A": AIcComponentDescriptor("A", 1, (pa,)), "B": AIcComponentDescriptor("B", 1, (pb,))})
    edges = {(b.consumer_instance_id, b.provider_instance_id) for b in resolved.bindings}
    assert (a1.id, b1.id) in edges and (b2.id, a2.id) in edges


def test_instance_cycle_is_rejected_even_with_two_distinct_instances():
    catalog = AIcActiveContractCatalog(); contract(catalog, "cap.x"); contract(catalog, "cap.y")
    pa = AIcProviderDefinitionDescriptor("pa", "cap.x", (1,), "x:A", requirements=(AIcConsumerRequirementDescriptor("needs-y", "cap.y", (1,)),))
    pb = AIcProviderDefinitionDescriptor("pb", "cap.y", (1,), "x:B", requirements=(AIcConsumerRequirementDescriptor("needs-x", "cap.x", (1,)),))
    registry = AIcProviderInstanceRegistry(); a = registry.create("A", pa); b = registry.create("B", pb)
    preferences = AIcBindingPreferenceStore(registry.store)
    preferences.put(AIcBindingPreference(a.id, "needs-y", (b.id,))); preferences.put(AIcBindingPreference(b.id, "needs-x", (a.id,)))
    graph = AIcApplicationGraphOrchestrator(registry, AIcBindingResolver(catalog), AIcBindingStore(registry.store), preferences)
    with pytest.raises(Exception, match="cycle|resolve"):
        graph.resolve({"A": AIcComponentDescriptor("A", 1, (pa,)), "B": AIcComponentDescriptor("B", 1, (pb,))})

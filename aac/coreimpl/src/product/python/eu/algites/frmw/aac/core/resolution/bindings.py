from __future__ import annotations
from collections import defaultdict
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingCycleError, AIxBindingResolutionError, AIxContractNegotiationError

from .aic_binding_resolver import AIcBindingResolver

ELIGIBLE_STATES = (
    AInProviderInstanceState.CONFIGURED,
    AInProviderInstanceState.ACTIVATABLE,
    AInProviderInstanceState.ACTIVE,
    AInProviderInstanceState.INACTIVE,
)

def validate_instance_dag(bindings: tuple[AIcBinding, ...] | list[AIcBinding]) -> tuple[str, ...]:
    """Validate the *resolved provider-instance* graph, not the declarative component graph."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for binding in bindings:
        adjacency[binding.consumer_instance_id].append(binding.provider_instance_id)
        nodes.add(binding.consumer_instance_id)
        nodes.add(binding.provider_instance_id)

    state: dict[str, int] = {}  # 0 absent, 1 visiting, 2 done
    stack: list[str] = []
    order: list[str] = []

    def visit(node: str) -> None:
        mark = state.get(node, 0)
        if mark == 2:
            return
        if mark == 1:
            start = stack.index(node)
            raise AIxBindingCycleError(tuple(stack[start:] + [node]))
        state[node] = 1
        stack.append(node)
        for target in adjacency.get(node, ()):
            visit(target)
        stack.pop()
        state[node] = 2
        order.append(node)

    for node in sorted(nodes):
        visit(node)
    order.reverse()
    return tuple(order)

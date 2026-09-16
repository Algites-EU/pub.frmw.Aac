from __future__ import annotations

from collections import defaultdict

from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import AIcConsumerRequirementDescriptor
from algites.lib.aac.coreintf.instances import AIcBinding, AIcProviderInstance, AInProviderInstanceState

from .contracts import AIcActiveContractCatalog
from .errors import AIxBindingCycleError, AIxBindingResolutionError, AIxContractNegotiationError


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


class AIcBindingResolver:
    def __init__(self, contract_catalog: AIcActiveContractCatalog | None = None) -> None:
        self.contract_catalog = contract_catalog

    def _negotiated_version(self, requirement: AIcConsumerRequirementDescriptor, candidate: AIcProviderInstance) -> int:
        consumer_versions = requirement.versions or candidate.capability_versions
        if self.contract_catalog is None:
            valid = set(consumer_versions) & set(candidate.capability_versions)
            if not valid:
                raise AIxContractNegotiationError(f"no common version for {requirement.capability_id}")
            return max(valid)
        return self.contract_catalog.negotiate(
            requirement.capability_id,
            tuple(consumer_versions),
            candidate.capability_versions,
        )

    def compatible_candidates(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
    ) -> tuple[AIcBinding, ...]:
        negotiated: list[AIcBinding] = []
        for candidate in candidates:
            if candidate.id == consumer_instance_id:
                continue
            if candidate.capability_id != requirement.capability_id:
                continue
            if candidate.state not in ELIGIBLE_STATES:
                continue
            try:
                version = self._negotiated_version(requirement, candidate)
            except AIxContractNegotiationError:
                continue
            if self.contract_catalog is not None and requirement.requested_authorizations:
                contract = self.contract_catalog.get(requirement.capability_id, version)
                known = {permission.id for permission in contract.authorization_permissions}
                if not set(requirement.requested_authorizations).issubset(known):
                    continue
            binding = AIcBinding(
                consumer_instance_id=consumer_instance_id,
                requirement_id=requirement.id,
                provider_instance_id=candidate.id,
                capability_id=candidate.capability_id,
                capability_version=version,
            )
            # Candidate compatibility/selection is intentionally independent from DAG validation.
            # The complete resolved instance graph is validated atomically after all selections.
            negotiated.append(binding)
        return tuple(negotiated)

    def resolve_single(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
    ) -> AIcBinding:
        compatible = list(self.compatible_candidates(consumer_instance_id, requirement, candidates, existing_bindings))
        # Provider selection is independent from version preference. Deterministic fallback uses stable instance id.
        compatible.sort(key=lambda binding: binding.provider_instance_id)
        if len(compatible) == 1:
            return compatible[0]
        if not compatible:
            if requirement.mandatory:
                raise AIxBindingResolutionError(
                    f"cannot resolve mandatory requirement {requirement.id!r} for instance {consumer_instance_id!r}"
                )
            raise AIxBindingResolutionError(f"no provider selected for optional requirement {requirement.id!r}")
        raise AIxBindingResolutionError(
            f"ambiguous SINGLE requirement {requirement.id!r}: valid providers="
            + ", ".join(binding.provider_instance_id for binding in compatible)
        )

    def resolve_multiple(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
    ) -> tuple[AIcBinding, ...]:
        compatible = self.compatible_candidates(consumer_instance_id, requirement, candidates, existing_bindings)
        if requirement.mandatory and not compatible:
            raise AIxBindingResolutionError(f"cannot resolve mandatory MULTIPLE requirement {requirement.id!r}")
        return tuple(sorted(compatible, key=lambda binding: binding.provider_instance_id))

    def resolve(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
    ) -> tuple[AIcBinding, ...]:
        if requirement.cardinality is AInConsumerCardinality.MULTIPLE:
            return self.resolve_multiple(consumer_instance_id, requirement, candidates, existing_bindings)
        return (self.resolve_single(consumer_instance_id, requirement, candidates, existing_bindings),)

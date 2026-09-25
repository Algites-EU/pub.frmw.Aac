from __future__ import annotations
from collections import defaultdict
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingCycleError, AIxBindingResolutionError, AIxContractNegotiationError

ELIGIBLE_STATES = (
    AInProviderInstanceState.CONFIGURED,
    AInProviderInstanceState.ACTIVATABLE,
    AInProviderInstanceState.ACTIVE,
    AInProviderInstanceState.INACTIVE,
)

class AIcBindingResolver:
    def __init__(self, contract_catalog: AIcActiveContractCatalog | None = None) -> None:
        self.contract_catalog = contract_catalog

    def _negotiated_version(self, requirement: AIcConsumerRequirementDescriptor, candidate: AIcProviderInstance) -> int:
        offered = candidate.capability(requirement.capability_id).versions
        consumer_versions = requirement.versions or offered
        if self.contract_catalog is None:
            valid = set(consumer_versions) & set(offered)
            if not valid:
                raise AIxContractNegotiationError(f"no common version for {requirement.capability_id}")
            return max(valid)
        return self.contract_catalog.negotiate(
            requirement.capability_id,
            tuple(consumer_versions),
            offered,
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
            if not candidate.supports_capability(requirement.capability_id):
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
                capability_id=requirement.capability_id,
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

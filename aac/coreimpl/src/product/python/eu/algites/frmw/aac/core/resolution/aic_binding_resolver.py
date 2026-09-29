from __future__ import annotations
from collections import defaultdict
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingCycleError, AIxBindingResolutionError, AIxContractNegotiationError
from eu.algites.frmw.aac.core.bindings.api import AIiCapabilityProfileMatcher
from eu.algites.frmw.aac.core.loading.symbols import load_class

ELIGIBLE_STATES = (
    AInProviderInstanceState.CONFIGURED,
    AInProviderInstanceState.ACTIVATABLE,
    AInProviderInstanceState.ACTIVE,
    AInProviderInstanceState.INACTIVE,
)

class AIcBindingResolver:
    def __init__(self, contract_catalog: AIcActiveContractCatalog | None = None) -> None:
        self.contract_catalog = contract_catalog

    def _candidate_versions(
        self, requirement: AIcConsumerRequirementDescriptor, candidate: AIcProviderInstance
    ) -> tuple[int, ...]:
        offered = candidate.capability(requirement.capability_id).versions
        consumer_versions = requirement.versions or offered
        versions = set(consumer_versions) & set(offered)
        if self.contract_catalog is not None:
            versions &= set(self.contract_catalog.versions(requirement.capability_id))
        return tuple(sorted(versions, reverse=True))

    def _normalized_provider_profiles(
        self, requirement: AIcConsumerRequirementDescriptor, candidate: AIcProviderInstance, version: int
    ) -> tuple[dict[str, object], ...]:
        provided = candidate.capability(requirement.capability_id)
        if self.contract_catalog is None:
            return tuple(dict(profile) for profile in provided.binding_qualifier_profiles)
        contract = self.contract_catalog.get(requirement.capability_id, version)
        schema_ref = contract.binding_qualifiers_schema
        if schema_ref is None:
            if provided.binding_qualifier_profiles:
                raise AIxBindingResolutionError(
                    f"provider instance {candidate.id!r} declares BindingQualifierProfiles for "
                    f"{requirement.capability_id}/{version}, but the capability contract has no BindingQualifiersSchema"
                )
            return ()
        offered_profiles = provided.binding_qualifier_profiles or ({},)
        normalized: list[dict[str, object]] = []
        for profile in offered_profiles:
            try:
                value = self.contract_catalog.schema_registry.normalize_value_identity(
                    schema_ref.id, schema_ref.version, profile
                )
            except Exception as exc:
                raise AIxBindingResolutionError(
                    f"provider instance {candidate.id!r} binding qualifier profile is invalid for "
                    f"{requirement.capability_id}/{version}: {exc}"
                ) from exc
            normalized.append(dict(value))
        return tuple(normalized)

    def _matched_profiles(
        self,
        requirement: AIcConsumerRequirementDescriptor,
        candidate: AIcProviderInstance,
        version: int,
        *,
        capability_profile_matcher_class_name: str | None,
        consumer_configuration: dict[str, object],
    ) -> tuple[dict[str, object], ...]:
        profiles = self._normalized_provider_profiles(requirement, candidate, version)
        if self.contract_catalog is not None:
            contract = self.contract_catalog.get(requirement.capability_id, version)
            if contract.binding_qualifiers_schema is None:
                return ()
        if capability_profile_matcher_class_name is None:
            raise AIxBindingResolutionError(
                f"consumer requirement {requirement.id!r} needs CapabilityProfileMatcherClassName for "
                f"qualified capability {requirement.capability_id}/{version}"
            )
        matcher_class = load_class(capability_profile_matcher_class_name, AIiCapabilityProfileMatcher)
        matcher = matcher_class()
        indexes = tuple(matcher.match_profile_indexes(
            requirement, version, candidate.id, profiles, consumer_configuration
        ))
        if len(indexes) != len(set(indexes)):
            raise AIxBindingResolutionError("capability profile matcher returned duplicate profile indexes")
        if any(index < 0 or index >= len(profiles) for index in indexes):
            raise AIxBindingResolutionError("capability profile matcher returned an out-of-range profile index")
        return tuple(profiles[index] for index in indexes)

    def _compatible_version_and_profiles(
        self, requirement: AIcConsumerRequirementDescriptor, candidate: AIcProviderInstance,
        *, capability_profile_matcher_class_name: str | None, consumer_configuration: dict[str, object]
    ) -> tuple[int, tuple[dict[str, object], ...]]:
        for version in self._candidate_versions(requirement, candidate):
            if self.contract_catalog is not None and requirement.requested_authorizations:
                contract = self.contract_catalog.get(requirement.capability_id, version)
                known = {permission.id for permission in contract.authorization_permissions}
                if not set(requirement.requested_authorizations).issubset(known):
                    continue
            if self.contract_catalog is not None:
                contract = self.contract_catalog.get(requirement.capability_id, version)
                if contract.binding_qualifiers_schema is None:
                    self._normalized_provider_profiles(requirement, candidate, version)
                    return version, ()
            profiles = self._matched_profiles(
                requirement, candidate, version,
                capability_profile_matcher_class_name=capability_profile_matcher_class_name,
                consumer_configuration=consumer_configuration,
            )
            if profiles:
                return version, profiles
        raise AIxContractNegotiationError(
            f"no common compatible contract/capability profile for {requirement.capability_id}"
        )

    def compatible_candidates(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
        *, capability_profile_matcher_class_name: str | None = None,
        consumer_configuration: dict[str, object] | None = None,
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
                version, profiles = self._compatible_version_and_profiles(
                    requirement, candidate,
                    capability_profile_matcher_class_name=capability_profile_matcher_class_name,
                    consumer_configuration=dict(consumer_configuration or {}),
                )
            except AIxContractNegotiationError:
                continue
            binding = AIcBinding(
                consumer_instance_id=consumer_instance_id,
                requirement_id=requirement.id,
                provider_instance_id=candidate.id,
                capability_id=requirement.capability_id,
                capability_version=version,
                binding_qualifier_profiles=profiles,
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
        *, capability_profile_matcher_class_name: str | None = None,
        consumer_configuration: dict[str, object] | None = None,
    ) -> AIcBinding:
        compatible = list(self.compatible_candidates(
            consumer_instance_id, requirement, candidates, existing_bindings,
            capability_profile_matcher_class_name=capability_profile_matcher_class_name,
            consumer_configuration=consumer_configuration,
        ))
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
        *, capability_profile_matcher_class_name: str | None = None,
        consumer_configuration: dict[str, object] | None = None,
    ) -> tuple[AIcBinding, ...]:
        compatible = self.compatible_candidates(
            consumer_instance_id, requirement, candidates, existing_bindings,
            capability_profile_matcher_class_name=capability_profile_matcher_class_name,
            consumer_configuration=consumer_configuration,
        )
        if requirement.mandatory and not compatible:
            raise AIxBindingResolutionError(f"cannot resolve mandatory MULTIPLE requirement {requirement.id!r}")
        return tuple(sorted(compatible, key=lambda binding: binding.provider_instance_id))

    def resolve(
        self,
        consumer_instance_id: str,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...] | list[AIcProviderInstance],
        existing_bindings: tuple[AIcBinding, ...] | list[AIcBinding] = (),
        *, capability_profile_matcher_class_name: str | None = None,
        consumer_configuration: dict[str, object] | None = None,
    ) -> tuple[AIcBinding, ...]:
        if requirement.cardinality is AInConsumerCardinality.MULTIPLE:
            return self.resolve_multiple(
                consumer_instance_id, requirement, candidates, existing_bindings,
                capability_profile_matcher_class_name=capability_profile_matcher_class_name,
                consumer_configuration=consumer_configuration,
            )
        return (self.resolve_single(
            consumer_instance_id, requirement, candidates, existing_bindings,
            capability_profile_matcher_class_name=capability_profile_matcher_class_name,
            consumer_configuration=consumer_configuration,
        ),)

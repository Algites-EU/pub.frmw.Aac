from __future__ import annotations

from dataclasses import dataclass

from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor, AIcConsumerRequirementDescriptor
from algites.lib.aac.coreintf.instances import AIcBinding, AIcBindingPreference, AIcProviderInstance

from .bindings import AIcBindingPreferenceStore, AIcBindingStore
from .errors import AIxBindingResolutionError
from .instances import AIcProviderInstanceRegistry
from .resolution import AIcBindingResolver, validate_instance_dag


@dataclass(frozen=True, slots=True)
class AIcResolvedApplicationGraph:
    bindings: tuple[AIcBinding, ...]
    provider_first_order: tuple[str, ...]


class AIcApplicationGraphOrchestrator:
    def __init__(
        self,
        registry: AIcProviderInstanceRegistry,
        resolver: AIcBindingResolver,
        bindings: AIcBindingStore,
        preferences: AIcBindingPreferenceStore,
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.bindings = bindings
        self.preferences = preferences

    def resolve(self, descriptors: dict[str, AIcComponentDescriptor]) -> AIcResolvedApplicationGraph:
        candidates = self.registry.all()
        resolved: list[AIcBinding] = []
        for consumer in sorted(candidates, key=lambda value: value.id):
            descriptor = descriptors[consumer.component_id]
            provider = descriptor.provider(consumer.provider_definition_id)
            for requirement in provider.requirements:
                selected = self._candidates_for_preference(consumer, requirement, candidates)
                try:
                    bindings = self.resolver.resolve(consumer.id, requirement, selected, tuple(resolved))
                except AIxBindingResolutionError:
                    if requirement.mandatory:
                        raise
                    bindings = ()
                resolved.extend(bindings)

        consumer_first = validate_instance_dag(tuple(resolved))
        provider_first = tuple(reversed(consumer_first))
        self.bindings.replace_all(tuple(resolved))
        return AIcResolvedApplicationGraph(tuple(resolved), provider_first)

    def _candidates_for_preference(
        self,
        consumer: AIcProviderInstance,
        requirement: AIcConsumerRequirementDescriptor,
        candidates: tuple[AIcProviderInstance, ...],
    ) -> tuple[AIcProviderInstance, ...]:
        preference = self.preferences.get(consumer.id, requirement.id)
        if preference is None:
            return candidates
        selected_ids = set(preference.provider_instance_ids)
        if not selected_ids and requirement.mandatory:
            raise AIxBindingResolutionError(
                f"binding preference for mandatory requirement {requirement.id!r} selects no provider"
            )
        selected = tuple(candidate for candidate in candidates if candidate.id in selected_ids)
        missing = selected_ids - {candidate.id for candidate in selected}
        if missing:
            raise AIxBindingResolutionError(
                f"binding preference for {consumer.id}:{requirement.id} references unknown provider instances {sorted(missing)}"
            )
        return selected

    def set_preference(self, preference: AIcBindingPreference) -> None:
        self.preferences.put(preference)

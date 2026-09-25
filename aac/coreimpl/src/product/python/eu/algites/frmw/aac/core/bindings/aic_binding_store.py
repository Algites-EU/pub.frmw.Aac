from __future__ import annotations
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcBindingPreference
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.persistence.state_store_support import state_delete_mutation, state_put_mutation
from eu.algites.frmw.aac.core.resolution.bindings import validate_instance_dag

_BINDING_NAMESPACE = "aac.bindings"

def _binding_to_dict(binding: AIcBinding) -> dict[str, object]:
    return {
        "consumer_instance_id": binding.consumer_instance_id,
        "requirement_id": binding.requirement_id,
        "provider_instance_id": binding.provider_instance_id,
        "capability_id": binding.capability_id,
        "capability_version": binding.capability_version,
    }

def _binding_from_dict(raw) -> AIcBinding:
    return AIcBinding(
        str(raw["consumer_instance_id"]), str(raw["requirement_id"]), str(raw["provider_instance_id"]),
        str(raw["capability_id"]), int(raw["capability_version"]),
    )

class AIcBindingStore:
    def __init__(self, store: AIiStateStore | None = None) -> None:
        self.store = store or AIcInMemoryStateStore()

    @staticmethod
    def key(binding: AIcBinding) -> str:
        return f"{binding.consumer_instance_id}:{binding.requirement_id}:{binding.provider_instance_id}"

    def all(self) -> tuple[AIcBinding, ...]:
        values = tuple(_binding_from_dict(raw) for raw in self.store.list(_BINDING_NAMESPACE).values())
        validate_instance_dag(values)
        return values

    def put(self, binding: AIcBinding) -> None:
        existing = [item for item in self.all() if self.key(item) != self.key(binding)]
        validate_instance_dag(tuple(existing) + (binding,))
        self.store.put(_BINDING_NAMESPACE, self.key(binding), _binding_to_dict(binding))

    def replace_requirement(self, consumer_instance_id: str, requirement_id: str, bindings: tuple[AIcBinding, ...]) -> None:
        retained = [
            item for item in self.all()
            if not (item.consumer_instance_id == consumer_instance_id and item.requirement_id == requirement_id)
        ]
        self.replace_all(tuple(retained) + bindings)

    def replace_all(self, bindings: tuple[AIcBinding, ...]) -> None:
        validate_instance_dag(bindings)
        current = self.store.list_records(_BINDING_NAMESPACE)
        target = {self.key(binding): binding for binding in bindings}
        mutations = [
            state_delete_mutation(self.store, _BINDING_NAMESPACE, key)
            for key in current if key not in target
        ]
        mutations.extend(
            state_put_mutation(self.store, _BINDING_NAMESPACE, key, _binding_to_dict(binding))
            for key, binding in target.items()
        )
        self.store.apply(tuple(mutations))

    def for_consumer(self, consumer_instance_id: str) -> tuple[AIcBinding, ...]:
        return tuple(item for item in self.all() if item.consumer_instance_id == consumer_instance_id)

    def references_instance(self, provider_instance_id: str) -> tuple[AIcBinding, ...]:
        return tuple(
            item for item in self.all()
            if item.provider_instance_id == provider_instance_id or item.consumer_instance_id == provider_instance_id
        )

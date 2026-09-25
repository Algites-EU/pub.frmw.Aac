from __future__ import annotations

from algites.frmw.aac.coreintf.instances import AIcBinding, AIcBindingPreference
from algites.frmw.aac.coreintf.persistence import AIcStateMutation, AIiStateStore

from .persistence import AIcInMemoryStateStore, state_delete_mutation, state_put_mutation
from .resolution import validate_instance_dag

_BINDING_NAMESPACE = "aac.bindings"
_PREFERENCE_NAMESPACE = "aac.binding-preferences"


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


class AIcBindingPreferenceStore:
    def __init__(self, store: AIiStateStore | None = None) -> None:
        self.store = store or AIcInMemoryStateStore()

    @staticmethod
    def key(consumer_instance_id: str, requirement_id: str) -> str:
        return f"{consumer_instance_id}:{requirement_id}"

    def put(self, preference: AIcBindingPreference) -> None:
        self.store.put(_PREFERENCE_NAMESPACE, self.key(preference.consumer_instance_id, preference.requirement_id), {
            "consumer_instance_id": preference.consumer_instance_id,
            "requirement_id": preference.requirement_id,
            "provider_instance_ids": list(preference.provider_instance_ids),
        })

    def get(self, consumer_instance_id: str, requirement_id: str) -> AIcBindingPreference | None:
        raw = self.store.get(_PREFERENCE_NAMESPACE, self.key(consumer_instance_id, requirement_id))
        if raw is None:
            return None
        return AIcBindingPreference(
            str(raw["consumer_instance_id"]),
            str(raw["requirement_id"]),
            tuple(str(value) for value in raw.get("provider_instance_ids", ())),
        )

    def delete(self, consumer_instance_id: str, requirement_id: str) -> None:
        self.store.delete(_PREFERENCE_NAMESPACE, self.key(consumer_instance_id, requirement_id))

    def all(self) -> tuple[AIcBindingPreference, ...]:
        values = []
        for raw in self.store.list(_PREFERENCE_NAMESPACE).values():
            values.append(AIcBindingPreference(
                str(raw["consumer_instance_id"]),
                str(raw["requirement_id"]),
                tuple(str(value) for value in raw.get("provider_instance_ids", ())),
            ))
        return tuple(values)


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

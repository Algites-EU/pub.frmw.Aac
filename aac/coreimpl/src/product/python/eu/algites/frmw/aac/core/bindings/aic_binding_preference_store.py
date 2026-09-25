from __future__ import annotations
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcBindingPreference
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.persistence.state_store_support import state_delete_mutation, state_put_mutation
from eu.algites.frmw.aac.core.resolution.bindings import validate_instance_dag

_PREFERENCE_NAMESPACE = "aac.binding-preferences"

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

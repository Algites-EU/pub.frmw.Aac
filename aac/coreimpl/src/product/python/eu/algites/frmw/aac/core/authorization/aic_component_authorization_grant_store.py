from __future__ import annotations
from eu.algites.frmw.aac.core.authorization.api import AIcComponentAuthorizationGrant
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore

_NAMESPACE = "aac.component-authorization-grants"

class AIcComponentAuthorizationGrantStore:
    def __init__(self, store: AIiStateStore | None = None) -> None:
        self.store = store or AIcInMemoryStateStore()

    @staticmethod
    def key(consumer_instance_id: str, requirement_id: str) -> str:
        return f"{consumer_instance_id}:{requirement_id}"

    def put(self, grant: AIcComponentAuthorizationGrant) -> None:
        self.store.put(_NAMESPACE, self.key(grant.consumer_instance_id, grant.requirement_id), {
            "consumer_instance_id": grant.consumer_instance_id,
            "requirement_id": grant.requirement_id,
            "permission_ids": list(grant.permission_ids),
            "approved_by": grant.approved_by,
            "metadata": dict(grant.metadata),
        })

    def get(self, consumer_instance_id: str, requirement_id: str) -> AIcComponentAuthorizationGrant | None:
        raw = self.store.get(_NAMESPACE, self.key(consumer_instance_id, requirement_id))
        if raw is None:
            return None
        return AIcComponentAuthorizationGrant(
            consumer_instance_id=str(raw["consumer_instance_id"]),
            requirement_id=str(raw["requirement_id"]),
            permission_ids=tuple(str(v) for v in raw.get("permission_ids", ())),
            approved_by=str(raw["approved_by"]) if raw.get("approved_by") is not None else None,
            metadata=dict(raw.get("metadata", {})),
        )

    def delete(self, consumer_instance_id: str, requirement_id: str) -> None:
        self.store.delete(_NAMESPACE, self.key(consumer_instance_id, requirement_id))

    def all(self) -> tuple[AIcComponentAuthorizationGrant, ...]:
        values = []
        for raw in self.store.list(_NAMESPACE).values():
            values.append(AIcComponentAuthorizationGrant(
                consumer_instance_id=str(raw["consumer_instance_id"]),
                requirement_id=str(raw["requirement_id"]),
                permission_ids=tuple(str(v) for v in raw.get("permission_ids", ())),
                approved_by=str(raw["approved_by"]) if raw.get("approved_by") is not None else None,
                metadata=dict(raw.get("metadata", {})),
            ))
        return tuple(values)

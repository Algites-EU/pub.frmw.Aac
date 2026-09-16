from __future__ import annotations

from algites.lib.aac.coreintf.extensions import (
    AIcCoreEntityRef,
    AIcEntityExtensionDataEnvelope,
    AIcEntityExtensionDataRecord,
    AIiEntityExtensionDataStore,
)
from algites.lib.aac.coreintf.persistence import AInPersistenceCapability, AInRecordRevisionKind

from .errors import AIxPersistenceRevisionConflict


class AIcInMemoryEntityExtensionDataStore(AIiEntityExtensionDataStore):
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], AIcEntityExtensionDataRecord] = {}

    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.MONOTONIC_INTEGER

    def persistence_capabilities(self) -> tuple[AInPersistenceCapability, ...]:
        return (
            AInPersistenceCapability.READ,
            AInPersistenceCapability.SINGLE_RECORD_CAS,
            AInPersistenceCapability.MULTI_RECORD_TRANSACTION,
        )

    @staticmethod
    def _key(entity: AIcCoreEntityRef, component_id: str) -> tuple[str, str, str]:
        return entity.entity_type_id, entity.entity_id, component_id

    def get_record(self, entity: AIcCoreEntityRef, component_id: str) -> AIcEntityExtensionDataRecord | None:
        return self._items.get(self._key(entity, component_id))

    def put(
        self,
        envelope: AIcEntityExtensionDataEnvelope,
        *,
        expected_record_revision: int | str | None = None,
        expect_absent: bool = False,
    ) -> AIcEntityExtensionDataRecord:
        key = self._key(envelope.core_entity, envelope.owner_component_id)
        current = self._items.get(key)
        actual = None if current is None else current.record_revision
        if expect_absent:
            if current is not None:
                raise AIxPersistenceRevisionConflict(":".join(key), None, actual)
        elif current is not None:
            if expected_record_revision is None or expected_record_revision != actual:
                raise AIxPersistenceRevisionConflict(":".join(key), expected_record_revision, actual)
        elif expected_record_revision is not None:
            raise AIxPersistenceRevisionConflict(":".join(key), expected_record_revision, None)
        revision = 1 if current is None else int(current.record_revision) + 1
        record = AIcEntityExtensionDataRecord(revision, envelope)
        self._items[key] = record
        return record

    def remove(
        self,
        entity: AIcCoreEntityRef,
        component_id: str,
        *,
        expected_record_revision: int | str | None = None,
    ) -> None:
        key = self._key(entity, component_id)
        current = self._items.get(key)
        if current is None:
            return
        if expected_record_revision is None or current.record_revision != expected_record_revision:
            raise AIxPersistenceRevisionConflict(":".join(key), expected_record_revision, current.record_revision)
        self._items.pop(key, None)

    def enumerate_records(self, entity: AIcCoreEntityRef) -> tuple[AIcEntityExtensionDataRecord, ...]:
        return tuple(
            value for (entity_type, entity_id, _), value in self._items.items()
            if entity_type == entity.entity_type_id and entity_id == entity.entity_id
        )

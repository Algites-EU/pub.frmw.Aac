from __future__ import annotations

from abc import ABC, abstractmethod

from ..persistence import AInPersistenceCapability, AInRecordRevisionKind
from .models import AIcCoreEntityRef, AIcEntityExtensionDataEnvelope, AIcEntityExtensionDataRecord


class AIiEntityExtensionDataStore(ABC):
    """Persistence-domain contract for component-extension data.

    Component-owned extension payloads remain independent from persistence metadata. The store wraps
    each payload envelope in a revisioned record and exposes compare-and-swap mutation semantics.
    """

    @property
    @abstractmethod
    def revision_kind(self) -> AInRecordRevisionKind: ...

    def persistence_capabilities(self) -> tuple[AInPersistenceCapability, ...]:
        return (AInPersistenceCapability.READ, AInPersistenceCapability.SINGLE_RECORD_CAS)

    @abstractmethod
    def get_record(self, entity: AIcCoreEntityRef, component_id: str) -> AIcEntityExtensionDataRecord | None: ...

    def get(self, entity: AIcCoreEntityRef, component_id: str) -> AIcEntityExtensionDataEnvelope | None:
        record = self.get_record(entity, component_id)
        return None if record is None else record.envelope

    @abstractmethod
    def put(
        self,
        envelope: AIcEntityExtensionDataEnvelope,
        *,
        expected_record_revision: int | str | None = None,
        expect_absent: bool = False,
    ) -> AIcEntityExtensionDataRecord: ...

    @abstractmethod
    def remove(
        self,
        entity: AIcCoreEntityRef,
        component_id: str,
        *,
        expected_record_revision: int | str | None = None,
    ) -> None: ...

    @abstractmethod
    def enumerate_records(self, entity: AIcCoreEntityRef) -> tuple[AIcEntityExtensionDataRecord, ...]: ...

    def enumerate(self, entity: AIcCoreEntityRef) -> tuple[AIcEntityExtensionDataEnvelope, ...]:
        return tuple(item.envelope for item in self.enumerate_records(entity))

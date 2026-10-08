from __future__ import annotations
from contextvars import ContextVar
from uuid import uuid4
from dataclasses import asdict, dataclass
from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationBinding,
    AIigObservationInput_1,
    AIigObservationOutput_1,
    AIngObservationInputPhase_1,
    AIiObservationProvider,
    AIcObservationSelector,
)
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.invocation.api import AIiCapabilityEndpoint, AIcInvocationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore

@dataclass(frozen=True, slots=True)
class AIcObservationDelivery:
    observer_instance_id: str
    output: AIigObservationOutput_1 | None
    error: str | None = None

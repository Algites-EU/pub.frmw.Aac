from __future__ import annotations
from contextvars import ContextVar
from uuid import uuid4
from dataclasses import asdict, dataclass
from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationBinding,
    AIcObservationInput,
    AIcObservationOutput,
    AInObservationPhase,
    AIiObservationProvider,
    AIcObservationSelector,
)
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.invocation.api import AIiCapabilityEndpoint, AIcInvocationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore

from .aic_endpoint_observation_provider import AIcEndpointObservationProvider
from .aic_observation_delivery import AIcObservationDelivery
from .aic_observation_topology_store import AIcObservationTopologyStore
from .aic_observation_dispatcher import AIcObservationDispatcher

OBSERVATION_CAPABILITY_ID = "_AAC.capability.observation"

_OBSERVATION_NAMESPACE = "aac.observation-bindings"

from ._context import ACTIVE_OBSERVERS as _ACTIVE_OBSERVERS

def _binding_to_dict(binding: AIcObservationBinding) -> dict[str, object]:
    return {
        "observer_instance_id": binding.observer_instance_id,
        "selectors": [
            {
                "capability": selector.capability,
                "versions": list(selector.versions),
                "operations": list(selector.operations),
                "phases": [phase.value for phase in selector.phases],
            }
            for selector in binding.selectors
        ],
    }

def _binding_from_dict(raw) -> AIcObservationBinding:
    return AIcObservationBinding(
        observer_instance_id=str(raw["observer_instance_id"]),
        selectors=tuple(
            AIcObservationSelector(
                capability=str(item.get("capability", "*")),
                versions=tuple(int(value) for value in item.get("versions", ())),
                operations=tuple(str(value) for value in item.get("operations", ())),
                phases=tuple(AInObservationPhase(str(value)) for value in item.get("phases", ("PRE", "POST"))),
            )
            for item in raw.get("selectors", ())
        ),
    )

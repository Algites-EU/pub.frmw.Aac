from __future__ import annotations
from eu.algites.frmw.aac.core.observation.aicgd_observation_output_1 import AIcgdObservationOutput_1
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

OBSERVATION_CAPABILITY_ID = "_AAC.capability.observation"

class AIcEndpointObservationProvider(AIiObservationProvider):
    """Observation-provider adapter for non-object endpoints such as process runtimes."""

    def __init__(self, instance_id: str, endpoint: AIiCapabilityEndpoint, invocation_dispatcher) -> None:
        self.instance_id = instance_id
        self.endpoint = endpoint
        self.invocation_dispatcher = invocation_dispatcher

    def observe_1(self, observation_input: AIigObservationInput_1) -> AIigObservationOutput_1:
        invocation = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=observation_input.invocation_id,
            capability_id=OBSERVATION_CAPABILITY_ID,
            capability_version=1,
            operation_id="observe",
            provider_instance_id=self.instance_id,
            arguments=observation_input.to_mapping(),
        )
        output = self.invocation_dispatcher.invoke(self.endpoint, invocation)
        if not output.success:
            raise RuntimeError(str(output.error))
        raw = output.result
        if isinstance(raw, AIigObservationOutput_1):
            return raw
        if isinstance(raw, dict):
            return AIcgdObservationOutput_1.from_mapping(raw)
        raise TypeError("observation endpoint returned an invalid output")

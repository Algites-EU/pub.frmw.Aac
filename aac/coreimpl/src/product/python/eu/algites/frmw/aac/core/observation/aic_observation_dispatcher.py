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

from .aic_observation_delivery import AIcObservationDelivery
from .aic_observation_topology_store import AIcObservationTopologyStore

OBSERVATION_CAPABILITY_ID = "_AAC.capability.observation"

from ._context import ACTIVE_OBSERVERS as _ACTIVE_OBSERVERS

class AIcObservationDispatcher:
    def __init__(self, topology: AIcObservationTopologyStore | None = None) -> None:
        self._providers: dict[str, AIiObservationProvider] = {}
        self.topology = topology or AIcObservationTopologyStore()

    def register_provider(self, instance_id: str, provider: AIiObservationProvider) -> None:
        self._providers[instance_id] = provider

    def unregister_provider(self, instance_id: str) -> None:
        self._providers.pop(instance_id, None)

    # Compatibility helper from build 1: topology and provider registration are now separated.
    def register(self, instance_id: str, provider: AIiObservationProvider, selectors: tuple[AIcObservationSelector, ...]) -> None:
        self.register_provider(instance_id, provider)
        self.topology.put(AIcObservationBinding(instance_id, selectors))

    def unregister(self, instance_id: str) -> None:
        self.unregister_provider(instance_id)
        self.topology.delete(instance_id)

    def dispatch(self, observation_input: AIcObservationInput) -> tuple[AIcObservationDelivery, ...]:
        if observation_input.capability_id == OBSERVATION_CAPABILITY_ID:
            return ()
        active = _ACTIVE_OBSERVERS.get()
        deliveries: list[AIcObservationDelivery] = []
        for binding in self.topology.all():
            if binding.observer_instance_id in active:
                continue
            if not any(selector.matches(observation_input) for selector in binding.selectors):
                continue
            provider = self._providers.get(binding.observer_instance_id)
            if provider is None:
                deliveries.append(AIcObservationDelivery(binding.observer_instance_id, None, "observer runtime is not active"))
                continue
            token = _ACTIVE_OBSERVERS.set(active | {binding.observer_instance_id})
            try:
                output = provider.observe_1(observation_input)
                if not isinstance(output, AIcObservationOutput):
                    raise TypeError("observer returned a non-AIcObservationOutput value")
                deliveries.append(AIcObservationDelivery(binding.observer_instance_id, output))
            except Exception as exc:
                deliveries.append(AIcObservationDelivery(binding.observer_instance_id, None, f"{type(exc).__name__}: {exc}"))
            finally:
                _ACTIVE_OBSERVERS.reset(token)
        return tuple(deliveries)

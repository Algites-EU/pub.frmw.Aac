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

OBSERVATION_CAPABILITY_ID = "_AAC.capability.observation"

_OBSERVATION_NAMESPACE = "aac.observation-bindings"

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

class AIcObservationTopologyStore:
    def __init__(self, store: AIiStateStore | None = None, contracts: AIcActiveContractCatalog | None = None) -> None:
        self.store = store or AIcInMemoryStateStore()
        self.contracts = contracts

    def put(self, binding: AIcObservationBinding) -> None:
        self._validate(binding)
        self.store.put(_OBSERVATION_NAMESPACE, binding.observer_instance_id, _binding_to_dict(binding))

    def get(self, observer_instance_id: str) -> AIcObservationBinding | None:
        raw = self.store.get(_OBSERVATION_NAMESPACE, observer_instance_id)
        return _binding_from_dict(raw) if raw is not None else None

    def all(self) -> tuple[AIcObservationBinding, ...]:
        return tuple(_binding_from_dict(value) for value in self.store.list(_OBSERVATION_NAMESPACE).values())

    def delete(self, observer_instance_id: str) -> None:
        self.store.delete(_OBSERVATION_NAMESPACE, observer_instance_id)

    def _validate(self, binding: AIcObservationBinding) -> None:
        if not binding.selectors:
            raise ValueError("observation binding must contain at least one selector")
        if self.contracts is None:
            return
        for selector in binding.selectors:
            if selector.capability == OBSERVATION_CAPABILITY_ID:
                raise ValueError("_AAC.capability.observation cannot observe itself")
            if any(ch in selector.capability for ch in "*?["):
                continue
            versions = selector.versions or self.contracts.versions(selector.capability)
            if not versions:
                raise ValueError(f"observation selector references unknown capability {selector.capability!r}")
            for version in versions:
                contract = self.contracts.get(selector.capability, version)
                known_operations = {operation.id for operation in contract.operations}
                unknown = set(selector.operations) - known_operations
                if unknown:
                    raise ValueError(
                        f"observation selector references unknown operations for {selector.capability}/{version}: {sorted(unknown)}"
                    )

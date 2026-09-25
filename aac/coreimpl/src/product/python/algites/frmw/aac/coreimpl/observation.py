from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4
from dataclasses import asdict, dataclass

from algites.frmw.aac.coreintf.observation import (
    AIcObservationBinding,
    AIcObservationInput,
    AIcObservationOutput,
    AInObservationPhase,
    AIiObservationProvider,
    AIcObservationSelector,
)
from algites.frmw.aac.coreintf.persistence import AIiStateStore
from algites.frmw.aac.coreintf.invocation import AIiCapabilityEndpoint, AIcInvocationInput

from .capability import AIcActiveContractCatalog
from .persistence import AIcInMemoryStateStore

OBSERVATION_CAPABILITY_ID = "_AAC.capability.observation"
_OBSERVATION_NAMESPACE = "aac.observation-bindings"
_ACTIVE_OBSERVERS: ContextVar[frozenset[str]] = ContextVar("aac_active_observers", default=frozenset())


class AIcEndpointObservationProvider(AIiObservationProvider):
    """Observation-provider adapter for non-object endpoints such as PROCESS runtimes."""

    def __init__(self, instance_id: str, endpoint: AIiCapabilityEndpoint, invocation_dispatcher) -> None:
        self.instance_id = instance_id
        self.endpoint = endpoint
        self.invocation_dispatcher = invocation_dispatcher

    def observe_1(self, observation_input: AIcObservationInput) -> AIcObservationOutput:
        invocation = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=observation_input.invocation_id,
            capability_id=OBSERVATION_CAPABILITY_ID,
            capability_version=1,
            operation_id="observe",
            provider_instance_id=self.instance_id,
            arguments=asdict(observation_input),
        )
        output = self.invocation_dispatcher.invoke(self.endpoint, invocation)
        if not output.success:
            raise RuntimeError(str(output.error))
        raw = output.result
        if isinstance(raw, AIcObservationOutput):
            return raw
        if isinstance(raw, dict):
            return AIcObservationOutput(
                accepted=bool(raw.get("accepted", True)),
                diagnostic=str(raw["diagnostic"]) if raw.get("diagnostic") is not None else None,
            )
        raise TypeError("observation endpoint returned an invalid output")


@dataclass(frozen=True, slots=True)
class AIcObservationDelivery:
    observer_instance_id: str
    output: AIcObservationOutput | None
    error: str | None = None


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

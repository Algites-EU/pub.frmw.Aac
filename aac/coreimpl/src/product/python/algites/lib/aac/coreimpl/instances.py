from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor, AIcProviderDefinitionDescriptor
from algites.lib.aac.coreintf.instances import AIcProviderInstance, AInProviderInstanceState
from algites.lib.aac.coreintf.persistence import AIcStateMutation, AIiStateStore

from .persistence import AIcInMemoryStateStore, state_delete_mutation, state_put_mutation

_PROVIDER_NAMESPACE = "aac.provider-instances"


class AIcProviderInstanceRegistry:
    def __init__(self, store: AIiStateStore | None = None) -> None:
        self.store = store or AIcInMemoryStateStore()
        self._instances: dict[str, AIcProviderInstance] = {}
        self._load()

    def reload(self) -> None:
        self._load()

    def _load(self) -> None:
        self._instances = {
            instance_id: _instance_from_dict(raw)
            for instance_id, raw in self.store.list(_PROVIDER_NAMESPACE).items()
        }

    def all(self) -> tuple[AIcProviderInstance, ...]:
        return tuple(self._instances.values())

    def get(self, instance_id: str) -> AIcProviderInstance:
        return self._instances[instance_id]

    def find(
        self,
        *,
        component_id: str | None = None,
        provider_definition_id: str | None = None,
        name: str | None = None,
        capability_id: str | None = None,
        states: tuple[AInProviderInstanceState, ...] | None = None,
    ) -> tuple[AIcProviderInstance, ...]:
        result = []
        for instance in self._instances.values():
            if component_id is not None and instance.component_id != component_id:
                continue
            if provider_definition_id is not None and instance.provider_definition_id != provider_definition_id:
                continue
            if name is not None and instance.name != name:
                continue
            if capability_id is not None and instance.capability_id != capability_id:
                continue
            if states is not None and instance.state not in states:
                continue
            result.append(instance)
        return tuple(result)

    def build(
        self,
        component_id: str,
        provider: AIcProviderDefinitionDescriptor,
        *,
        name: str = "default",
        configuration: dict[str, object] | None = None,
        state: AInProviderInstanceState = AInProviderInstanceState.CONFIGURED,
    ) -> AIcProviderInstance:
        return AIcProviderInstance(
            id=str(uuid4()),
            component_id=component_id,
            provider_definition_id=provider.id,
            name=name,
            capability_id=provider.capability_id,
            capability_versions=provider.capability_versions,
            implementation_class=provider.implementation_class,
            configuration=dict(configuration or {}),
            configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
            state=state,
        )

    def commit(self, instances: tuple[AIcProviderInstance, ...], extra_mutations: tuple[AIcStateMutation, ...] = ()) -> None:
        mutations = tuple(
            state_put_mutation(self.store, _PROVIDER_NAMESPACE, instance.id, _instance_to_dict(instance))
            for instance in instances
        ) + tuple(extra_mutations)
        self.store.apply(mutations)
        for instance in instances:
            self._instances[instance.id] = instance

    def create(
        self,
        component_id: str,
        provider: AIcProviderDefinitionDescriptor,
        *,
        name: str = "default",
        configuration: dict[str, object] | None = None,
        state: AInProviderInstanceState = AInProviderInstanceState.CONFIGURED,
    ) -> AIcProviderInstance:
        instance = self.build(
            component_id, provider, name=name, configuration=configuration, state=state
        )
        self.commit((instance,))
        return instance

    def update(self, instance_id: str, **changes: object) -> AIcProviderInstance:
        instance = replace(self.get(instance_id), **changes)
        self.store.put(_PROVIDER_NAMESPACE, instance.id, _instance_to_dict(instance))
        self._instances[instance_id] = instance
        return instance

    def reconcile_descriptor(self, descriptor: AIcComponentDescriptor) -> tuple[AIcProviderInstance, ...]:
        providers = {provider.id: provider for provider in descriptor.providers}
        updated = []
        for instance in self.find(component_id=descriptor.id):
            provider = providers.get(instance.provider_definition_id)
            if provider is None:
                raise ValueError(f"upgrade removed provider definition {instance.provider_definition_id!r} while instances still exist")
            updated.append(replace(
                instance,
                capability_id=provider.capability_id,
                capability_versions=provider.capability_versions,
                implementation_class=provider.implementation_class,
                configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
                state=AInProviderInstanceState.INACTIVE,
            ))
        if updated:
            self.commit(tuple(updated))
        return tuple(updated)

    def reconcile_initial_instances(self, descriptor: AIcComponentDescriptor) -> tuple[AIcProviderInstance, ...]:
        staged: list[AIcProviderInstance] = []
        for provider in descriptor.providers:
            for declared in provider.initial_instances:
                existing = self.find(component_id=descriptor.id, provider_definition_id=provider.id, name=declared.name)
                if existing:
                    continue
                staged.append(self.build(descriptor.id, provider, name=declared.name, configuration=dict(declared.configuration)))
        if staged:
            self.commit(tuple(staged))
        return tuple(staged)

    def remove_ids(self, instance_ids: tuple[str, ...], extra_mutations: tuple[AIcStateMutation, ...] = ()) -> tuple[AIcProviderInstance, ...]:
        removed = tuple(self._instances[instance_id] for instance_id in instance_ids if instance_id in self._instances)
        mutations = tuple(state_delete_mutation(self.store, _PROVIDER_NAMESPACE, instance.id) for instance in removed) + tuple(extra_mutations)
        self.store.apply(mutations)
        for instance in removed:
            self._instances.pop(instance.id, None)
        return removed

    def remove_component(self, component_id: str) -> tuple[AIcProviderInstance, ...]:
        return self.remove_ids(tuple(instance.id for instance in self._instances.values() if instance.component_id == component_id))


def instance_to_dict(instance: AIcProviderInstance) -> dict[str, object]:
    return _instance_to_dict(instance)


def _instance_to_dict(instance: AIcProviderInstance) -> dict[str, object]:
    return {
        "id": instance.id,
        "component_id": instance.component_id,
        "provider_definition_id": instance.provider_definition_id,
        "name": instance.name,
        "capability_id": instance.capability_id,
        "capability_versions": list(instance.capability_versions),
        "implementation_class": instance.implementation_class,
        "configuration": dict(instance.configuration),
        "configuration_schema": instance.configuration_schema,
        "state": instance.state.value,
    }


def _instance_from_dict(raw: dict[str, object] | object) -> AIcProviderInstance:
    if not isinstance(raw, dict):
        raise ValueError("persisted provider instance must be an object")
    return AIcProviderInstance(
        id=str(raw["id"]),
        component_id=str(raw["component_id"]),
        provider_definition_id=str(raw["provider_definition_id"]),
        name=str(raw["name"]),
        capability_id=str(raw["capability_id"]),
        capability_versions=tuple(int(v) for v in raw["capability_versions"]),
        implementation_class=str(raw["implementation_class"]),
        configuration=dict(raw.get("configuration", {})),
        configuration_schema=str(raw["configuration_schema"]) if raw.get("configuration_schema") is not None else None,
        state=AInProviderInstanceState(str(raw.get("state", AInProviderInstanceState.CONFIGURED.value))),
    )

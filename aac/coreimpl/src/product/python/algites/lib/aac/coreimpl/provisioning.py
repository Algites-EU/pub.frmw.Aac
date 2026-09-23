from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor
from algites.lib.aac.coreintf.instances import AInProviderInstanceState
from algites.lib.aac.coreintf.lifecycle import AIiProvisioningHook, AIiUnprovisioningHook
from algites.lib.aac.coreintf.persistence import AIcStateMutation, AIiStateStore
from algites.lib.aac.coreintf.provisioning import AIcProvisionContext, AIcProvisioningResult

from .bindings import AIcBindingStore
from .errors import AIxProvisioningError, AIxSchemaValidationError
from .instances import AIcProviderInstanceRegistry, instance_to_dict
from .loading import load_class
from .persistence import AIcInMemoryStateStore, state_delete_mutation, state_put_mutation
from .schemas import AIcSchemaRegistry

_COMPONENT_STATE_NAMESPACE = "aac.component-provisioning"
_PROVIDER_NAMESPACE = "aac.provider-instances"


@dataclass(frozen=True, slots=True)
class AIcProvisioningOutcome:
    created_instance_ids: tuple[str, ...]
    state: Mapping[str, object]
    hook_called: bool
    diagnostics: tuple[str, ...] = ()


class AIcProvisioningEngine:
    """Core-controlled declarative provisioning with optional statically declared callback."""

    def __init__(
        self,
        registry: AIcProviderInstanceRegistry | None = None,
        *,
        schema_registry: AIcSchemaRegistry | None = None,
        store: AIiStateStore | None = None,
        binding_store: AIcBindingStore | None = None,
    ) -> None:
        self.store = store or (registry.store if registry is not None else AIcInMemoryStateStore())
        self.registry = registry or AIcProviderInstanceRegistry(self.store)
        self.schemas = schema_registry or AIcSchemaRegistry()
        self.bindings = binding_store

    @staticmethod
    def _state_key(application_scope_id: str, component_id: str) -> str:
        return f"{application_scope_id}:{component_id}"

    def provision(self, application_scope_id: str, descriptor: AIcComponentDescriptor) -> AIcProvisioningOutcome:
        staged = []
        diagnostics: list[str] = []

        for provider in descriptor.capability_providers:
            for declared in provider.initial_instances:
                existing = self.registry.find(
                    component_id=descriptor.id,
                    provider_definition_id=provider.id,
                    name=declared.name,
                )
                if existing:
                    continue
                configuration = dict(declared.configuration)
                state = AInProviderInstanceState.CONFIGURED
                if provider.configuration_schema is not None:
                    try:
                        configuration = self.schemas.normalize(provider.configuration_schema.resource_name, configuration)
                    except KeyError:
                        state = AInProviderInstanceState.UNCONFIGURED
                        diagnostics.append(f"schema {provider.configuration_schema.resource_name!r} is not registered for {provider.id!r}")
                    except AIxSchemaValidationError as exc:
                        state = AInProviderInstanceState.UNCONFIGURED
                        diagnostics.extend(
                            f"provider {provider.id!r} instance {declared.name!r}: {item}" for item in exc.diagnostics
                        )
                staged.append(self.registry.build(
                    descriptor.id,
                    provider,
                    name=declared.name,
                    configuration=configuration,
                    state=state,
                ))

        key = self._state_key(application_scope_id, descriptor.id)
        state = dict(self.store.get(_COMPONENT_STATE_NAMESPACE, key) or {})
        hook_called = False

        if descriptor.lifecycle.provision is not None:
            hook_class = load_class(descriptor.lifecycle.provision, AIiProvisioningHook)
            result = hook_class().provision(AIcProvisionContext(
                application_scope_id=application_scope_id,
                component=descriptor,
                existing_state=dict(state),
            ))
            if not isinstance(result, AIcProvisioningResult):
                raise AIxProvisioningError("provision hook returned an invalid result")
            requested: dict[str, object] = {}
            for change in result.requested_changes:
                if change.key in requested:
                    raise AIxProvisioningError(f"provision hook requested duplicate state key {change.key!r}")
                requested[change.key] = change.value
            state.update(requested)
            hook_called = True
            diagnostics.extend(result.diagnostics)

        mutations = tuple(
            state_put_mutation(self.store, _PROVIDER_NAMESPACE, instance.id, instance_to_dict(instance))
            for instance in staged
        ) + (state_put_mutation(self.store, _COMPONENT_STATE_NAMESPACE, key, state),)
        self.store.apply(mutations)
        for instance in staged:
            self.registry._instances[instance.id] = instance  # same atomic commit already completed

        return AIcProvisioningOutcome(
            created_instance_ids=tuple(instance.id for instance in staged),
            state=dict(state),
            hook_called=hook_called,
            diagnostics=tuple(diagnostics),
        )

    def validate_instances(self, descriptor: AIcComponentDescriptor) -> tuple[str, ...]:
        diagnostics: list[str] = []
        providers = {provider.id: provider for provider in descriptor.capability_providers}
        for instance in self.registry.find(component_id=descriptor.id):
            provider = providers[instance.provider_definition_id]
            if provider.configuration_schema is None:
                if instance.state is AInProviderInstanceState.UNCONFIGURED:
                    self.registry.update(instance.id, state=AInProviderInstanceState.CONFIGURED)
                continue
            try:
                configuration = dict(instance.configuration)
                target_schema = provider.configuration_schema.resource_name
                normalized = self.schemas.normalize(target_schema, configuration)
                self.registry.update(
                    instance.id,
                    configuration=normalized,
                    configuration_schema=target_schema,
                    state=AInProviderInstanceState.CONFIGURED,
                )
            except (KeyError, AIxSchemaValidationError) as exc:
                if isinstance(exc, AIxSchemaValidationError):
                    diagnostics.extend(f"instance {instance.id}: {item}" for item in exc.diagnostics)
                else:
                    diagnostics.append(f"instance {instance.id}: schema {provider.configuration_schema.resource_name!r} is not registered")
                self.registry.update(instance.id, state=AInProviderInstanceState.UNCONFIGURED)
        return tuple(diagnostics)

    def state(self, application_scope_id: str, component_id: str) -> Mapping[str, object]:
        return dict(self.store.get(_COMPONENT_STATE_NAMESPACE, self._state_key(application_scope_id, component_id)) or {})

    def unprovision(self, application_scope_id: str, descriptor: AIcComponentDescriptor) -> None:
        instances = self.registry.find(component_id=descriptor.id)
        if self.bindings is not None:
            referenced = []
            for instance in instances:
                referenced.extend(self.bindings.references_instance(instance.id))
            if referenced:
                raise AIxProvisioningError(
                    "cannot unprovision component while provider instances participate in bindings: "
                    + ", ".join(sorted({f"{item.consumer_instance_id}:{item.requirement_id}->{item.provider_instance_id}" for item in referenced}))
                )

        if descriptor.lifecycle.unprovision is not None:
            hook_class = load_class(descriptor.lifecycle.unprovision, AIiUnprovisioningHook)
            result = hook_class().unprovision(AIcProvisionContext(
                application_scope_id=application_scope_id,
                component=descriptor,
                existing_state=self.state(application_scope_id, descriptor.id),
            ))
            if not isinstance(result, AIcProvisioningResult):
                raise AIxProvisioningError("unprovision hook returned an invalid result")

        key = self._state_key(application_scope_id, descriptor.id)
        mutations = tuple(state_delete_mutation(self.store, _PROVIDER_NAMESPACE, instance.id) for instance in instances) + (
            state_delete_mutation(self.store, _COMPONENT_STATE_NAMESPACE, key),
        )
        self.store.apply(mutations)
        for instance in instances:
            self.registry._instances.pop(instance.id, None)

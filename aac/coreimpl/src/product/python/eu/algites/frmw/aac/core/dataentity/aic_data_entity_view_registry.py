from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from uuid import uuid4
from eu.algites.frmw.aac.core.dataentity.api import (
    AIcDataEntityEnvelope,
    AIcDataEntityImplementationBinding,
    AIcDataEntityType,
    AIcDataEntityViewBinding,
    AIcTypedDataEntityEnvelope,
    AInDataEntityState,
)
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderAccessMode
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcEndpointRegistry, AIcInvocationDispatcher
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

T = TypeVar("T")

class AIcDataEntityViewRegistry:
    def __init__(self) -> None:
        self._bindings: dict[tuple[str, int], AIcDataEntityViewBinding[object]] = {}
        self._by_interface: dict[type[object], AIcDataEntityViewBinding[object]] = {}

    def register(self, binding: AIcDataEntityViewBinding[object]) -> None:
        key = (binding.data_type.schema_id, binding.data_type.view_version)
        existing = self._bindings.get(key)
        if existing is not None and existing != binding:
            raise ValueError(f"conflicting data entity view binding for {key[0]}/{key[1]}")
        interface_existing = self._by_interface.get(binding.data_type.interface_type)
        if interface_existing is not None and interface_existing.data_type != binding.data_type:
            raise ValueError("data entity view interface is already registered for another schema/version")
        self._bindings[key] = binding
        self._by_interface[binding.data_type.interface_type] = binding

    def get(self, schema_id: str, version: int) -> AIcDataEntityViewBinding[object]:
        return self._bindings[(schema_id, version)]

    def for_type(self, data_type: AIcDataEntityType[T]) -> AIcDataEntityViewBinding[T]:
        binding = self.get(data_type.schema_id, data_type.view_version)
        if binding.data_type.interface_type is not data_type.interface_type:
            raise TypeError("registered Data Entity view interface differs from requested DataEntityType")
        return binding  # type: ignore[return-value]

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

class AIcDataEntityImplementationRegistry:
    def __init__(self) -> None:
        self._bindings: dict[str, AIcDataEntityImplementationBinding] = {}
        self._by_type: dict[type[object], AIcDataEntityImplementationBinding] = {}

    def register(self, binding: AIcDataEntityImplementationBinding) -> None:
        existing = self._bindings.get(binding.schema_id)
        if existing is not None and existing != binding:
            raise ValueError(f"conflicting Data Entity implementation for {binding.schema_id!r}")
        type_existing = self._by_type.get(binding.implementation_type)
        if type_existing is not None and type_existing.schema_id != binding.schema_id:
            raise ValueError("Data Entity implementation class is already registered for another schema")
        self._bindings[binding.schema_id] = binding
        self._by_type[binding.implementation_type] = binding

    def get(self, schema_id: str) -> AIcDataEntityImplementationBinding:
        return self._bindings[schema_id]

    def for_object(self, value: object) -> AIcDataEntityImplementationBinding:
        for implementation_type, binding in self._by_type.items():
            if isinstance(value, implementation_type):
                return binding
        raise KeyError(type(value))

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

class AIcProviderCapabilityInvoker:
    """Invoke one capability on one explicitly selected provider instance."""

    def __init__(
        self,
        provider: AIcProviderInstance,
        endpoints: AIcEndpointRegistry,
        dispatcher: AIcInvocationDispatcher,
    ) -> None:
        self.provider = provider
        self.endpoints = endpoints
        self.dispatcher = dispatcher

    def invoke(self, capability_id: str, version: int, operation_id: str, arguments: Mapping[str, object]) -> Mapping[str, object]:
        capability = self.provider.capability(capability_id)
        if version not in capability.versions:
            raise ValueError(
                f"provider {self.provider.id!r} does not provide {capability_id}/{version}"
            )
        invocation = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=None,
            capability_id=capability_id,
            capability_version=version,
            operation_id=operation_id,
            provider_instance_id=self.provider.id,
            arguments=dict(arguments),
        )
        output = self.dispatcher.invoke(self.endpoints.get(self.provider.id), invocation)
        if not output.success:
            raise RuntimeError(f"provider capability invocation failed: {output.error}")
        if not isinstance(output.result, Mapping):
            raise TypeError("Data Entity provider operation returned a non-object result")
        return dict(output.result)

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from ..instances import AIcProviderInstance
from ..configuration import AIcEffectiveConfiguration
from ..entitlement import AIcEntitlementContext
from ..invocation import AIiCapabilityHandle
from ..readiness import AIcReadinessResult


@dataclass(frozen=True, slots=True)
class AIcProviderRuntimeContext:
    application_scope_id: str
    provider_instance: AIcProviderInstance
    entitlement: AIcEntitlementContext
    component_configuration: AIcEffectiveConfiguration
    provider_instance_configuration: AIcEffectiveConfiguration


class AIiProviderRuntime(ABC):
    """Explicit AAC provider runtime marker with per-instance lifecycle callbacks.

    Capability operations are supplied by concrete provider-specific interfaces/classes.
    The lifecycle methods have no-op defaults, equivalent to default methods in a Java
    interface, so a provider overrides only the phases it needs.
    """

    def entitlement_changed(self, entitlement: AIcEntitlementContext) -> None:
        """Receive the Core-validated effective permission/constraint context."""
        pass

    def wire(self, bindings: Mapping[str, tuple[AIiCapabilityHandle, ...]]) -> None:
        pass

    def prepare_activation(self) -> None:
        pass

    def readiness(self) -> AIcReadinessResult:
        """Report dynamic runtime readiness after wiring/activation preparation.

        The default is READY so existing provider runtimes need no changes.
        """
        return AIcReadinessResult()

    def activate(self) -> None:
        pass

    def suspend(self, reason: str) -> None:
        pass

    def deactivate(self, reason: str) -> None:
        pass


class AIiProviderRuntimeFactory(ABC):
    """Optional statically declared factory for providers requiring custom construction."""

    @abstractmethod
    def create(self, context: AIcProviderRuntimeContext) -> AIiProviderRuntime: ...

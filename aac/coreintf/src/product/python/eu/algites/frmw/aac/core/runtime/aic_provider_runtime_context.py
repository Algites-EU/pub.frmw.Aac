from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping
from ..instances.api import AIcProviderInstance
from ..configuration.api import AIcEffectiveConfiguration
from ..entitlement.api import AIcEntitlementContext
from ..invocation.api import AIiCapabilityHandle
from ..readiness.api import AIcReadinessResult

@dataclass(frozen=True, slots=True)
class AIcProviderRuntimeContext:
    application_scope_id: str
    provider_instance: AIcProviderInstance
    entitlement: AIcEntitlementContext
    component_configuration: AIcEffectiveConfiguration
    provider_instance_configuration: AIcEffectiveConfiguration

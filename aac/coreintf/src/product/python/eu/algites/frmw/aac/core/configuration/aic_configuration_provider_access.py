from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_target import AIcConfigurationTarget
from .ain_configuration_provider_capability import AInConfigurationProviderCapability

@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderAccess:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_target: AIcConfigurationTarget
    technical_capabilities: tuple[AInConfigurationProviderCapability, ...]
    authorized_capabilities: tuple[AInConfigurationProviderCapability, ...]
    diagnostics: tuple[str, ...] = ()

    def allows(self, capability: AInConfigurationProviderCapability) -> bool:
        return capability in self.authorized_capabilities

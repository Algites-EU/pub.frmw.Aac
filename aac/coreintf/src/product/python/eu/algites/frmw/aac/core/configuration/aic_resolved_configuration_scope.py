from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_provider_binding import AIcConfigurationProviderBinding

@dataclass(frozen=True, slots=True)
class AIcResolvedConfigurationScope:
    definition_id: str
    configuration_scope: AIcConfigurationScope
    configuration_providers: tuple[AIcConfigurationProviderBinding, ...]
    policy_authority: bool = True

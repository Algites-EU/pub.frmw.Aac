from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_target import AIcConfigurationTarget

@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderRequest:
    configuration_target: AIcConfigurationTarget
    configuration_scope: AIcConfigurationScope
    context: Mapping[str, object] = field(default_factory=dict)

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationScopeResolutionRequest:
    configuration_scope_type: str
    definition_id: str
    context: Mapping[str, object] = field(default_factory=dict)

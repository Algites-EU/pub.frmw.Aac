from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationContributionProvenance:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_provider_priority: int
    provider_record_revision: str | int | None = None

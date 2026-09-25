from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_target import AIcConfigurationTarget

@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderSnapshot:
    configuration_scope: AIcConfigurationScope
    configuration_target: AIcConfigurationTarget
    record_revision: str | int | None
    payload: "AIcConfigurationPersistedPayload"

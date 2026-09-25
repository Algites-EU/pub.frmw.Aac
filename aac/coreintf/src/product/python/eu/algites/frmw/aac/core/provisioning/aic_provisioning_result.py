from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from ..descriptor.api import AIcComponentDescriptor

from .aic_requested_state_change import AIcRequestedStateChange

@dataclass(frozen=True, slots=True)
class AIcProvisioningResult:
    requested_changes: tuple[AIcRequestedStateChange, ...] = ()
    diagnostics: tuple[str, ...] = ()

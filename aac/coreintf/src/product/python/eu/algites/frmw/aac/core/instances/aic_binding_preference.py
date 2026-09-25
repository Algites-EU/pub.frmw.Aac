from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AIcProvidedCapability

@dataclass(frozen=True, slots=True)
class AIcBindingPreference:
    """Core-owned topology preference; references stable instance IDs, never names."""

    consumer_instance_id: str
    requirement_id: str
    provider_instance_ids: tuple[str, ...]

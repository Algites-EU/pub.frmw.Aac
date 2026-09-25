from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementProviderBinding:
    entitlement_provider_id: str

    def __post_init__(self) -> None:
        if not self.entitlement_provider_id:
            raise ValueError("entitlement_provider_id must not be empty")

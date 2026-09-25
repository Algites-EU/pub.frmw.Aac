from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementPermissionGrant:
    id: str
    valid_from: str | None = None
    valid_until: str | None = None
    constraints: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("entitlement permission grant id must not be empty")

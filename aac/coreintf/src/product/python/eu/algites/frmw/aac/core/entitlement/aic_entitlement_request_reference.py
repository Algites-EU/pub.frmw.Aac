from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementRequestReference:
    request_id: str
    request_digest: str

    def __post_init__(self) -> None:
        if not self.request_id or not self.request_digest:
            raise ValueError("entitlement request reference requires request_id and request_digest")

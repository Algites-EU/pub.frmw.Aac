from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_document import AIcEntitlementDocument

@dataclass(frozen=True, slots=True)
class AIcEntitlementEvidence:
    document: AIcEntitlementDocument
    evidence_type: str
    source: str | None = None
    verification_material: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_type:
            raise ValueError("entitlement evidence_type must not be empty")

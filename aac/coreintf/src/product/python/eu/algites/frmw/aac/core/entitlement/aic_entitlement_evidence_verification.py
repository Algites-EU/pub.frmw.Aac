from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementEvidenceVerification:
    valid: bool
    verifier_id: str
    diagnostics: tuple[str, ...] = ()
    signer_identity: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

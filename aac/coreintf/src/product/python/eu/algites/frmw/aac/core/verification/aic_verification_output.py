from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcVerificationOutput:
    valid: bool
    diagnostics: tuple[str, ...] = ()
    verifier_id: str | None = None
    signer_identity: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

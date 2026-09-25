from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageProvenance:
    source_id: str
    source_uri: str | None
    artifact_uri: str
    sha256: str
    downloaded_at: str
    verifier_id: str | None = None
    signer_identity: str | None = None
    verification_metadata: Mapping[str, object] = field(default_factory=dict)

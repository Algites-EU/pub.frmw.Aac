from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageSourceRegistration:
    id: str
    type: str
    uri: str
    authentication_profile_id: str | None = None
    verifier_id: str | None = None
    priority: int = 0
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type or not self.uri:
            raise ValueError("package source registration requires id/type/uri")

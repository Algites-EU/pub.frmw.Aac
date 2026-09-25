from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcVerificationInput:
    component_id: str
    component_version: int
    package: str | None
    source: str
    metadata: Mapping[str, object]
    artifact_path: str | None = None

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcUpgradeCompatibilityDiagnostic:
    component_id: str
    message: str
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    capability_id: str | None = None
    consumer_versions: tuple[int, ...] = ()
    provider_versions: tuple[int, ...] = ()
    available_provider_component_ids: tuple[str, ...] = ()
    blocking: bool = True
    code: str | None = None

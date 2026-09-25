from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcLifecycleContext:
    application_scope_id: str
    component_id: str
    component_version: int
    metadata: Mapping[str, object] = field(default_factory=dict)

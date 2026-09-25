from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from ..descriptor.api import AIcComponentDescriptor

@dataclass(frozen=True, slots=True)
class AIcProvisionContext:
    application_scope_id: str
    component: AIcComponentDescriptor
    existing_state: Mapping[str, object] = field(default_factory=dict)

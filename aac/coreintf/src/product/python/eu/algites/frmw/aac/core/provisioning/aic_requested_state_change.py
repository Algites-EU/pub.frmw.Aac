from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from ..descriptor.api import AIcComponentDescriptor

@dataclass(frozen=True, slots=True)
class AIcRequestedStateChange:
    key: str
    value: object

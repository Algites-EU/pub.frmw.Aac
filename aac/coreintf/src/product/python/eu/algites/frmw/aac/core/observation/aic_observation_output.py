from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcObservationOutput:
    accepted: bool = True
    diagnostic: str | None = None

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcValidationResult:
    valid: bool
    diagnostics: tuple[str, ...] = ()

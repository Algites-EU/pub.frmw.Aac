from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcAuthorizationDecision:
    allowed: bool
    diagnostics: tuple[str, ...] = ()

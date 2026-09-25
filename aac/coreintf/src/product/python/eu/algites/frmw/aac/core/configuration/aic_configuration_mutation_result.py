from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationMutationResult:
    record_revision: str | int | None = None
    changed_property_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

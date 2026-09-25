from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from eu.algites.frmw.aac.core.presentation.api import (
    AIcDisplayContent,
    AIcDisplayText,
    normalize_display_content,
    normalize_display_text,
)

@dataclass(frozen=True, slots=True)
class AIcUiBinding:
    consumer_instance_id: str
    requirement_id: str
    provider_instance_id: str
    capability_id: str
    capability_version: int

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

from .aic_ui_observation_selector import AIcUiObservationSelector

@dataclass(frozen=True, slots=True)
class AIcUiObservationBinding:
    observer_instance_id: str
    selectors: tuple[AIcUiObservationSelector, ...]

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

from .aic_ui_choice import AIcUiChoice

@dataclass(frozen=True, slots=True)
class AIcUiRequirementEditor:
    consumer_instance_id: str
    requirement_id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: str
    mandatory: bool
    selected_provider_instance_ids: tuple[str, ...]
    provider_choices: tuple[AIcUiChoice, ...]
    requested_authorizations: tuple[str, ...] = ()
    granted_authorizations: tuple[str, ...] = ()
    authorization_choices: tuple[AIcUiChoice, ...] = ()

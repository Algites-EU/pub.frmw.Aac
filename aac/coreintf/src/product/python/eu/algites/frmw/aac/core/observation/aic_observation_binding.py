from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

from .aic_observation_selector import AIcObservationSelector

@dataclass(frozen=True, slots=True)
class AIcObservationBinding:
    observer_instance_id: str
    selectors: tuple[AIcObservationSelector, ...]

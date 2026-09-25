from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_secret_reference import AIcSecretReference

@dataclass(frozen=True, slots=True)
class AIcAuthenticationParameter:
    value: object | None = None
    secret_reference: AIcSecretReference | None = None

    def __post_init__(self) -> None:
        if self.value is not None and self.secret_reference is not None:
            raise ValueError("authentication parameter may contain value or secret_reference, not both")

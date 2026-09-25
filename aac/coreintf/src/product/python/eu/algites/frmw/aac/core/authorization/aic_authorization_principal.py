from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcAuthorizationPrincipal:
    id: str
    type: str = "USER"
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("authorization principal id/type must not be empty")

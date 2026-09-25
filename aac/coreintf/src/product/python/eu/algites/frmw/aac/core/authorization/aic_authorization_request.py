from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

from .aic_authorization_principal import AIcAuthorizationPrincipal

@dataclass(frozen=True, slots=True)
class AIcAuthorizationRequest:
    action: str
    resource_type: str
    resource_id: str
    principal: AIcAuthorizationPrincipal | None = None
    context: Mapping[str, object] = field(default_factory=dict)
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.resource_id:
            raise ValueError("authorization request action/resource must not be empty")

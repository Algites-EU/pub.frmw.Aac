from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope_definition import AIcEntitlementLicensingScopeDefinition

@dataclass(frozen=True, slots=True)
class AIcEntitlementProfile:
    id: str
    version: int
    licensing_scopes: tuple[AIcEntitlementLicensingScopeDefinition, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or self.version < 1:
            raise ValueError("entitlement profile id must not be empty and version must be >= 1")
        ids = [item.id for item in self.licensing_scopes]
        if len(ids) != len(set(ids)):
            raise ValueError("entitlement licensing-scope definition ids must be unique inside a profile")

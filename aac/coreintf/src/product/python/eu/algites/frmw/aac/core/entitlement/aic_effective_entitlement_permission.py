from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_grant_provenance import AIcEntitlementGrantProvenance

@dataclass(frozen=True, slots=True)
class AIcEffectiveEntitlementPermission:
    id: str
    effective_from: str | None = None
    effective_until: str | None = None
    constraints: tuple[Mapping[str, object], ...] = ()
    provenance: tuple[AIcEntitlementGrantProvenance, ...] = ()
    implicit: bool = False

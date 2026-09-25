from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_provider_binding import AIcEntitlementProviderBinding

@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeDefinition:
    id: str
    licensing_scope_type: str
    licensing_scope_resolver_id: str
    entitlement_providers: tuple[AIcEntitlementProviderBinding, ...] = ()
    mandatory: bool = False
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.licensing_scope_type or not self.licensing_scope_resolver_id:
            raise ValueError("entitlement licensing-scope definition id/type/resolver must not be empty")
        provider_ids = [item.entitlement_provider_id for item in self.entitlement_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("entitlement-provider bindings must be unique inside one entitlement licensing-scope definition")

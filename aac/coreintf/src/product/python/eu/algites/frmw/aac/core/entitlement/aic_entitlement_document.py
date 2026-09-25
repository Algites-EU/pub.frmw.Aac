from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_component_grant import AIcEntitlementComponentGrant
from .aic_entitlement_issuer import AIcEntitlementIssuer
from .aic_entitlement_licensing_scope import AIcEntitlementLicensingScope
from .aic_entitlement_request_reference import AIcEntitlementRequestReference
from .aic_entitlement_subject import AIcEntitlementSubject

@dataclass(frozen=True, slots=True)
class AIcEntitlementDocument:
    format_version: int
    entitlement_id: str
    issuer: AIcEntitlementIssuer
    licensing_scope: AIcEntitlementLicensingScope
    subject: AIcEntitlementSubject
    components: tuple[AIcEntitlementComponentGrant, ...]
    issued_for_request: AIcEntitlementRequestReference | None = None
    issued_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.format_version < 1:
            raise ValueError("entitlement document format_version must be >= 1")
        if not self.entitlement_id:
            raise ValueError("entitlement_id must not be empty")
        if self.licensing_scope.id != self.subject.id:
            raise ValueError("entitlement licensing-scope concrete id must equal entitlement subject id")
        component_ids = [item.component_id for item in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component ids must be unique inside one entitlement document")

    def component(self, component_id: str) -> AIcEntitlementComponentGrant | None:
        for item in self.components:
            if item.component_id == component_id:
                return item
        return None

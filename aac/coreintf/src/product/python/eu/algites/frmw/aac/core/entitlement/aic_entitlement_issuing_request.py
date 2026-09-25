from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope import AIcEntitlementLicensingScope
from .aic_entitlement_subject import AIcEntitlementSubject
from .aic_requested_component_grant import AIcRequestedComponentGrant

@dataclass(frozen=True, slots=True)
class AIcEntitlementIssuingRequest:
    format_version: int
    request_id: str
    requested_licensing_scope: AIcEntitlementLicensingScope
    subject: AIcEntitlementSubject
    components: tuple[AIcRequestedComponentGrant, ...]
    generated_at: str | None = None
    request_digest: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.format_version < 1 or not self.request_id:
            raise ValueError("entitlement issuing request requires format_version >= 1 and request_id")
        if self.requested_licensing_scope.id != self.subject.id:
            raise ValueError("requested entitlement licensing-scope concrete id must equal entitlement subject id")
        ids = [item.component_id for item in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("requested component ids must be unique")

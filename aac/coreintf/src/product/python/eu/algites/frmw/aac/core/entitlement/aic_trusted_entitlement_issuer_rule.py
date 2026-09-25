from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcTrustedEntitlementIssuerRule:
    issuer_id: str
    component_ids: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    signer_identities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.issuer_id:
            raise ValueError("trusted entitlement issuer rule requires issuer_id")

    def allows(self, component_id: str, evidence_type: str, signer_identity: str | None = None) -> bool:
        if self.component_ids and component_id not in self.component_ids:
            return False
        if self.evidence_types and evidence_type not in self.evidence_types:
            return False
        if self.signer_identities and signer_identity not in self.signer_identities:
            return False
        return True

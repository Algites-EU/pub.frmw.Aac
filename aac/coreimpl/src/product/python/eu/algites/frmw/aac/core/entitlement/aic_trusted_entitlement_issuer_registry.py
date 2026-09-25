from __future__ import annotations
from eu.algites.frmw.aac.core.entitlement.api import AIcTrustedEntitlementIssuerRule, AIcEntitlementEvidenceVerification

class AIcTrustedEntitlementIssuerRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, tuple[AIcTrustedEntitlementIssuerRule, ...]] = {}

    def register(self, rule: AIcTrustedEntitlementIssuerRule) -> None:
        self._rules[rule.issuer_id] = self._rules.get(rule.issuer_id, ()) + (rule,)

    def is_trusted(
        self,
        issuer_id: str,
        component_id: str,
        evidence_type: str,
        verification: AIcEntitlementEvidenceVerification,
    ) -> bool:
        return any(
            rule.allows(component_id, evidence_type, verification.signer_identity)
            for rule in self._rules.get(issuer_id, ())
        )

    def has_rules(self) -> bool:
        return bool(self._rules)

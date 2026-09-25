from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcCapabilityEntitlementContext,
    AIcEffectiveEntitlementPermission,
    AIcEntitlementContext,
    AIcEntitlementDocument,
    AIcEntitlementEvidence,
    AIcEntitlementEvidenceVerification,
    AIcEntitlementGrantProvenance,
    AIcEntitlementSubject,
    AIcEntitlementProfile,
    AIcEntitlementProviderRequest,
    AIcEntitlementLicensingScopeResolutionRequest,
    AIcResolvedEntitlementLicensingScope,
    AIiEntitlementEvidenceVerifier,
    AIiEntitlementProvider,
    AIiEntitlementLicensingScopeResolver,
)
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance
from eu.algites.frmw.aac.core.implementation.errors import AIxEntitlementError
from eu.algites.frmw.aac.core.entitlement.trust import AIcTrustedEntitlementIssuerRegistry

from .aic_entitlement_evidence_verifier_registry import AIcEntitlementEvidenceVerifierRegistry
from .aic_entitlement_provider_registry import AIcEntitlementProviderRegistry
from .aic_trusted_bootstrap_entitlement_evidence_verifier import AIcTrustedBootstrapEntitlementEvidenceVerifier

def _effective_interval(records, instant: datetime):
    active = [record for record in records if _contains_instant(record[0], record[1], instant)]
    if not active:
        return None
    start = None if any(record[0] is None for record in active) else min(record[0] for record in active)
    end: datetime | None = None
    if all(record[1] is not None for record in active):
        end = max(record[1] for record in active if record[1] is not None)
    used = list(active)
    # Future overlapping/adjacent grants can extend a currently effective permission.
    changed = True
    while changed and end is not None:
        changed = False
        for record in records:
            if record in used:
                continue
            rec_start, rec_end = record[0], record[1]
            if rec_start is None or rec_start <= end:
                if rec_end is None:
                    end = None
                    used.append(record)
                    changed = True
                    break
                if rec_end >= instant and rec_end > end:
                    end = rec_end
                    used.append(record)
                    changed = True
    return start, end, used

def _contains_instant(start: datetime | None, end: datetime | None, instant: datetime) -> bool:
    return (start is None or start <= instant) and (end is None or instant <= end)

def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return _utc(parsed)

def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def _fmt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _utc(value).isoformat().replace("+00:00", "Z")

def _max_start(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)

def _min_end(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)

class AIcEntitlementManager:
    """Validate evidence and aggregate effective rights per capability version."""

    def __init__(
        self,
        providers: AIcEntitlementProviderRegistry | None = None,
        verifiers: AIcEntitlementEvidenceVerifierRegistry | None = None,
        trusted_issuers: AIcTrustedEntitlementIssuerRegistry | None = None,
        request_validator: Callable[[AIcEntitlementDocument], None] | None = None,
    ) -> None:
        self.providers = providers or AIcEntitlementProviderRegistry()
        self.verifiers = verifiers or AIcEntitlementEvidenceVerifierRegistry()
        self.trusted_issuers = trusted_issuers or AIcTrustedEntitlementIssuerRegistry()
        self.request_validator = request_validator
        if "TRUSTED_BOOTSTRAP" not in self.verifiers._verifiers:
            self.verifiers.register("TRUSTED_BOOTSTRAP", AIcTrustedBootstrapEntitlementEvidenceVerifier())
        self._cache: dict[tuple[str, str | None], AIcEntitlementContext] = {}

    def evaluate_component(
        self,
        descriptor: AIcComponentDescriptor,
        *,
        licensing_scopes: tuple[AIcResolvedEntitlementLicensingScope, ...] = (),
        provider_instance: AIcProviderInstance | None = None,
        context: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> AIcEntitlementContext:
        instant = _utc(now or datetime.now(timezone.utc))
        diagnostics: list[str] = []
        # (capability, version, permission) -> interval/provenance records
        intervals: dict[tuple[str, int, str], list[tuple[datetime | None, datetime | None, AIcEntitlementGrantProvenance, Mapping[str, object]]]] = {}
        transition_candidates: list[datetime] = []

        declarations = {
            (item.capability_id, item.capability_version): item
            for item in descriptor.provided_capability_entitlements
        }

        for capability in descriptor.provided_capability_entitlements:
            for permission in capability.permissions:
                if permission.implicit:
                    provenance = AIcEntitlementGrantProvenance(
                        "_AAC.implicit", "_AAC.implicit", "_AAC.implicit", AIcEntitlementLicensingScope("IMPLICIT", descriptor.id),
                        capability.capability_id, capability.capability_version, permission.id,
                    )
                    intervals.setdefault((capability.capability_id, capability.capability_version, permission.id), []).append(
                        (None, None, provenance, {})
                    )

        raw_context = dict(context or {})
        for resolved_scope in licensing_scopes:
            for binding in resolved_scope.entitlement_providers:
                provider = self.providers.get(binding.entitlement_provider_id)
                request = AIcEntitlementProviderRequest(resolved_scope.licensing_scope, raw_context, resolved_scope.subject)
                for evidence in provider.evidence(request):
                    verification = self.verifiers.verify(evidence)
                    if not verification.valid:
                        diagnostics.extend(verification.diagnostics or (f"invalid entitlement evidence from {binding.entitlement_provider_id}",))
                        continue
                    document = evidence.document
                    if self.request_validator is not None and document.issued_for_request is not None:
                        try:
                            self.request_validator(document)
                        except Exception as exc:
                            diagnostics.append(f"ignored entitlement {document.entitlement_id!r}: issuing request validation failed: {exc}")
                            continue
                    if document.licensing_scope != resolved_scope.licensing_scope:
                        diagnostics.append(
                            f"ignored entitlement {document.entitlement_id!r}: entitlement licensing-scope/subject does not match provider query"
                        )
                        continue
                    if resolved_scope.subject is not None and document.subject.id != resolved_scope.subject.id:
                        diagnostics.append(
                            f"ignored entitlement {document.entitlement_id!r}: subject id does not match trusted resolved subject"
                        )
                        continue
                    component = document.component(descriptor.id)
                    if component is not None and evidence.evidence_type != "TRUSTED_BOOTSTRAP":
                        if not self.trusted_issuers.is_trusted(
                            document.issuer.id, descriptor.id, evidence.evidence_type, verification
                        ):
                            diagnostics.append(
                                f"ignored entitlement {document.entitlement_id!r}: issuer {document.issuer.id!r} is not trusted "
                                f"for component {descriptor.id!r}"
                            )
                            continue
                    if component is None:
                        # Multi-component bundle can legitimately carry unrelated/dormant entries.
                        continue
                    doc_start = _parse_time(document.valid_from)
                    doc_end = _parse_time(document.valid_until)
                    if doc_start is not None:
                        transition_candidates.append(doc_start)
                    if doc_end is not None:
                        transition_candidates.append(doc_end)
                    for grant in component.grants:
                        declaration = declarations.get((grant.capability_id, grant.capability_version))
                        if declaration is None:
                            diagnostics.append(
                                f"ignored grant in entitlement {document.entitlement_id!r}: component does not declare provided capability "
                                f"{grant.capability_id}/{grant.capability_version} for entitlement"
                            )
                            continue
                        declared_permissions = {item.id: item for item in declaration.permissions}
                        for permission_grant in grant.permissions:
                            permission = declared_permissions.get(permission_grant.id)
                            if permission is None:
                                diagnostics.append(
                                    f"ignored undeclared permission {permission_grant.id!r} for {grant.capability_id}/{grant.capability_version} "
                                    f"from entitlement {document.entitlement_id!r}"
                                )
                                continue
                            accepted = permission.possible_licensing_scope_types
                            if accepted and document.licensing_scope.type not in accepted:
                                diagnostics.append(
                                    f"ignored permission {permission.id!r} for {grant.capability_id}/{grant.capability_version} from unsupported "
                                    f"entitlement licensing-scope type {document.licensing_scope.type!r}"
                                )
                                continue
                            start = _max_start(doc_start, _parse_time(permission_grant.valid_from))
                            end = _min_end(doc_end, _parse_time(permission_grant.valid_until))
                            if start is not None and end is not None and start > end:
                                diagnostics.append(
                                    f"ignored permission {permission.id!r} from entitlement {document.entitlement_id!r}: empty validity interval"
                                )
                                continue
                            if start is not None:
                                transition_candidates.append(start)
                            if end is not None:
                                transition_candidates.append(end)
                            provenance = AIcEntitlementGrantProvenance(
                                binding.entitlement_provider_id,
                                document.entitlement_id,
                                document.issuer.id,
                                document.licensing_scope,
                                grant.capability_id,
                                grant.capability_version,
                                permission.id,
                                _fmt(start),
                                _fmt(end),
                            )
                            intervals.setdefault((grant.capability_id, grant.capability_version, permission.id), []).append(
                                (start, end, provenance, permission_grant.constraints)
                            )

        by_capability: dict[tuple[str, int], dict[str, AIcEffectiveEntitlementPermission]] = {}
        for identity, permission_intervals in intervals.items():
            capability_id, capability_version, permission_id = identity
            merged = _effective_interval(permission_intervals, instant)
            if merged is None:
                continue
            start, end, used = merged
            permission_descriptor = declarations[(capability_id, capability_version)].permission(permission_id)
            effective = AIcEffectiveEntitlementPermission(
                permission_id,
                _fmt(start),
                _fmt(end),
                tuple(record[3] for record in used if record[3]),
                tuple(record[2] for record in used),
                permission_descriptor.implicit,
            )
            by_capability.setdefault((capability_id, capability_version), {})[permission_id] = effective

        capabilities = tuple(
            AIcCapabilityEntitlementContext(capability_id, version, dict(sorted(permissions.items())))
            for (capability_id, version), permissions in sorted(by_capability.items())
        )
        future_transitions = sorted({value for value in transition_candidates if value > instant})
        effective = AIcEntitlementContext(
            component_id=descriptor.id,
            capabilities=capabilities,
            next_transition_at=_fmt(future_transitions[0]) if future_transitions else None,
            diagnostics=tuple(diagnostics),
        )
        self._cache[(descriptor.id, provider_instance.id if provider_instance else None)] = effective
        return effective

    def cached_context(self, component_id: str, provider_instance_id: str | None = None) -> AIcEntitlementContext | None:
        return self._cache.get((component_id, provider_instance_id))

    def cached_contexts(self) -> tuple[AIcEntitlementContext, ...]:
        return tuple(self._cache.values())

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

from .aic_entitlement_provider_registry import AIcEntitlementProviderRegistry
from .aic_entitlement_evidence_verifier_registry import AIcEntitlementEvidenceVerifierRegistry
from .aic_trusted_bootstrap_entitlement_evidence_verifier import AIcTrustedBootstrapEntitlementEvidenceVerifier
from .aic_entitlement_licensing_scope_resolver_registry import AIcEntitlementLicensingScopeResolverRegistry
from .aic_static_entitlement_licensing_scope_resolver import AIcStaticEntitlementLicensingScopeResolver
from .aic_static_entitlement_provider import AIcStaticEntitlementProvider
from .aic_entitlement_context_resolver import AIcEntitlementContextResolver
from .aic_entitlement_manager import AIcEntitlementManager

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

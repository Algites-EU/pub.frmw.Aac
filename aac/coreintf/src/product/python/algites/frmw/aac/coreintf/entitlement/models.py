from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..presentation import AIcDisplayText


def _validate_licensing_scope_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("entitlement licensing scope type must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScope:
    """Concrete entitlement licensing-scope identity.

    The type is an extensible component-declared licensing contract identifier,
    not a configuration-scope enum.
    """

    type: str
    id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", _validate_licensing_scope_type(self.type))
        if self.id is not None and not self.id.strip():
            raise ValueError("entitlement licensing-scope id must not be empty when present")

    @property
    def key(self) -> str:
        return self.type if self.id is None else f"{self.type}({self.id})"


class AInPermissionRetryDisposition(str, Enum):
    SAFE_AFTER_ENTITLEMENT_CHANGE = "SAFE_AFTER_ENTITLEMENT_CHANGE"
    DO_NOT_RETRY = "DO_NOT_RETRY"


@dataclass(frozen=True, slots=True)
class AIcEntitlementSubject:
    id: str
    display_name: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("entitlement subject id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementIssuer:
    id: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("entitlement issuer id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementPermissionGrant:
    id: str
    valid_from: str | None = None
    valid_until: str | None = None
    constraints: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("entitlement permission grant id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementCapabilityGrant:
    capability_id: str
    capability_version: int
    permissions: tuple[AIcEntitlementPermissionGrant, ...]

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("entitlement capability grant capability_id must not be empty")
        if self.capability_version < 1:
            raise ValueError("entitlement capability grant capability_version must be >= 1")
        ids = [item.id for item in self.permissions]
        if len(ids) != len(set(ids)):
            raise ValueError("permission ids must be unique inside one capability-version grant")


@dataclass(frozen=True, slots=True)
class AIcEntitlementComponentGrant:
    component_id: str
    grants: tuple[AIcEntitlementCapabilityGrant, ...]

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("entitlement component grant component_id must not be empty")
        identities = [(item.capability_id, item.capability_version) for item in self.grants]
        if len(identities) != len(set(identities)):
            raise ValueError("capability id/version grants must be unique inside one entitlement component entry")


@dataclass(frozen=True, slots=True)
class AIcEntitlementRequestReference:
    request_id: str
    request_digest: str

    def __post_init__(self) -> None:
        if not self.request_id or not self.request_digest:
            raise ValueError("entitlement request reference requires request_id and request_digest")


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


@dataclass(frozen=True, slots=True)
class AIcRequestedCapabilityGrant:
    capability_id: str
    capability_version: int
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1:
            raise ValueError("requested capability grant requires capability id/version")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("requested permission ids must be unique")


@dataclass(frozen=True, slots=True)
class AIcRequestedComponentGrant:
    component_id: str
    requested_grants: tuple[AIcRequestedCapabilityGrant, ...]

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("requested component id must not be empty")
        identities = [(item.capability_id, item.capability_version) for item in self.requested_grants]
        if len(identities) != len(set(identities)):
            raise ValueError("requested capability id/version grants must be unique")


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


@dataclass(frozen=True, slots=True)
class AIcEntitlementEvidence:
    document: AIcEntitlementDocument
    evidence_type: str
    source: str | None = None
    verification_material: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_type:
            raise ValueError("entitlement evidence_type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementEvidenceVerification:
    valid: bool
    verifier_id: str
    diagnostics: tuple[str, ...] = ()
    signer_identity: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcEntitlementProviderRequest:
    licensing_scope: AIcEntitlementLicensingScope
    context: Mapping[str, object] = field(default_factory=dict)
    subject: AIcEntitlementSubject | None = None


@dataclass(frozen=True, slots=True)
class AIcEntitlementGrantProvenance:
    entitlement_provider_id: str
    entitlement_id: str
    issuer_id: str
    licensing_scope: AIcEntitlementLicensingScope
    capability_id: str
    capability_version: int
    permission_id: str
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(frozen=True, slots=True)
class AIcEffectiveEntitlementPermission:
    id: str
    effective_from: str | None = None
    effective_until: str | None = None
    constraints: tuple[Mapping[str, object], ...] = ()
    provenance: tuple[AIcEntitlementGrantProvenance, ...] = ()
    implicit: bool = False


@dataclass(frozen=True, slots=True)
class AIcCapabilityEntitlementContext:
    capability_id: str
    capability_version: int
    permissions: Mapping[str, AIcEffectiveEntitlementPermission] = field(default_factory=dict)

    def has_permission(self, permission_id: str) -> bool:
        return permission_id in self.permissions


@dataclass(frozen=True, slots=True)
class AIcEntitlementContext:
    component_id: str
    capabilities: tuple[AIcCapabilityEntitlementContext, ...] = ()
    next_transition_at: str | None = None
    diagnostics: tuple[str, ...] = ()

    def capability(self, capability_id: str, capability_version: int) -> AIcCapabilityEntitlementContext | None:
        for item in self.capabilities:
            if item.capability_id == capability_id and item.capability_version == capability_version:
                return item
        return None

    def has_permission(self, capability_id: str, capability_version: int, permission_id: str) -> bool:
        capability = self.capability(capability_id, capability_version)
        return capability is not None and capability.has_permission(permission_id)


@dataclass(frozen=True, slots=True)
class AIcEntitlementProviderBinding:
    entitlement_provider_id: str

    def __post_init__(self) -> None:
        if not self.entitlement_provider_id:
            raise ValueError("entitlement_provider_id must not be empty")


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


@dataclass(frozen=True, slots=True)
class AIcEntitlementRemediationRequest:
    component_id: str
    provider_instance_id: str | None
    capability_id: str
    capability_version: int
    permission_id: str | None
    remediation_hint: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcEntitlementRemediationOutcome:
    changed: bool
    diagnostics: tuple[str, ...] = ()


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


@dataclass(frozen=True, slots=True)
class AIcEntitlementProviderRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("entitlement-provider registration id and type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeResolverRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("entitlement licensing-scope resolver registration id and type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcEntitlementBootstrap:
    schema_version: int
    default_entitlement_profile_id: str
    entitlement_profiles: tuple[AIcEntitlementProfile, ...]
    entitlement_providers: tuple[AIcEntitlementProviderRegistration, ...] = ()
    licensing_scope_resolvers: tuple[AIcEntitlementLicensingScopeResolverRegistration, ...] = ()
    trusted_issuers: tuple[AIcTrustedEntitlementIssuerRule, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("entitlement bootstrap schema_version must be >= 1")
        profiles = {profile.id: profile for profile in self.entitlement_profiles}
        if len(profiles) != len(self.entitlement_profiles):
            raise ValueError("entitlement profile ids must be unique")
        if self.default_entitlement_profile_id not in profiles:
            raise ValueError("default_entitlement_profile_id must reference a configured profile")
        provider_ids = [item.id for item in self.entitlement_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("entitlement-provider registration ids must be unique")
        resolver_ids = [item.id for item in self.licensing_scope_resolvers]
        if len(resolver_ids) != len(set(resolver_ids)):
            raise ValueError("entitlement licensing-scope resolver registration ids must be unique")
        issuer_ids = [item.issuer_id for item in self.trusted_issuers]
        if len(issuer_ids) != len(set(issuer_ids)):
            raise ValueError("trusted entitlement issuer ids must be unique inside one bootstrap")
        provider_id_set = set(provider_ids)
        resolver_id_set = set(resolver_ids)
        for profile in self.entitlement_profiles:
            for definition in profile.licensing_scopes:
                if definition.licensing_scope_resolver_id not in resolver_id_set:
                    raise ValueError(
                        f"entitlement profile {profile.id!r} references unregistered entitlement licensing-scope resolver "
                        f"{definition.licensing_scope_resolver_id!r}"
                    )
                for binding in definition.entitlement_providers:
                    if binding.entitlement_provider_id not in provider_id_set:
                        raise ValueError(
                            f"entitlement profile {profile.id!r} references unregistered entitlement-provider "
                            f"{binding.entitlement_provider_id!r}"
                        )

    def profile(self, profile_id: str | None = None) -> AIcEntitlementProfile:
        target = profile_id or self.default_entitlement_profile_id
        for profile in self.entitlement_profiles:
            if profile.id == target:
                return profile
        raise KeyError(target)


@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeResolutionRequest:
    licensing_scope_type: str
    definition_id: str
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcResolvedEntitlementLicensingScope:
    definition_id: str
    licensing_scope: AIcEntitlementLicensingScope
    entitlement_providers: tuple[AIcEntitlementProviderBinding, ...] = ()
    subject: AIcEntitlementSubject | None = None

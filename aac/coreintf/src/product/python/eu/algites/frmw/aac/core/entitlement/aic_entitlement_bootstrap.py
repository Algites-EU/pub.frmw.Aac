from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope_resolver_registration import AIcEntitlementLicensingScopeResolverRegistration
from .aic_entitlement_profile import AIcEntitlementProfile
from .aic_entitlement_provider_registration import AIcEntitlementProviderRegistration
from .aic_trusted_entitlement_issuer_rule import AIcTrustedEntitlementIssuerRule

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

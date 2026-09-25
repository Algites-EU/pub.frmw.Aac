from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_authentication_profile import AIcAuthenticationProfile
from .aic_secret_provider_registration import AIcSecretProviderRegistration

@dataclass(frozen=True, slots=True)
class AIcSecurityBootstrap:
    schema_version: int
    secret_providers: tuple[AIcSecretProviderRegistration, ...] = ()
    authentication_profiles: tuple[AIcAuthenticationProfile, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("security bootstrap schema_version must be >= 1")
        provider_ids = [item.id for item in self.secret_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("secret-provider registration ids must be unique")
        profile_ids = [item.id for item in self.authentication_profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("authentication profile ids must be unique")

    def authentication_profile(self, profile_id: str) -> AIcAuthenticationProfile:
        for profile in self.authentication_profiles:
            if profile.id == profile_id:
                return profile
        raise KeyError(profile_id)

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..presentation import AIcDisplayText

WELL_KNOWN_AUTHENTICATION_MECHANISMS = (
    "NONE",
    "BASIC",
    "BEARER",
    "CLIENT_CERTIFICATE",
)


class AInSecretProviderCapability(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class AIcSecretReference:
    secret_provider_id: str
    key: str
    version: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.secret_provider_id:
            raise ValueError("secret_provider_id must not be empty")
        if not self.key:
            raise ValueError("secret reference key must not be empty")


@dataclass(frozen=True, slots=True)
class AIcAuthenticationParameter:
    value: object | None = None
    secret_reference: AIcSecretReference | None = None

    def __post_init__(self) -> None:
        if self.value is not None and self.secret_reference is not None:
            raise ValueError("authentication parameter may contain value or secret_reference, not both")


@dataclass(frozen=True, slots=True)
class AIcAuthenticationProfile:
    id: str
    mechanism: str
    parameters: Mapping[str, AIcAuthenticationParameter] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("authentication profile id must not be empty")
        mechanism = self.mechanism.strip()
        if not mechanism:
            raise ValueError("authentication mechanism must not be empty")
        object.__setattr__(self, "mechanism", mechanism)


@dataclass(frozen=True, slots=True)
class AIcAuthenticationRequest:
    profile: AIcAuthenticationProfile
    transport_kind: str
    endpoint: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transport_kind:
            raise ValueError("transport_kind must not be empty")


@dataclass(frozen=True, slots=True)
class AIcClientCertificateMaterial:
    certificate_path: str
    private_key_path: str | None = None
    private_key_password: str | None = None

    def __post_init__(self) -> None:
        if not self.certificate_path:
            raise ValueError("certificate_path must not be empty")


@dataclass(frozen=True, slots=True)
class AIcAuthenticationMaterial:
    headers: Mapping[str, str] = field(default_factory=dict)
    client_certificate: AIcClientCertificateMaterial | None = None
    properties: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcSecretProviderRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    bootstrap_safe: bool = False
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("secret-provider registration id/type must not be empty")


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

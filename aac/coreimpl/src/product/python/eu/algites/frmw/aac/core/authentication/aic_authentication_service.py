from __future__ import annotations
import base64
import os
from pathlib import Path
from typing import Mapping
from eu.algites.frmw.aac.core.authentication.api import (
    AInSecretProviderCapability,
    AIcAuthenticationMaterial,
    AIcAuthenticationProfile,
    AIcAuthenticationRequest,
    AIcClientCertificateMaterial,
    AIcSecretReference,
    AIiAuthenticationHandler,
    AIiSecretProvider,
    AIiSecretResolver,
)

from .aic_authentication_handler_registry import AIcAuthenticationHandlerRegistry
from .aic_authentication_profile_registry import AIcAuthenticationProfileRegistry
from .aic_basic_authentication_handler import AIcBasicAuthenticationHandler
from .aic_bearer_authentication_handler import AIcBearerAuthenticationHandler
from .aic_client_certificate_authentication_handler import AIcClientCertificateAuthenticationHandler
from .aic_none_authentication_handler import AIcNoneAuthenticationHandler
from .aic_secret_provider_registry import AIcSecretProviderRegistry

class AIcAuthenticationService:
    def __init__(self, secret_providers: AIcSecretProviderRegistry | None = None) -> None:
        self.secret_providers = secret_providers or AIcSecretProviderRegistry()
        self.profiles = AIcAuthenticationProfileRegistry()
        self.handlers = AIcAuthenticationHandlerRegistry()
        self.handlers.register("NONE", AIcNoneAuthenticationHandler())
        self.handlers.register("BASIC", AIcBasicAuthenticationHandler())
        self.handlers.register("BEARER", AIcBearerAuthenticationHandler())
        self.handlers.register("CLIENT_CERTIFICATE", AIcClientCertificateAuthenticationHandler())

    def register_profile(self, profile: AIcAuthenticationProfile) -> None:
        self.profiles.register(profile)

    def material(\
        self, profile_id: str | None, *, transport_kind: str, endpoint: str | None = None,\
        context: Mapping[str, object] | None = None,\
    ) -> AIcAuthenticationMaterial:
        if profile_id is None:
            return AIcAuthenticationMaterial()
        profile = self.profiles.get(profile_id)
        handler = self.handlers.get(profile.mechanism)
        return handler.authenticate(AIcAuthenticationRequest(profile, transport_kind, endpoint, dict(context or {})), self.secret_providers)

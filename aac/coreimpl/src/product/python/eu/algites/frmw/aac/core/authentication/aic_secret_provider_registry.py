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

class AIcSecretProviderRegistry(AIiSecretResolver):
    def __init__(self) -> None:
        self._providers: dict[str, AIiSecretProvider] = {}

    def register(self, secret_provider_id: str, provider: AIiSecretProvider) -> None:
        if not secret_provider_id:
            raise ValueError("secret_provider_id must not be empty")
        if secret_provider_id in self._providers:
            raise ValueError(f"secret-provider {secret_provider_id!r} is already registered")
        self._providers[secret_provider_id] = provider

    def contains(self, secret_provider_id: str) -> bool:
        return secret_provider_id in self._providers

    def get(self, secret_provider_id: str) -> AIiSecretProvider:
        return self._providers[secret_provider_id]

    def resolve_secret(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str | bytes:
        return self.get(reference.secret_provider_id).resolve(reference, context)

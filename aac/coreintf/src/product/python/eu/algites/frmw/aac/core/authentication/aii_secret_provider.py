from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping
from .models import (
    AInSecretProviderCapability,
    AIcAuthenticationMaterial,
    AIcAuthenticationRequest,
    AIcSecretReference,
)

class AIiSecretProvider(ABC):
    def capabilities(self, context: Mapping[str, object] | None = None) -> tuple[AInSecretProviderCapability, ...]:
        return (AInSecretProviderCapability.READ,)

    @abstractmethod
    def resolve(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str | bytes:
        """Resolve one secret reference."""

    def put(self, key: str, value: str | bytes, context: Mapping[str, object] | None = None) -> None:
        raise PermissionError("secret-provider is read-only")

    def delete(self, key: str, context: Mapping[str, object] | None = None) -> None:
        raise PermissionError("secret-provider is read-only")

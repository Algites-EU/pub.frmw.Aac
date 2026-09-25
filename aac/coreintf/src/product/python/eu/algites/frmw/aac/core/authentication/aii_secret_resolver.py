from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping
from .models import (
    AInSecretProviderCapability,
    AIcAuthenticationMaterial,
    AIcAuthenticationRequest,
    AIcSecretReference,
)

class AIiSecretResolver(ABC):
    @abstractmethod
    def resolve_secret(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str | bytes:
        """Resolve secret material without exposing storage details to the caller."""

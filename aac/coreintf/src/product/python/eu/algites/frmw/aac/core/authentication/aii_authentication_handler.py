from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping
from .models import (
    AInSecretProviderCapability,
    AIcAuthenticationMaterial,
    AIcAuthenticationRequest,
    AIcSecretReference,
)

from .aii_secret_resolver import AIiSecretResolver

class AIiAuthenticationHandler(ABC):
    @abstractmethod
    def authenticate(self, request: AIcAuthenticationRequest, secret_resolver: AIiSecretResolver) -> AIcAuthenticationMaterial:
        """Produce transport-neutral authentication material for a connection attempt."""

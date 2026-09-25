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

class AIcEnvironmentSecretProvider(AIiSecretProvider):
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def resolve(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str:
        key = self.prefix + reference.key
        if key not in os.environ:
            raise KeyError(f"environment secret {key!r} is not defined")
        return os.environ[key]

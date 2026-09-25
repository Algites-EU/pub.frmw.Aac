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

class AIcAuthenticationHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, AIiAuthenticationHandler] = {}

    def register(self, mechanism: str, handler: AIiAuthenticationHandler) -> None:
        mechanism = mechanism.strip()
        if not mechanism:
            raise ValueError("authentication mechanism must not be empty")
        self._handlers[mechanism] = handler

    def get(self, mechanism: str) -> AIiAuthenticationHandler:
        return self._handlers[mechanism]

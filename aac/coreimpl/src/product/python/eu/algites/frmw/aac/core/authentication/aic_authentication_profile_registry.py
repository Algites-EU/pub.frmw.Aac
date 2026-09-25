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

class AIcAuthenticationProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, AIcAuthenticationProfile] = {}

    def register(self, profile: AIcAuthenticationProfile) -> None:
        if profile.id in self._profiles:
            raise ValueError(f"authentication profile {profile.id!r} is already registered")
        self._profiles[profile.id] = profile

    def contains(self, profile_id: str) -> bool:
        return profile_id in self._profiles

    def get(self, profile_id: str) -> AIcAuthenticationProfile:
        return self._profiles[profile_id]

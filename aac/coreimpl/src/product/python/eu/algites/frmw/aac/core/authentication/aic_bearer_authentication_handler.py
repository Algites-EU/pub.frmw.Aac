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

def _parameter_text(profile, key, secret_resolver, context) -> str:
    parameter = profile.parameters.get(key)
    if parameter is None:
        raise ValueError(f"authentication profile {profile.id!r} requires parameter {key!r}")
    if parameter.secret_reference is not None:
        value = secret_resolver.resolve_secret(parameter.secret_reference, context)
    else:
        value = parameter.value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if value is None:
        raise ValueError(f"authentication parameter {key!r} has no value")
    return str(value)

class AIcBearerAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        token = _parameter_text(request.profile, "token", secret_resolver, request.context)
        return AIcAuthenticationMaterial(headers={"Authorization": f"Bearer {token}"})

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

class AIcBasicAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        username = _parameter_text(request.profile, "username", secret_resolver, request.context)
        password = _parameter_text(request.profile, "password", secret_resolver, request.context)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return AIcAuthenticationMaterial(headers={"Authorization": f"Basic {token}"})

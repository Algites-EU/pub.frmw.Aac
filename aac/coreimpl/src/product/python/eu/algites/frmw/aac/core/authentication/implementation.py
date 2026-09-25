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

from .aic_secret_provider_registry import AIcSecretProviderRegistry
from .aic_environment_secret_provider import AIcEnvironmentSecretProvider
from .aic_file_secret_provider import AIcFileSecretProvider
from .aic_authentication_handler_registry import AIcAuthenticationHandlerRegistry
from .aic_authentication_profile_registry import AIcAuthenticationProfileRegistry
from .aic_none_authentication_handler import AIcNoneAuthenticationHandler
from .aic_basic_authentication_handler import AIcBasicAuthenticationHandler
from .aic_bearer_authentication_handler import AIcBearerAuthenticationHandler
from .aic_client_certificate_authentication_handler import AIcClientCertificateAuthenticationHandler
from .aic_authentication_service import AIcAuthenticationService

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

def _optional_parameter_text(profile, key, secret_resolver, context) -> str | None:
    if key not in profile.parameters:
        return None
    return _parameter_text(profile, key, secret_resolver, context)

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .ain_secret_provider_capability import AInSecretProviderCapability
from .aic_secret_reference import AIcSecretReference
from .aic_authentication_parameter import AIcAuthenticationParameter
from .aic_authentication_profile import AIcAuthenticationProfile
from .aic_authentication_request import AIcAuthenticationRequest
from .aic_client_certificate_material import AIcClientCertificateMaterial
from .aic_authentication_material import AIcAuthenticationMaterial
from .aic_secret_provider_registration import AIcSecretProviderRegistration
from .aic_security_bootstrap import AIcSecurityBootstrap

WELL_KNOWN_AUTHENTICATION_MECHANISMS = (
    "NONE",
    "BASIC",
    "BEARER",
    "CLIENT_CERTIFICATE",
)

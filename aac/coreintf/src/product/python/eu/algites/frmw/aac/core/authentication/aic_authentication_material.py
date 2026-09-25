from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_client_certificate_material import AIcClientCertificateMaterial

@dataclass(frozen=True, slots=True)
class AIcAuthenticationMaterial:
    headers: Mapping[str, str] = field(default_factory=dict)
    client_certificate: AIcClientCertificateMaterial | None = None
    properties: Mapping[str, object] = field(default_factory=dict)

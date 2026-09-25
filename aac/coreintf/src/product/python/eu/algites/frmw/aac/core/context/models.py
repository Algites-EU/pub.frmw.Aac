from __future__ import annotations
from dataclasses import dataclass

from .aic_configuration_scope import AIcConfigurationScope

WELL_KNOWN_CONFIGURATION_SCOPE_TYPES = ("SYSTEM", "USER", "WORKSPACE")

def _validate_scope_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("scope type must not be empty")
    return normalized

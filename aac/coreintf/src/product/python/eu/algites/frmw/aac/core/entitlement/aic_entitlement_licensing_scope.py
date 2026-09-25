from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

def _validate_licensing_scope_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("entitlement licensing scope type must not be empty")
    return normalized

@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScope:
    """Concrete entitlement licensing-scope identity.

    The type is an extensible component-declared licensing contract identifier,
    not a configuration-scope enum.
    """

    type: str
    id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", _validate_licensing_scope_type(self.type))
        if self.id is not None and not self.id.strip():
            raise ValueError("entitlement licensing-scope id must not be empty when present")

    @property
    def key(self) -> str:
        return self.type if self.id is None else f"{self.type}({self.id})"

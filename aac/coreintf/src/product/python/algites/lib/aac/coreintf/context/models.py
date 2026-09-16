from __future__ import annotations

from dataclasses import dataclass

WELL_KNOWN_CONFIGURATION_SCOPE_TYPES = ("SYSTEM", "USER", "WORKSPACE")


def _validate_scope_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("scope type must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class AIcConfigurationScope:
    """Concrete configuration-scope identity.

    ``type`` is intentionally an extensible string rather than an AAC enum. SYSTEM,
    USER and WORKSPACE are well-known names; deployments may add CUSTOMER, TEAM,
    ORGANIZATION, TENANT or domain-specific types without changing AAC.
    """

    type: str
    id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", _validate_scope_type(self.type))
        if self.id is not None and not self.id.strip():
            raise ValueError("configuration-scope id must not be empty when present")

    @property
    def key(self) -> str:
        return self.type if self.id is None else f"{self.type}({self.id})"

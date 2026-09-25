from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AIcAuthorizationPrincipal:
    id: str
    type: str = "USER"
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("authorization principal id/type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcAuthorizationRequest:
    action: str
    resource_type: str
    resource_id: str
    principal: AIcAuthorizationPrincipal | None = None
    context: Mapping[str, object] = field(default_factory=dict)
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.resource_id:
            raise ValueError("authorization request action/resource must not be empty")


@dataclass(frozen=True, slots=True)
class AIcAuthorizationDecision:
    allowed: bool
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcComponentAuthorizationGrant:
    """Core-owned authorization grant for one consumer requirement.

    The grant is intentionally independent from entitlement. Permission IDs are
    defined by the consumed canonical capability contract and are meaningful to
    both Core and the capability provider.
    """

    consumer_instance_id: str
    requirement_id: str
    permission_ids: tuple[str, ...] = ()
    approved_by: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.consumer_instance_id or not self.requirement_id:
            raise ValueError("component authorization grant requires consumer instance and requirement")
        if len(self.permission_ids) != len(set(self.permission_ids)):
            raise ValueError("component authorization grant permission ids must be unique")
        if any(not value for value in self.permission_ids):
            raise ValueError("component authorization grant permission ids must not be empty")

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

@dataclass(frozen=True, slots=True)
class AIcPermissionDescriptor:
    id: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    possible_licensing_scope_types: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("permission id must not be empty")
        if len(self.possible_licensing_scope_types) != len(set(self.possible_licensing_scope_types)):
            raise ValueError("possible entitlement licensing scope types must be unique")

    @property
    def implicit(self) -> bool:
        """Permission is included/scope-free when no external entitlement licensing scope is possible."""
        return not self.possible_licensing_scope_types

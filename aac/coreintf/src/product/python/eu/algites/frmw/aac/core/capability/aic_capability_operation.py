from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_capability_operation_interaction import AIcCapabilityOperationInteraction
from .aic_operation_authorization_requirement import AIcOperationAuthorizationRequirement
from .aic_schema_ref import AIcSchemaRef
from .ain_capability_operation_interaction_kind import AInCapabilityOperationInteractionKind

@dataclass(frozen=True, slots=True)
class AIcCapabilityOperation:
    id: str
    interactions: tuple[AIcCapabilityOperationInteraction, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    authorization: AIcOperationAuthorizationRequirement | None = None
    sensitive_input_paths: tuple[str, ...] = ()
    sensitive_output_paths: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("operation id must not be empty")
        kinds = [item.kind for item in self.interactions]
        if len(kinds) != len(set(kinds)):
            raise ValueError("operation interaction kinds must be unique")

    def interaction(self, kind: AInCapabilityOperationInteractionKind) -> AIcCapabilityOperationInteraction | None:
        for item in self.interactions:
            if item.kind is kind:
                return item
        return None

    def schema_ref(self, kind: AInCapabilityOperationInteractionKind) -> AIcSchemaRef | None:
        item = self.interaction(kind)
        return None if item is None else item.schema

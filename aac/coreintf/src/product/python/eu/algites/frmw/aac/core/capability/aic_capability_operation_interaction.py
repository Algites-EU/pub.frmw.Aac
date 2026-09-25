from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_schema_ref import AIcSchemaRef
from .ain_capability_operation_interaction_kind import AInCapabilityOperationInteractionKind

@dataclass(frozen=True, slots=True)
class AIcCapabilityOperationInteraction:
    kind: AInCapabilityOperationInteractionKind
    schema: AIcSchemaRef

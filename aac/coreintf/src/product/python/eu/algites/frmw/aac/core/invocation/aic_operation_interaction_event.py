from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .ain_operation_interaction_event_type import AInOperationInteractionEventType
from .ain_operation_interaction_severity import AInOperationInteractionSeverity

@dataclass(frozen=True, slots=True)
class AIcOperationInteractionEvent:
    event_type: AInOperationInteractionEventType
    progress_id: str | None = None
    parent_progress_id: str | None = None
    phase_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    current: int | float | None = None
    total: int | float | None = None
    unit: str | None = None
    severity: AInOperationInteractionSeverity = AInOperationInteractionSeverity.INFO
    code: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type is AInOperationInteractionEventType.PROGRESS and not self.progress_id:
            raise ValueError("PROGRESS interaction event requires progress_id")
        if self.progress_id is not None and not self.progress_id:
            raise ValueError("operation interaction progress_id must not be empty")
        if self.parent_progress_id is not None and not self.parent_progress_id:
            raise ValueError("operation interaction parent_progress_id must not be empty")
        if self.parent_progress_id is not None and self.parent_progress_id == self.progress_id:
            raise ValueError("operation interaction progress cannot be its own parent")
        if self.phase_id is not None and not self.phase_id:
            raise ValueError("operation interaction phase_id must not be empty")
        if self.unit is not None and not self.unit:
            raise ValueError("operation interaction unit must not be empty")
        if self.code is not None and not self.code:
            raise ValueError("operation interaction code must not be empty")
        if self.total is not None and self.total < 0:
            raise ValueError("operation interaction total must be non-negative")
        if self.current is not None and self.current < 0:
            raise ValueError("operation interaction current must be non-negative")

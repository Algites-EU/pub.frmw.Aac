from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

@dataclass(frozen=True, slots=True)
class AIcOperationFailure:
    system_message: str
    exception_type: str
    user_message: AIcDisplayText | None = None
    error_code: str | None = None
    stack_trace: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)
    extension: object | None = None

    def __post_init__(self) -> None:
        if not self.system_message:
            raise ValueError("operation failure system_message must not be empty")
        if not self.exception_type:
            raise ValueError("operation failure exception_type must not be empty")
        if self.error_code is not None and not self.error_code:
            raise ValueError("operation failure error_code must not be empty")

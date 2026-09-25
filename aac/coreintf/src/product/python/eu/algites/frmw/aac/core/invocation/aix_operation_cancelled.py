from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

class AIxOperationCancelled(RuntimeError):
    """Raised by a cooperative provider after observing cancellation_requested."""

    def __init__(
        self,
        message: str = "operation cancelled",
        *,
        state_result: object = None,
        has_state_result: bool = False,
    ) -> None:
        super().__init__(message)
        self.state_result = state_result
        self.has_state_result = has_state_result

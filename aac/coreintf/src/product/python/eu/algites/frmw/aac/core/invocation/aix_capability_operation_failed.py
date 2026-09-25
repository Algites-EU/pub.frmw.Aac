from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_failure import AIcOperationFailure

class AIxCapabilityOperationFailed(RuntimeError):
    """Caller-side AAC exception representing a FAILED capability-operation execution."""

    def __init__(self, failure: AIcOperationFailure) -> None:
        super().__init__(failure.system_message)
        self.failure = failure
        self.additional_data = failure.extension

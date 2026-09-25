from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_failure import AIcOperationFailure
from .aix_capability_operation_failed import AIxCapabilityOperationFailed

AIxOperationFailureT = TypeVar("AIxOperationFailureT", bound=AIxCapabilityOperationFailed)

class AIiOperationFailureExceptionFactory(Generic[AIxOperationFailureT], ABC):
    @abstractmethod
    def create(self, failure: AIcOperationFailure) -> AIxOperationFailureT: ...

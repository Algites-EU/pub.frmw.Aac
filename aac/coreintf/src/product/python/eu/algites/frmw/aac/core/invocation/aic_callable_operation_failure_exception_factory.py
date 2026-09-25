from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_failure import AIcOperationFailure
from .aii_operation_failure_exception_factory import AIiOperationFailureExceptionFactory
from .aix_capability_operation_failed import AIxCapabilityOperationFailed

AIxOperationFailureT = TypeVar("AIxOperationFailureT", bound=AIxCapabilityOperationFailed)

class AIcCallableOperationFailureExceptionFactory(AIiOperationFailureExceptionFactory[AIxOperationFailureT]):
    def __init__(self, factory: Callable[[AIcOperationFailure], AIxOperationFailureT]) -> None:
        self._factory = factory

    def create(self, failure: AIcOperationFailure) -> AIxOperationFailureT:
        result = self._factory(failure)
        if not isinstance(result, AIxCapabilityOperationFailed):
            raise TypeError("operation failure exception factory must return AIxCapabilityOperationFailed")
        return result

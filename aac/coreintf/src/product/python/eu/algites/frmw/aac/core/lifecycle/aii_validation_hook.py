from __future__ import annotations
from abc import ABC, abstractmethod
from ..provisioning.api import AIcProvisionContext, AIcProvisioningResult
from .models import AIcLifecycleContext, AIcValidationResult

class AIiValidationHook(ABC):
    @abstractmethod
    def validate(self, context: AIcLifecycleContext) -> AIcValidationResult: ...

from __future__ import annotations
from abc import ABC, abstractmethod
from ..provisioning.api import AIcProvisionContext, AIcProvisioningResult
from .models import AIcLifecycleContext, AIcValidationResult

class AIiProvisioningHook(ABC):
    @abstractmethod
    def provision(self, context: AIcProvisionContext) -> AIcProvisioningResult: ...

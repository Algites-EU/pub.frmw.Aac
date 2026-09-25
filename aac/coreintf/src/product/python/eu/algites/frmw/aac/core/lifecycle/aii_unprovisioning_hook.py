from __future__ import annotations
from abc import ABC, abstractmethod
from ..provisioning.api import AIcProvisionContext, AIcProvisioningResult
from .models import AIcLifecycleContext, AIcValidationResult

class AIiUnprovisioningHook(ABC):
    @abstractmethod
    def unprovision(self, context: AIcProvisionContext) -> AIcProvisioningResult: ...

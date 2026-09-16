from __future__ import annotations

from abc import ABC, abstractmethod

from ..provisioning import AIcProvisionContext, AIcProvisioningResult
from .models import AIcLifecycleContext, AIcValidationResult


class AIiProvisioningHook(ABC):
    @abstractmethod
    def provision(self, context: AIcProvisionContext) -> AIcProvisioningResult: ...


class AIiValidationHook(ABC):
    @abstractmethod
    def validate(self, context: AIcLifecycleContext) -> AIcValidationResult: ...


class AIiUnprovisioningHook(ABC):
    @abstractmethod
    def unprovision(self, context: AIcProvisionContext) -> AIcProvisioningResult: ...

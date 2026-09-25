from __future__ import annotations
from abc import ABC, abstractmethod
from .models import AIcInvocationInput, AIcInvocationOutput

class AIiCapabilityEndpoint(ABC):
    @abstractmethod
    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput: ...

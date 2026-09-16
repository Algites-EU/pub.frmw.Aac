from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcAuthorizationDecision, AIcAuthorizationRequest


class AIiAuthorizationProvider(ABC):
    @abstractmethod
    def authorize(self, request: AIcAuthorizationRequest) -> AIcAuthorizationDecision:
        """Return an application authorization decision independent of transport credentials."""

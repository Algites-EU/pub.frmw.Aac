from __future__ import annotations
from abc import ABC, abstractmethod
from .models import (
    AInConfigurationProviderCapability,
    AIcConfigurationChangeSet,
    AIcConfigurationContribution,
    AIcConfigurationMutationResult,
    AIcConfigurationPersistedPayload,
    AIcConfigurationProviderRequest,
    AIcConfigurationProviderSnapshot,
    AIcConfigurationScopeResolutionRequest,
)
from ..context.api import AIcConfigurationScope
from ..persistence.api import AInPersistenceCapability, AInRecordRevisionKind

class AIiConfigurationScopeResolver(ABC):
    @abstractmethod
    def resolve(self, request: AIcConfigurationScopeResolutionRequest) -> AIcConfigurationScope | None:
        """Resolve one profile configuration-scope definition to a concrete identity."""

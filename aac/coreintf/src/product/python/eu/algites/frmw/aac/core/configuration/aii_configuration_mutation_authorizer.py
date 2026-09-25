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

class AIiConfigurationMutationAuthorizer(ABC):
    def authorized_capabilities(
        self, request: AIcConfigurationProviderRequest, actor_context,
        provider_capabilities: tuple[AInConfigurationProviderCapability, ...],
    ) -> tuple[AInConfigurationProviderCapability, ...]:
        """Return mutation capabilities the current application principal may use.

        The safe default exposes only READ. Concrete product authorizers should override.
        """
        return tuple(item for item in provider_capabilities if item is AInConfigurationProviderCapability.READ)

    @abstractmethod
    def authorize(self, change_set: AIcConfigurationChangeSet) -> tuple[bool, tuple[str, ...]]:
        """Authorize one Core-mediated configuration mutation for the current principal/context."""

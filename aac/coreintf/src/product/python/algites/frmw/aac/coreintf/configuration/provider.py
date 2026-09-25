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
from ..context import AIcConfigurationScope
from ..persistence import AInPersistenceCapability, AInRecordRevisionKind


class AIiConfigurationProvider(ABC):

    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.OPAQUE_STRING

    def persistence_capabilities(
        self, request: AIcConfigurationProviderRequest
    ) -> tuple[AInPersistenceCapability, ...]:
        """Declare persistence guarantees independently from logical configuration operations.

        The baseline is read-only. Writable providers override this method when they can guarantee
        conditional single-record replacement or genuine multi-record transactions. An atomic
        change-set inside one configuration document is still a single-record mutation and MUST
        NOT be advertised as ``MULTI_RECORD_TRANSACTION`` merely because several properties change.
        """
        return (AInPersistenceCapability.READ,)
    def snapshot(self, request: AIcConfigurationProviderRequest) -> AIcConfigurationProviderSnapshot | None:
        """Return a versioned persisted snapshot when this provider exposes one."""
        return None

    @abstractmethod
    def contributions(self, request: AIcConfigurationProviderRequest) -> tuple[AIcConfigurationContribution, ...]:
        """Return normalized contributions for one target in one concrete configuration-scope."""

    def capabilities(self, request: AIcConfigurationProviderRequest) -> tuple[AInConfigurationProviderCapability, ...]:
        """Return technical provider capabilities for this target/scope/context."""
        return (AInConfigurationProviderCapability.READ,)

    def apply_changes(self, change_set: AIcConfigurationChangeSet) -> AIcConfigurationMutationResult:
        """Atomically apply a normalized change-set when supported."""
        raise PermissionError("configuration-provider is read-only")

    def replace_payload(
        self, request: AIcConfigurationProviderRequest, payload: AIcConfigurationPersistedPayload,
        expected_record_revision: str | int | None = None,
    ) -> AIcConfigurationMutationResult:
        """Atomically replace a complete versioned payload, primarily for Core-orchestrated migration."""
        raise PermissionError("configuration-provider does not support payload replacement")


class AIiConfigurationScopeResolver(ABC):
    @abstractmethod
    def resolve(self, request: AIcConfigurationScopeResolutionRequest) -> AIcConfigurationScope | None:
        """Resolve one profile configuration-scope definition to a concrete identity."""


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

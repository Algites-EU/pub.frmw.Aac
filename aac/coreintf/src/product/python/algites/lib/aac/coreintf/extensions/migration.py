from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcEntityExtensionMigrationRequest, AIcEntityExtensionMigrationResult


class AIiEntityExtensionDataMigrator(ABC):
    @abstractmethod
    def migrate(self, request: AIcEntityExtensionMigrationRequest) -> AIcEntityExtensionMigrationResult:
        """Transform one component-owned payload without directly mutating Core persistence."""

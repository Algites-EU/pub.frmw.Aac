from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcConfigurationMigrationRequest, AIcConfigurationMigrationResult


class AIiConfigurationMigrator(ABC):
    @abstractmethod
    def migrate(self, request: AIcConfigurationMigrationRequest) -> AIcConfigurationMigrationResult:
        """Transform values and policy-modes without directly mutating persistence."""

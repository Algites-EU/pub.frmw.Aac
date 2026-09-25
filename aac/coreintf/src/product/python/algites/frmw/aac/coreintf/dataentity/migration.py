from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcDataEntityMigrationRequest, AIcDataEntityMigrationResult


class AIiDataEntityMigrator(ABC):
    @abstractmethod
    def migrate(self, request: AIcDataEntityMigrationRequest) -> AIcDataEntityMigrationResult:
        """Transform one data entity payload without directly mutating persistence."""

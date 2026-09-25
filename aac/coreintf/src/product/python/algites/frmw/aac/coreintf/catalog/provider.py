from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcCatalogEntry, AIcCatalogQuery


class AIiCatalogProvider(ABC):
    @abstractmethod
    def query(self, query: AIcCatalogQuery) -> tuple[AIcCatalogEntry, ...]: ...

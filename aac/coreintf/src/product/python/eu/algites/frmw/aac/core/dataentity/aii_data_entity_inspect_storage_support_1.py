from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping

class AIiDataEntityInspectStorageSupport_1(ABC):
    @abstractmethod
    def inspect_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...

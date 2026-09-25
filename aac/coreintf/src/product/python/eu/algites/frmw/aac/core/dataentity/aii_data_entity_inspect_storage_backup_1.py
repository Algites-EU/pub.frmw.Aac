from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping

class AIiDataEntityInspectStorageBackup_1(ABC):
    @abstractmethod
    def inspect_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...

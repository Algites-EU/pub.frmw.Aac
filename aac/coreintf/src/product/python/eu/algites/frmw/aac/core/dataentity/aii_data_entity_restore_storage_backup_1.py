from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping

class AIiDataEntityRestoreStorageBackup_1(ABC):
    @abstractmethod
    def restore_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...

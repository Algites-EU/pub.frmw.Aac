from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class AIiDataEntityGetRecord_1(ABC):
    @abstractmethod
    def get_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityQueryRecords_1(ABC):
    @abstractmethod
    def query_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityApplyDirectRecordChanges_1(ABC):
    @abstractmethod
    def apply_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityInspectStorageSupport_1(ABC):
    @abstractmethod
    def inspect_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityEnsureStorageSupport_1(ABC):
    @abstractmethod
    def ensure_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityRetireStorageSupport_1(ABC):
    @abstractmethod
    def retire_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityCreateStorageBackup_1(ABC):
    @abstractmethod
    def create_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityInspectStorageBackup_1(ABC):
    @abstractmethod
    def inspect_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


class AIiDataEntityRestoreStorageBackup_1(ABC):
    @abstractmethod
    def restore_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AInDataEntityState(str, Enum):
    ACTIVE = "ACTIVE"
    TOMBSTONE = "TOMBSTONE"


@dataclass(frozen=True, slots=True)
class AIcDataEntityIdentity:
    schema_id: str
    uid: str

    def __post_init__(self) -> None:
        if not self.schema_id or not self.uid:
            raise ValueError("data entity identity requires non-empty schema_id and uid")


@dataclass(frozen=True, slots=True)
class AIcDataEntityEnvelope:
    uid: str
    schema_id: str
    schema_version: int
    record_revision: int | str
    state: AInDataEntityState
    payload: object

    def __post_init__(self) -> None:
        if not self.uid or not self.schema_id:
            raise ValueError("data entity envelope requires non-empty uid and schema_id")
        if self.schema_version < 1:
            raise ValueError("data entity schema_version must be >= 1")
        if isinstance(self.record_revision, int):
            if self.record_revision < 1:
                raise ValueError("integer data entity record_revision must be >= 1")
        elif isinstance(self.record_revision, str):
            if not self.record_revision:
                raise ValueError("string data entity record_revision must not be empty")
        else:
            raise TypeError("data entity record_revision must be an integer or opaque string")

    @property
    def identity(self) -> AIcDataEntityIdentity:
        return AIcDataEntityIdentity(self.schema_id, self.uid)


@dataclass(frozen=True, slots=True)
class AIcDataEntityMigrationRequest:
    source: AIcDataEntityEnvelope
    target_schema_version: int

    def __post_init__(self) -> None:
        if self.target_schema_version < 1:
            raise ValueError("target data entity schema version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcDataEntityMigrationResult:
    schema_id: str
    schema_version: int
    payload: object
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_id or self.schema_version < 1:
            raise ValueError("data entity migration result requires schema id/version >= 1")


@dataclass(frozen=True, slots=True)
class AIcDataEntityReferenceDefinition:
    source_schema_id: str
    source_schema_version: int
    schema_path: tuple[str, ...]
    target_schema_id: str

    def __post_init__(self) -> None:
        if not self.source_schema_id or not self.target_schema_id:
            raise ValueError("data entity reference definition requires source and target schema ids")
        if self.source_schema_version < 1:
            raise ValueError("data entity reference source schema version must be >= 1")

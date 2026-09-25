from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcOperationAuthorizationRequirement:
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.all_of) != len(set(self.all_of)):
            raise ValueError("authorization all_of permissions must be unique")
        if len(self.any_of) != len(set(self.any_of)):
            raise ValueError("authorization any_of permissions must be unique")
        if any(not value for value in (*self.all_of, *self.any_of)):
            raise ValueError("authorization permission references must not be empty")

    @property
    def permission_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.all_of, *self.any_of)))

    def is_satisfied_by(self, permissions: set[str] | frozenset[str] | tuple[str, ...]) -> bool:
        granted = set(permissions)
        return all(value in granted for value in self.all_of) and (
            not self.any_of or any(value in granted for value in self.any_of)
        )

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..presentation import AIcDisplayText


class AInConsumerCardinality(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"


@dataclass(frozen=True, slots=True)
class AIcCapabilityRef:
    id: str
    version: int

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("capability id must not be empty")
        if self.version < 1:
            raise ValueError("capability version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcAuthorizationPermissionDescriptor:
    id: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("authorization permission id must not be empty")


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


@dataclass(frozen=True, slots=True)
class AIcCapabilityOperation:
    id: str
    input_type: str = "Object"
    output_type: str = "Object"
    input_schema: str | None = None
    output_schema: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    authorization: AIcOperationAuthorizationRequirement | None = None
    sensitive_input_paths: tuple[str, ...] = ()
    sensitive_output_paths: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("operation id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcCapabilityContract:
    capability: AIcCapabilityRef
    operations: tuple[AIcCapabilityOperation, ...]
    authorization_permissions: tuple[AIcAuthorizationPermissionDescriptor, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        operation_ids = [operation.id for operation in self.operations]
        if not operation_ids:
            raise ValueError("a capability contract must define at least one operation")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation ids must be unique inside a capability contract version")
        permission_ids = [permission.id for permission in self.authorization_permissions]
        if len(permission_ids) != len(set(permission_ids)):
            raise ValueError("authorization permission ids must be unique inside a capability contract version")
        known = set(permission_ids)
        for operation in self.operations:
            if operation.authorization is None:
                continue
            unknown = set(operation.authorization.permission_ids) - known
            if unknown:
                raise ValueError(
                    f"operation {operation.id!r} references undeclared authorization permissions {sorted(unknown)!r}"
                )

    def operation(self, operation_id: str) -> AIcCapabilityOperation:
        for operation in self.operations:
            if operation.id == operation_id:
                return operation
        raise KeyError(operation_id)

    def authorization_permission(self, permission_id: str) -> AIcAuthorizationPermissionDescriptor:
        for permission in self.authorization_permissions:
            if permission.id == permission_id:
                return permission
        raise KeyError(permission_id)

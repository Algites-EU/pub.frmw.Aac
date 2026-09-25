from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_authorization_permission_descriptor import AIcAuthorizationPermissionDescriptor
from .aic_capability_operation import AIcCapabilityOperation
from .aic_capability_ref import AIcCapabilityRef

@dataclass(frozen=True, slots=True)
class AIcCapabilityContract:
    capability: AIcCapabilityRef
    group_id: str
    operations: tuple[AIcCapabilityOperation, ...]
    authorization_permissions: tuple[AIcAuthorizationPermissionDescriptor, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("capability group id must not be empty")
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

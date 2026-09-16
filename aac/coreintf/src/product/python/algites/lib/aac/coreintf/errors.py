class AIxAACError(Exception):
    """Base error for the public AAC Python binding."""


class AIxContractError(AIxAACError):
    """Raised for an invalid capability contract."""


class AIxDescriptorError(AIxAACError):
    """Raised for an invalid component descriptor."""


class AIxLifecycleError(AIxAACError):
    """Raised for a lifecycle contract failure."""


class AIxPermissionDenied(AIxAACError):
    """Standard provider operation denial based on the current entitlement context."""

    def __init__(
        self,
        message: str = "permission for operation is missing",
        *,
        capability_id: str | None = None,
        capability_version: int | None = None,
        permission_id: str | None = None,
        retry_disposition=None,
        remediation_hint: str | None = None,
    ) -> None:
        from .entitlement import AInPermissionRetryDisposition

        self.capability_id = capability_id
        self.capability_version = capability_version
        self.permission_id = permission_id
        self.retry_disposition = retry_disposition or AInPermissionRetryDisposition.DO_NOT_RETRY
        self.remediation_hint = remediation_hint
        super().__init__(message)


class AIxPersistedSchemaIncompatible(AIxAACError):
    """Stored component-owned payload cannot be interpreted/migrated by the installed component."""

    def __init__(self, schema_id: str, source_version: int, target_version: int, message: str | None = None) -> None:
        self.schema_id = schema_id
        self.source_version = source_version
        self.target_version = target_version
        super().__init__(message or f"persisted schema {schema_id}/{source_version} is incompatible with target {target_version}")


class AIxPersistedPayloadMigrationError(AIxAACError):
    """A component-owned persisted payload migration failed contract validation."""


class AIxAuthorizationDenied(AIxAACError):
    """Core bridge rejected a capability invocation before provider execution."""

    def __init__(
        self,
        message: str = "authorization for operation is missing",
        *,
        capability_id: str | None = None,
        capability_version: int | None = None,
        operation_id: str | None = None,
        required_all_of: tuple[str, ...] = (),
        required_any_of: tuple[str, ...] = (),
    ) -> None:
        self.capability_id = capability_id
        self.capability_version = capability_version
        self.operation_id = operation_id
        self.required_all_of = required_all_of
        self.required_any_of = required_any_of
        super().__init__(message)


class AIxPackageManagementError(AIxAACError):
    """Base error for package-store/source/install operations."""


class AIxPackageDigestMismatch(AIxPackageManagementError):
    """Downloaded or copied package bytes do not match the expected digest."""


class AIxPackageRevisionConflict(AIxPackageManagementError):
    """Requested package selection/lock cannot be reconciled deterministically."""

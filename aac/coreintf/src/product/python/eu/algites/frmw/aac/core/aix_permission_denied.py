from .aix_aac_error import AIxAACError

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
        from .entitlement.api import AInPermissionRetryDisposition

        self.capability_id = capability_id
        self.capability_version = capability_version
        self.permission_id = permission_id
        self.retry_disposition = retry_disposition or AInPermissionRetryDisposition.DO_NOT_RETRY
        self.remediation_hint = remediation_hint
        super().__init__(message)

from .aix_aac_error import AIxAACError

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

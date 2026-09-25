from .aix_aac_error import AIxAACError

class AIxPersistedSchemaIncompatible(AIxAACError):
    """Stored component-owned payload cannot be interpreted/migrated by the installed component."""

    def __init__(self, schema_id: str, source_version: int, target_version: int, message: str | None = None) -> None:
        self.schema_id = schema_id
        self.source_version = source_version
        self.target_version = target_version
        super().__init__(message or f"persisted schema {schema_id}/{source_version} is incompatible with target {target_version}")

from eu.algites.frmw.aac.core.errors import AIxAACError

from .aix_core_implementation_error import AIxCoreImplementationError

class AIxSchemaValidationError(AIxCoreImplementationError):
    def __init__(self, schema_name: str, diagnostics: tuple[str, ...]):
        self.schema_name = schema_name
        self.diagnostics = diagnostics
        super().__init__(f"schema validation failed for {schema_name!r}: " + "; ".join(diagnostics))

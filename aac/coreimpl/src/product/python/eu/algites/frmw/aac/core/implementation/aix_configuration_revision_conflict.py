from eu.algites.frmw.aac.core.errors import AIxAACError

from .aix_configuration_conflict_error import AIxConfigurationConflictError

class AIxConfigurationRevisionConflict(AIxConfigurationConflictError):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
        super().__init__(f"configuration revision conflict: expected {expected!r}, actual {actual!r}")

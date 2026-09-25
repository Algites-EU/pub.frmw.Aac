from eu.algites.frmw.aac.core.errors import AIxAACError

from .aix_persistence_error import AIxPersistenceError

class AIxPersistenceRevisionConflict(AIxPersistenceError):
    def __init__(self, record_id: str, expected, actual):
        self.record_id = record_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"persistence revision conflict for {record_id!r}: expected {expected!r}, actual {actual!r}"
        )

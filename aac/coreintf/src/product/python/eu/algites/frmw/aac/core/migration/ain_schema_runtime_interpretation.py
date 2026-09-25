from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from ..descriptor.api import AIcSchemaMigrationStepDescriptor

class AInSchemaRuntimeInterpretation(str, Enum):
    """How an active component can consume one persisted schema representation.

    Runtime interpretation is deliberately independent from whether the stored representation is
    already the component's preferred write version and from whether a persistence-convergence
    migration happens to exist.
    """

    DIRECT = "DIRECT"
    TRANSFORMED = "TRANSFORMED"
    UNSUPPORTED = "UNSUPPORTED"

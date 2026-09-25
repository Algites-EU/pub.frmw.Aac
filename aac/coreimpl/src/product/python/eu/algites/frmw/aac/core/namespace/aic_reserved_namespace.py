from __future__ import annotations
from dataclasses import dataclass
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.implementation.errors import AIxCoreImplementationError

@dataclass(frozen=True, slots=True)
class AIcReservedNamespace:
    prefix: str

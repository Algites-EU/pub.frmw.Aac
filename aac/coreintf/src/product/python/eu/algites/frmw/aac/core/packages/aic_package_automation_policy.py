from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageAutomationPolicy:
    verify_on_download: bool = True
    require_entitlement_for_automatic_paid_component: bool = True
    allow_automatic_download: bool = True
    allow_automatic_install: bool = True

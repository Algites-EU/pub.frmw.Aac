from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_reconciliation_action import AIcPackageReconciliationAction
from .ain_package_update_policy import AInPackageUpdatePolicy

@dataclass(frozen=True, slots=True)
class AIcPackageReconciliationPlan:
    workspace_id: str
    policy: AInPackageUpdatePolicy
    actions: tuple[AIcPackageReconciliationAction, ...]

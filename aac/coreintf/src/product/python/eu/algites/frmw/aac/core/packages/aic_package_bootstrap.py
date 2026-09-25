from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_automation_policy import AIcPackageAutomationPolicy
from .aic_package_source_registration import AIcPackageSourceRegistration
from .aic_package_store_layout import AIcPackageStoreLayout

@dataclass(frozen=True, slots=True)
class AIcPackageBootstrap:
    schema_version: int
    layout: AIcPackageStoreLayout
    sources: tuple[AIcPackageSourceRegistration, ...] = ()
    automation_policy: AIcPackageAutomationPolicy = AIcPackageAutomationPolicy()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("package bootstrap schema_version must be >= 1")
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("package source registration ids must be unique")

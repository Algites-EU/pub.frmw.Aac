from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Mapping
from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogEntry,
    AIcCatalogPersistentSchema,
    AIcCatalogQuery,
    AInCatalogPersistentSchemaKind,
)
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor,
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderImplementationClassDescriptor,
)
from eu.algites.frmw.aac.core.packages.api import (
    AInStoredPackageState,
    AIcStoredPackage,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentRequirements,
)
from eu.algites.frmw.aac.core.readiness.api import AInReadinessState
from eu.algites.frmw.aac.core.solver.api import (
    AInTargetStateChangeDirection,
    AInTargetStateRequestMode,
    AIcSolverEntitlementDiagnostic,
    AIcSolverExplanation,
    AIcSolverReadinessDiagnostic,
    AIcTargetStateRequest,
    AIcTargetStateSelection,
    AIcTargetStateSolution,
    AIcTargetStateSolverResult,
)

from .aic_solver_requirement import AIcSolverRequirement

@dataclass(frozen=True, slots=True)
class AIcSolverCandidate:
    component_id: str
    version: int
    provides: tuple[tuple[str, tuple[int, ...]], ...]
    requires: tuple[AIcSolverRequirement, ...]
    persistent_schemas: tuple[AIcCatalogPersistentSchema, ...]
    entitlements: tuple[AIcCapabilityEntitlementDescriptor, ...]
    entitlement_licensing_scopes: tuple[AIcEntitlementLicensingScopeDescriptor, ...] = ()
    descriptor: AIcComponentDescriptor | None = None
    stored_package: AIcStoredPackage | None = None
    catalog_entry: AIcCatalogEntry | None = None
    catalog_artifact_id: str | None = None

    @property
    def source_id(self) -> str | None:
        if self.catalog_entry is not None:
            return self.catalog_entry.source_id
        if self.stored_package is not None:
            return self.stored_package.provenance.source_id
        return None

    @property
    def local_state(self) -> AInStoredPackageState | None:
        return None if self.stored_package is None else self.stored_package.state

    @property
    def entropy_key(self) -> tuple:
        return self.component_id, self.version, self.source_id or "", self.catalog_artifact_id or ""

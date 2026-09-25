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
from .aic_solver_candidate import AIcSolverCandidate
from .aic_compatible_target_state_solver import AIcCompatibleTargetStateSolver

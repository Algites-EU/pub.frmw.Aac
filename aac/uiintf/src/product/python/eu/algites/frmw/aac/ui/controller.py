from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping
from eu.algites.frmw.aac.core.solver.api import AIcTargetStateSolution, AIcTargetStateSolverResult
from .models import (
    AIcUiBinding,
    AIcUiComponent,
    AIcUiForm,
    AIcUiObservationBinding,
    AIcUiProviderInstance,
    AIcUiRequirement,
    AIcUiRequirementEditor,
    AIcUiEntitlementStatus,
    AIcUiCatalogPackageArtifact,
    AIcUiPackageArtifact,
    AIcUiUpgradePlan,
)

from .aii_aac_ui_controller import AIiAacUiController

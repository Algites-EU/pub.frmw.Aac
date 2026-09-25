from __future__ import annotations
from dataclasses import dataclass, replace
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationTargetKind,
    AIcConfigurationPersistedPayload,
    AIcConfigurationProviderRequest,
    AIcConfigurationTarget,
)
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.migration.api import AInSchemaRuntimeInterpretation
from eu.algites.frmw.aac.core.persistence.api import AInPersistenceCapability
from eu.algites.frmw.aac.core.readiness.api import AInReadinessState
from eu.algites.frmw.aac.core.packages.api import (
    AIcComponentUpgradePlan,
    AIcComponentUpgradeReplacement,
    AIcUpgradeCompatibilityDiagnostic,
)
from eu.algites.frmw.aac.core.configuration.runtime import AIcConfigurationReadService, AIcConfigurationResolver
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.descriptor.loader import AIcDiscoveredComponent, iter_discovered_resources, read_discovered_resource
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingResolutionError
from eu.algites.frmw.aac.core.resolution.bindings import AIcBindingResolver, validate_instance_dag
from eu.algites.frmw.aac.core.readiness.evaluator import AIcReadinessEvaluator
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

@dataclass(frozen=True, slots=True)
class AIcPersistenceConvergenceOutcome:
    """Best-effort persistence convergence performed outside the component transaction."""

    configuration_persisted: int = 0
    configuration_deferred: int = 0
    diagnostics: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.configuration_deferred == 0

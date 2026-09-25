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

from .aic_target_state_upgrade_analyzer import AIcTargetStateUpgradeAnalyzer
from .aic_staged_configuration_migration import AIcStagedConfigurationMigration
from .aic_upgrade_migration_stage import AIcUpgradeMigrationStage
from .aic_persistence_convergence_outcome import AIcPersistenceConvergenceOutcome
from .aic_upgrade_migration_coordinator import AIcUpgradeMigrationCoordinator

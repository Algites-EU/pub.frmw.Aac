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
class AIcStagedConfigurationMigration:
    """Validated in-memory migration candidate discovered during target-state preflight.

    The object is *not* a transaction write-set.  It records enough information for an
    independent post-upgrade convergence attempt.  Component cutover never depends on that
    persistence attempt succeeding.
    """

    component_id: str
    configuration_provider_id: str
    request: AIcConfigurationProviderRequest
    source_revision: str | int | None
    source_payload: AIcConfigurationPersistedPayload
    target_payload: AIcConfigurationPersistedPayload

from __future__ import annotations
from dataclasses import dataclass, replace
import importlib
import sys
from pathlib import Path
from eu.algites.frmw.aac.core.authentication.api import AIcSecurityBootstrap, AIiAuthenticationHandler, AIiSecretProvider
from eu.algites.frmw.aac.core.authorization.api import AIcAuthorizationPrincipal, AIcComponentAuthorizationGrant, AIiAuthorizationProvider
from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogBootstrap, AIcCatalogEntry, AIcCatalogQuery, AIiCatalogProvider, AInCatalogPersistentSchemaKind,
)
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationMutationOperation, AInConfigurationTargetKind, AIcConfigurationBootstrap, AIcConfigurationChangeSet, AIcConfigurationProviderRequest, AIcConfigurationTarget,
    AIcEffectiveConfiguration, AIiConfigurationProvider, AIiConfigurationScopeResolver,
)
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementBootstrap, AIcEntitlementProviderBinding, AIcResolvedEntitlementLicensingScope,
    AIcTrustedEntitlementIssuerRule, AIiEntitlementEvidenceVerifier, AIiEntitlementProvider,
    AIiEntitlementRemediator, AIiEntitlementLicensingScopeResolver,
)
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.dataentity.api import AIcDataEntityEnvelope, AIcDataEntityImplementationBinding, AIcDataEntityViewBinding
from eu.algites.frmw.aac.core.migration.api import AInSchemaRuntimeInterpretation
from eu.algites.frmw.aac.core.errors import AIxPersistedSchemaIncompatible
from eu.algites.frmw.aac.core.instances.api import AIcBindingPreference, AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.observation.api import AIcObservationBinding
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.readiness.api import AIcProviderReadiness, AIcComponentReadiness, AIcCapabilityReadiness
from eu.algites.frmw.aac.core.packages.api import (
    AInStoredPackageState, AIcPackageAutomationPolicy, AIcPackageBootstrap, AIcPackageCandidate, AIcPackageReconciliationPlan,
    AIcPackageStoreLayout, AIcStoredPackage, AIcWorkspaceComponentLock, AIcWorkspaceComponentRequirements, AIcPackageSidecar,
    AIcComponentUpgradePlan, AIcComponentUpgradeTransactionOutcome, AIcComponentUpgradeReplacement,
)
from eu.algites.frmw.aac.core.solver.api import (
    AIcTargetStateRequest, AIcTargetStateSolution, AIcTargetStateSolverResult,
)
from eu.algites.frmw.aac.core.verification.api import AIiPackageVerifier, AIcVerificationInput
from eu.algites.frmw.aac.core.descriptor.api import AInComponentOrigin
from eu.algites.frmw.aac.core.capability.api import AInCapabilityOperationInteractionKind
from eu.algites.frmw.aac.core.interaction_types import AInStateResultDeliveryMode
from eu.algites.frmw.aac.core.bootstrap.loaders import AIcBootstrapResourceLoader, AIcConfigurationProfileLoader
from eu.algites.frmw.aac.core.bindings.store import AIcBindingPreferenceStore, AIcBindingStore
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader, AIcDiscoveredComponent, iter_discovered_resources, read_discovered_resource
from eu.algites.frmw.aac.core.dataentity.runtime import (
    AIcDataEntityImplementationRegistry, AIcDataEntityMarshaller, AIcDataEntityProviderFacade,
    AIcDataEntityViewRegistry,
)
from eu.algites.frmw.aac.core.catalog.loading import AIcCatalogProviderRegistry, AIcFilesystemCatalogProvider, AIcHttpCatalogProvider
from eu.algites.frmw.aac.core.configuration.runtime import (
    AIcAllowOwnNamespaceConfigurationMutationAuthorizer, AIcConfigurationContextResolver,
    AIcConfigurationMutationService, AIcConfigurationProviderRegistry, AIcConfigurationReadService, AIcConfigurationResolver,
    AIcConfigurationScopeResolverRegistry, AIcStaticConfigurationScopeResolver,
)
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService, AIcEnvironmentSecretProvider, AIcFileSecretProvider
from eu.algites.frmw.aac.core.authorization.implementation import AIcComponentAuthorizationGrantStore
from eu.algites.frmw.aac.core.configuration.providers import AIcFileSystemConfigurationProvider, AIcHttpConfigurationProvider
from eu.algites.frmw.aac.core.entitlement.runtime import (
    AIcEntitlementContextResolver, AIcEntitlementManager, AIcEntitlementProviderRegistry,
    AIcEntitlementEvidenceVerifierRegistry, AIcEntitlementLicensingScopeResolverRegistry, AIcStaticEntitlementLicensingScopeResolver,
)
from eu.algites.frmw.aac.core.implementation.errors import AIxSchemaValidationError, AIxUpgradeError, AIxVerificationError
from eu.algites.frmw.aac.core.entitlement.providers import AIcFileEntitlementProvider
from eu.algites.frmw.aac.core.entitlement.trust import AIcTrustedEntitlementIssuerRegistry
from eu.algites.frmw.aac.core.entitlement.refresh import AIcEntitlementRefreshPlanner
from eu.algites.frmw.aac.core.entitlement.requests import AIcEntitlementIssuingRequestService
from eu.algites.frmw.aac.core.graph.orchestrator import AIcApplicationGraphOrchestrator, AIcResolvedApplicationGraph
from eu.algites.frmw.aac.core.instances.registry import AIcProviderInstanceRegistry
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcCapabilityHandleFactory, AIcEndpointRegistry, AIcInvocationDispatcher, authorization_principal_context
from eu.algites.frmw.aac.core.lifecycle.engine import AIcLifecycleEngine
from eu.algites.frmw.aac.core.migration.service import AIcConfigurationMigrationService, AIcDataEntityMigrationService
from eu.algites.frmw.aac.core.namespace.policy import AIcNamespacePolicy
from eu.algites.frmw.aac.core.observation.dispatcher import AIcObservationDispatcher, AIcObservationTopologyStore
from eu.algites.frmw.aac.core.operation_parameters.resolver import AIcOperationParameterConfigurationStore, AIcOperationParameterResolver
from eu.algites.frmw.aac.core.packages.store import AIcManifestPackageSource, AIcPackageManager
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.provisioning.engine import AIcProvisioningEngine
from eu.algites.frmw.aac.core.resolution.bindings import AIcBindingResolver
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry
from eu.algites.frmw.aac.core.solver.engine import AIcCompatibleTargetStateSolver
from eu.algites.frmw.aac.core.verification.python_package import AIcPythonPackageVerifier
from eu.algites.frmw.aac.core.upgrade.service import AIcTargetStateUpgradeAnalyzer, AIcUpgradeMigrationCoordinator

@dataclass(frozen=True, slots=True)
class AIcPythonCandidateImportSnapshot:
    sys_path: tuple[str, ...]
    modules: dict[str, object]
    package_prefixes: tuple[str, ...]

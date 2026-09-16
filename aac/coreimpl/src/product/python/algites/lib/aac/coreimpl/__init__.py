"""Reusable Python implementation of Algites Application Components."""

from .bindings import AIcBindingStore
from .bootstrap import AIcConfigurationBootstrapLoader, AIcEntitlementBootstrapLoader, AIcSecurityBootstrapLoader
from .authentication import (
    AIcAuthenticationService, AIcEnvironmentSecretProvider, AIcFileSecretProvider, AIcSecretProviderRegistry,
)
from .configuration import (
    AIcAllowOwnNamespaceConfigurationMutationAuthorizer,
    AIcConfigurationContextResolver,
    AIcConfigurationMutationService,
    AIcConfigurationProviderRegistry,
    AIcConfigurationReadService,
    AIcConfigurationResolver,
    AIcConfigurationScopeResolverRegistry,
    AIcStaticConfigurationProvider,
    AIcStaticConfigurationScopeResolver,
)
from .configuration_providers import AIcConfigurationDocumentCodec, AIcFileSystemConfigurationProvider, AIcHttpConfigurationProvider
from .contracts import AIcActiveContractCatalog, AIcAdmittedContract
from .codegen import AIcPythonCapabilityBindingGenerator
from .core import AIcApplicationComponentCore, AIcInstalledComponent, AIcUpgradeOutcome
from .descriptor import AIcDescriptorLoader, AIcDiscoveredComponent
from .entitlement_documents import AIcEntitlementDocumentLoader, AIcEntitlementIssuingRequestLoader, entitlement_request_digest
from .entitlement_providers import AIcFileEntitlementProvider
from .entitlement_requests import AIcEntitlementIssuingRequestService
from .entitlement_refresh import AIcEntitlementRefreshPlanner
from .entitlement_trust import AIcTrustedEntitlementIssuerRegistry
from .entitlement import (
    AIcEntitlementContextResolver,
    AIcEntitlementEvidenceVerifierRegistry,
    AIcEntitlementManager,
    AIcEntitlementProviderRegistry,
    AIcEntitlementLicensingScopeResolverRegistry,
    AIcStaticEntitlementProvider,
    AIcStaticEntitlementLicensingScopeResolver,
    AIcTrustedBootstrapEntitlementEvidenceVerifier,
)
from .extensions import AIcInMemoryEntityExtensionDataStore
from .instances import AIcProviderInstanceRegistry
from .invocation import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
from .lifecycle import AIcActivationOutcome, AIcLifecycleEngine
from .migration import AIcConfigurationMigrationService, AIcEntityExtensionMigrationService, AIcSchemaCompatibilityEvaluator
from .observation import AIcObservationBinding, AIcObservationDelivery, AIcObservationDispatcher, AIcObservationSelector
from .package_documents import AIcPackageBootstrapLoader, AIcWorkspaceComponentLockLoader, AIcWorkspaceComponentRequirementsLoader
from .packages import (
    AIcManifestPackageSource, AIcPackageManager, AIcPackageSelectionStore, AIcPackageSourceRegistry,
    AIcPackageStore, AIcPackageVerifierRegistry, AIcStaticPackageSource,
)
from .persistence import AIcInMemoryStateStore, AIcJsonFileStateStore
from .process import AIcJsonLineProcessEndpoint
from .subinterpreter import AIcSubinterpreterCapabilityEndpoint, subinterpreter_available
from .provisioning import AIcProvisioningEngine
from .resolution import AIcBindingResolver, validate_instance_dag
from .schemas import AIcSchemaRegistry
from .solver import AIcCompatibleTargetStateSolver

__all__ = [name for name in globals() if name.startswith(("AIi", "AIc", "AIn", "AIx", "subinterpreter", "validate"))]

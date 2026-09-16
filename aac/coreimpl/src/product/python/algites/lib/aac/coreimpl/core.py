from __future__ import annotations

from dataclasses import dataclass, replace
import importlib
import sys
from pathlib import Path

from algites.lib.aac.coreintf.authentication import AIcSecurityBootstrap, AIiAuthenticationHandler, AIiSecretProvider
from algites.lib.aac.coreintf.authorization import AIcAuthorizationPrincipal, AIcComponentAuthorizationGrant, AIiAuthorizationProvider
from algites.lib.aac.coreintf.catalog import (
    AIcCatalogBootstrap, AIcCatalogEntry, AIcCatalogQuery, AIiCatalogProvider, AInCatalogPersistentSchemaKind,
)
from algites.lib.aac.coreintf.configuration import (
    AInConfigurationMutationOperation, AInConfigurationTargetKind, AIcConfigurationBootstrap, AIcConfigurationChangeSet, AIcConfigurationProviderRequest, AIcConfigurationTarget,
    AIcEffectiveConfiguration, AIiConfigurationProvider, AIiConfigurationScopeResolver,
)
from algites.lib.aac.coreintf.entitlement import (
    AIcEntitlementBootstrap, AIcEntitlementProviderBinding, AIcResolvedEntitlementLicensingScope,
    AIcTrustedEntitlementIssuerRule, AIiEntitlementEvidenceVerifier, AIiEntitlementProvider,
    AIiEntitlementRemediator, AIiEntitlementLicensingScopeResolver,
)
from algites.lib.aac.coreintf.entitlement import AIcEntitlementLicensingScope
from algites.lib.aac.coreintf.extensions import AIcCoreEntityContext, AIiEntityExtensionDataStore
from algites.lib.aac.coreintf.migration import AInSchemaRuntimeInterpretation
from algites.lib.aac.coreintf.errors import AIxPersistedSchemaIncompatible, AIxPersistedPayloadMigrationError
from algites.lib.aac.coreintf.instances import AIcBindingPreference, AIcProviderInstance, AInProviderInstanceState
from algites.lib.aac.coreintf.observation import AIcObservationBinding
from algites.lib.aac.coreintf.persistence import AIiStateStore
from algites.lib.aac.coreintf.readiness import AIcProviderReadiness, AIcComponentReadiness, AIcCapabilityReadiness
from algites.lib.aac.coreintf.packages import (
    AInStoredPackageState, AIcPackageAutomationPolicy, AIcPackageBootstrap, AIcPackageCandidate, AIcPackageReconciliationPlan,
    AIcPackageStoreLayout, AIcStoredPackage, AIcWorkspaceComponentLock, AIcWorkspaceComponentRequirements, AIcPackageSidecar,
    AIcComponentUpgradePlan, AIcComponentUpgradeTransactionOutcome, AIcComponentUpgradeReplacement,
)

from algites.lib.aac.coreintf.solver import (
    AIcTargetStateRequest, AIcTargetStateSolution, AIcTargetStateSolverResult,
)
from algites.lib.aac.coreintf.verification import AIiPackageVerifier, AIcVerificationInput
from algites.lib.aac.coreintf.descriptor import AInComponentOrigin

from .bootstrap import AIcBootstrapResourceLoader, AIcConfigurationProfileLoader
from .bindings import AIcBindingPreferenceStore, AIcBindingStore
from .contracts import AIcActiveContractCatalog
from .descriptor import AIcDescriptorLoader, AIcDiscoveredComponent, iter_discovered_resources, read_discovered_resource
from .catalog import AIcCatalogProviderRegistry, AIcFilesystemCatalogProvider, AIcHttpCatalogProvider
from .configuration import (
    AIcAllowOwnNamespaceConfigurationMutationAuthorizer, AIcConfigurationContextResolver,
    AIcConfigurationMutationService, AIcConfigurationProviderRegistry, AIcConfigurationReadService, AIcConfigurationResolver,
    AIcConfigurationScopeResolverRegistry, AIcStaticConfigurationScopeResolver,
)
from .authentication import AIcAuthenticationService, AIcEnvironmentSecretProvider, AIcFileSecretProvider
from .authorization import AIcComponentAuthorizationGrantStore
from .configuration_providers import AIcFileSystemConfigurationProvider, AIcHttpConfigurationProvider
from .entitlement import (
    AIcEntitlementContextResolver, AIcEntitlementManager, AIcEntitlementProviderRegistry,
    AIcEntitlementEvidenceVerifierRegistry, AIcEntitlementLicensingScopeResolverRegistry, AIcStaticEntitlementLicensingScopeResolver,
)
from .errors import AIxSchemaValidationError, AIxUpgradeError, AIxVerificationError
from .entitlement_providers import AIcFileEntitlementProvider
from .entitlement_trust import AIcTrustedEntitlementIssuerRegistry
from .entitlement_refresh import AIcEntitlementRefreshPlanner
from .entitlement_requests import AIcEntitlementIssuingRequestService
from .graph import AIcApplicationGraphOrchestrator, AIcResolvedApplicationGraph
from .instances import AIcProviderInstanceRegistry
from .invocation import AIcCapabilityHandleFactory, AIcEndpointRegistry, AIcInvocationDispatcher, authorization_principal_context
from .lifecycle import AIcLifecycleEngine
from .migration import AIcConfigurationMigrationService, AIcEntityExtensionMigrationService
from .namespace import AIcNamespacePolicy
from .observation import AIcObservationDispatcher, AIcObservationTopologyStore
from .packages import AIcManifestPackageSource, AIcPackageManager
from .persistence import AIcInMemoryStateStore
from .provisioning import AIcProvisioningEngine
from .resolution import AIcBindingResolver
from .schemas import AIcSchemaRegistry
from .solver import AIcCompatibleTargetStateSolver
from .verification import AIcPythonPackageVerifier
from .upgrade import AIcTargetStateUpgradeAnalyzer, AIcUpgradeMigrationCoordinator


@dataclass(frozen=True, slots=True)
class AIcInstalledComponent:
    discovered: AIcDiscoveredComponent
    origin: AInComponentOrigin = AInComponentOrigin.PACKAGE

    @property
    def descriptor(self):
        return self.discovered.descriptor


@dataclass(frozen=True, slots=True)
class AIcUpgradeOutcome:
    component_id: str
    previous_version: int
    current_version: int
    graph: AIcResolvedApplicationGraph


@dataclass(frozen=True, slots=True)
class AIcPythonCandidateImportSnapshot:
    sys_path: tuple[str, ...]
    modules: dict[str, object]
    package_prefixes: tuple[str, ...]


class AIcApplicationComponentCore:
    """Reusable AAC composition root for the Python technology profile."""

    def __init__(
        self,
        *,
        store: AIiStateStore | None = None,
        entitlement_provider: AIiEntitlementProvider | None = None,
        entitlement_licensing_scope: AIcEntitlementLicensingScope | None = None,
        entitlement_remediator: AIiEntitlementRemediator | None = None,
        authorization_provider: AIiAuthorizationProvider | None = None,
        verifier: AIiPackageVerifier | None = None,
    ) -> None:
        self.store = store or AIcInMemoryStateStore()
        self.schemas = AIcSchemaRegistry()
        self.contracts = AIcActiveContractCatalog(self.schemas)
        self.contracts.admit_builtin_contracts()
        self.authentication = AIcAuthenticationService()
        self.security_bootstrap: AIcSecurityBootstrap | None = None
        self._bootstrap_safe_secret_provider_ids: set[str] = set()

        self.configuration_providers = AIcConfigurationProviderRegistry()
        self.configuration_scope_resolvers = AIcConfigurationScopeResolverRegistry()
        self.configuration_scope_resolvers.register("_AAC.context.mapping", AIcStaticConfigurationScopeResolver())
        self.configuration_context_resolver = AIcConfigurationContextResolver(self.configuration_scope_resolvers)
        self.configuration_migrations = AIcConfigurationMigrationService()
        self.entity_extension_migrations = AIcEntityExtensionMigrationService()
        self.configuration_reads = AIcConfigurationReadService(
            self.configuration_providers, self.configuration_migrations, self._configuration_schema_for_target, self.schemas
        )
        self.configuration_resolver = AIcConfigurationResolver(self.configuration_providers, self.configuration_reads)
        self.configuration_mutations = AIcConfigurationMutationService(
            self.configuration_providers, AIcAllowOwnNamespaceConfigurationMutationAuthorizer()
        )
        self.configuration_bootstrap: AIcConfigurationBootstrap | None = None
        self.active_configuration_scopes = ()
        self.application_context: dict[str, object] = {}
        self.entity_extension_store: AIiEntityExtensionDataStore | None = None
        self._entity_contexts: dict[tuple[str, str], AIcCoreEntityContext] = {}

        self.entitlement_requests = AIcEntitlementIssuingRequestService()
        self.entitlement_providers = AIcEntitlementProviderRegistry()
        self.entitlement_verifiers = AIcEntitlementEvidenceVerifierRegistry()
        self.trusted_entitlement_issuers = AIcTrustedEntitlementIssuerRegistry()
        self.licensing_scope_resolvers = AIcEntitlementLicensingScopeResolverRegistry()
        self.licensing_scope_resolvers.register("_AAC.context.mapping", AIcStaticEntitlementLicensingScopeResolver())
        self.entitlement_context_resolver = AIcEntitlementContextResolver(self.licensing_scope_resolvers)
        self.entitlement = AIcEntitlementManager(
            self.entitlement_providers, self.entitlement_verifiers, self.trusted_entitlement_issuers,
            self.entitlement_requests.validate_returned_entitlement,
        )
        self.entitlement_remediator = entitlement_remediator
        self.entitlement_bootstrap: AIcEntitlementBootstrap | None = None
        self.active_licensing_scopes: tuple[AIcResolvedEntitlementLicensingScope, ...] = ()
        if entitlement_provider is not None:
            if entitlement_licensing_scope is None:
                raise ValueError(
                    "entitlement_licensing_scope is required when entitlement_provider is supplied; "
                    "AAC does not assume a built-in licensing-scope type"
                )
            self.entitlement_providers.register("_AAC.constructor.entitlement-provider", entitlement_provider)
            self.active_licensing_scopes = (AIcResolvedEntitlementLicensingScope(
                "constructor-entitlement", entitlement_licensing_scope,
                (AIcEntitlementProviderBinding("_AAC.constructor.entitlement-provider"),),
            ),)
        self.authorization_provider = authorization_provider
        self._active_application_scope_ids: set[str] = set()
        self._builtin_component_ids: set[str] = set()
        self.verifier = verifier or AIcPythonPackageVerifier()
        self.namespaces = AIcNamespacePolicy()
        self._installed: dict[str, AIcInstalledComponent] = {}
        self.catalogs = AIcCatalogProviderRegistry()
        self.catalog_bootstrap: AIcCatalogBootstrap | None = None
        self.catalog_product_id: str | None = None
        self.catalog_technology_id: str | None = None
        self.package_bootstrap: AIcPackageBootstrap | None = None
        self.package_manager: AIcPackageManager | None = None
        self._rebuild_runtime_services()

    def _rebuild_runtime_services(self) -> None:
        self.instances = AIcProviderInstanceRegistry(self.store)
        self.bindings = AIcBindingStore(self.store)
        self.preferences = AIcBindingPreferenceStore(self.store)
        self.provisioning = AIcProvisioningEngine(
            self.instances, schema_registry=self.schemas, store=self.store, binding_store=self.bindings
        )
        self.resolver = AIcBindingResolver(self.contracts)
        self.graph = AIcApplicationGraphOrchestrator(self.instances, self.resolver, self.bindings, self.preferences)
        self.observation_topology = AIcObservationTopologyStore(self.store, self.contracts)
        self.observations = AIcObservationDispatcher(self.observation_topology)
        self.component_authorizations = AIcComponentAuthorizationGrantStore(self.store)
        self.endpoints = AIcEndpointRegistry()
        self.invocations = AIcInvocationDispatcher(
            self.contracts, self.observations, self.component_authorizations, self.authorization_provider,
            entitlement_remediator=self.entitlement_remediator, entitlement_refresh_callback=self._refresh_entitlements_after_remediation,
        )
        self.handles = AIcCapabilityHandleFactory(self.endpoints, self.invocations)
        self.lifecycle = AIcLifecycleEngine(
            contract_catalog=self.contracts,
            provisioning=self.provisioning,
            entitlement=self.entitlement,
            store=self.store,
            endpoints=self.endpoints,
            handles=self.handles,
            observations=self.observations,
            verifier=self.verifier,
        )
        self.lifecycle.licensing_scopes = self.active_licensing_scopes
        self.lifecycle.entitlement_context = dict(self.application_context)


    def active_application_scope_ids(self) -> tuple[str, ...]:
        """Return currently active application-scope identifiers in deterministic order."""
        return tuple(sorted(self._active_application_scope_ids))

    def provider_readiness(self, application_scope_id: str, provider_instance_id: str) -> AIcProviderReadiness | None:
        return self.lifecycle.provider_readiness(application_scope_id, provider_instance_id)

    def component_readiness(self, application_scope_id: str, component_id: str) -> AIcComponentReadiness:
        return self.lifecycle.component_readiness(application_scope_id, component_id)

    def capability_readiness(self, application_scope_id: str) -> tuple[AIcCapabilityReadiness, ...]:
        return self.lifecycle.capability_readiness(application_scope_id)

    def refresh_provider_readiness(self, application_scope_id: str, provider_instance_id: str) -> AIcProviderReadiness:
        instance = self.instances.get(provider_instance_id)
        descriptor = self.installed(instance.component_id).descriptor
        return self.lifecycle.refresh_instance_readiness(
            application_scope_id, descriptor, provider_instance_id,
            component_configuration=self.resolve_component_scoped_configuration(instance.component_id),
            provider_configuration=self.resolve_provider_scoped_configuration(provider_instance_id),
        )

    def refresh_component_readiness(self, application_scope_id: str, component_id: str) -> AIcComponentReadiness:
        for instance in self.instances.find(component_id=component_id):
            if self.lifecycle.provider_readiness(application_scope_id, instance.id) is not None:
                self.refresh_provider_readiness(application_scope_id, instance.id)
        return self.component_readiness(application_scope_id, component_id)

    def register_catalog_provider(self, source_id: str, provider: AIiCatalogProvider, *, priority: int = 0) -> None:
        self.catalogs.register(source_id, provider, priority=priority)

    def apply_catalog_bootstrap(self, bootstrap: AIcCatalogBootstrap) -> None:
        self.catalog_bootstrap = bootstrap
        self.catalog_product_id = bootstrap.product_id
        self.catalog_technology_id = bootstrap.technology_id
        # Bootstrap application replaces the current source registry so a changed product profile
        # cannot accidentally retain catalog sources from an earlier scope.
        self.catalogs = AIcCatalogProviderRegistry()
        for source in bootstrap.sources:
            if source.authentication_profile_id is not None and not self.authentication.profiles.contains(source.authentication_profile_id):
                raise ValueError(
                    f"catalog source {source.id!r} references unknown authentication profile {source.authentication_profile_id!r}"
                )
            kind = source.type.upper()
            kwargs = dict(
                authentication=self.authentication,
                authentication_profile_id=source.authentication_profile_id,
                timeout_seconds=float(source.settings.get("timeout_seconds", 30.0)),
                context=self.application_context,
            )
            if kind in {"FILE", "FILESYSTEM"}:
                provider = AIcFilesystemCatalogProvider(source.id, source.uri, **kwargs)
            elif kind in {"HTTP", "HTTPS"}:
                provider = AIcHttpCatalogProvider(source.id, source.uri, **kwargs)
            else:
                raise ValueError(f"no catalog-provider factory registered for type {source.type!r}")
            self.catalogs.register(source.id, provider, priority=source.priority)

    def query_catalog(self, query: AIcCatalogQuery) -> tuple[AIcCatalogEntry, ...]:
        return self.catalogs.query(query)

    def query_default_catalog(
        self, *, component_id: str | None = None, text: str | None = None,
        provides_capability_id: str | None = None, requires_capability_id: str | None = None,
    ) -> tuple[AIcCatalogEntry, ...]:
        if self.catalog_product_id is None or self.catalog_technology_id is None:
            raise RuntimeError("AAC catalog scope is not configured")
        return self.query_catalog(AIcCatalogQuery(
            self.catalog_product_id, self.catalog_technology_id, component_id=component_id, text=text,
            provides_capability_id=provides_capability_id, requires_capability_id=requires_capability_id,
        ))

    def _catalog_entry(
        self, source_id: str, product_id: str, technology_id: str, component_id: str, component_version: int
    ) -> AIcCatalogEntry:
        matches = self.catalogs.get(source_id).query(AIcCatalogQuery(
            product_id, technology_id, component_id=component_id, versions=(component_version,)
        ))
        for entry in matches:
            if entry.source_id == source_id and entry.component_id == component_id and entry.component_version == component_version:
                return entry
        raise KeyError((source_id, product_id, technology_id, component_id, component_version))

    @staticmethod
    def _catalog_artifact(entry: AIcCatalogEntry, artifact_id: str):
        for artifact in entry.release.artifacts:
            if artifact.id == artifact_id:
                return artifact
        raise KeyError(artifact_id)

    @staticmethod
    def _verify_catalog_descriptor(entry: AIcCatalogEntry, descriptor) -> None:
        if descriptor.id != entry.component_id or descriptor.version != entry.component_version:
            raise ValueError("catalog release identity does not match component descriptor")
        catalog_provides = {
            (offer.capability_id, version) for offer in entry.release.provides for version in offer.versions
        }
        descriptor_provides = {
            (provider.capability_id, version) for provider in descriptor.providers for version in provider.capability_versions
        }
        if catalog_provides != descriptor_provides:
            raise ValueError("catalog provides metadata does not match component descriptor")
        catalog_requires = {
            (item.capability_id, tuple(item.versions), item.cardinality.value, item.mandatory)
            for item in entry.release.requires
        }
        descriptor_requires = {
            (item.capability_id, tuple(item.versions), item.cardinality.value, item.mandatory)
            for provider in descriptor.providers for item in provider.requirements
        }
        if catalog_requires != descriptor_requires:
            raise ValueError("catalog requires metadata does not match component descriptor")
        if entry.release.entitlement_licensing_scopes != descriptor.entitlement_licensing_scopes:
            raise ValueError("catalog entitlement licensing-scope metadata does not match component descriptor")
        catalog_entitlements = {
            (item.capability_id, item.capability_version, permission.id, tuple(permission.possible_licensing_scope_types))
            for item in entry.release.provided_capability_entitlements for permission in item.permissions
        }
        descriptor_entitlements = {
            (item.capability_id, item.capability_version, permission.id, tuple(permission.possible_licensing_scope_types))
            for item in descriptor.provided_capability_entitlements for permission in item.permissions
        }
        if catalog_entitlements != descriptor_entitlements:
            raise ValueError("catalog entitlement metadata does not match component descriptor")
        if entry.release.persistent_schemas:
            descriptor_schemas = []
            if descriptor.component_configuration_schema is not None:
                schema = descriptor.component_configuration_schema
                descriptor_schemas.append((AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION.value, None, schema.schema_id, schema.write_version))
            for provider in descriptor.providers:
                if provider.configuration_schema is not None:
                    schema = provider.configuration_schema
                    descriptor_schemas.append((AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION.value, provider.id, schema.schema_id, schema.write_version))
            for extension in descriptor.entity_extensions:
                schema = extension.extension_data.component_extension_schema
                if schema is not None:
                    descriptor_schemas.append((AInCatalogPersistentSchemaKind.ENTITY_EXTENSION.value, extension.entity_type_id, schema.schema_id, schema.write_version))
            catalog_schemas = [
                (*item.identity, item.schema_id, item.write_version)
                for item in entry.release.persistent_schemas
            ]
            if sorted(catalog_schemas) != sorted(descriptor_schemas):
                raise ValueError("catalog persistent-schema metadata does not match component descriptor")

    def catalog_package_candidate(
        self, source_id: str, product_id: str, technology_id: str, component_id: str, component_version: int, artifact_id: str
    ) -> AIcPackageCandidate:
        entry = self._catalog_entry(source_id, product_id, technology_id, component_id, component_version)
        artifact = self._catalog_artifact(entry, artifact_id)
        if artifact.locator.type.upper() != "URI" or not artifact.locator.uri:
            raise ValueError(
                f"catalog artifact {artifact.id!r} uses locator type {artifact.locator.type!r}; no repository adapter is registered"
            )
        return AIcPackageCandidate(
            component_id=entry.component_id,
            component_version=entry.component_version,
            source_id=entry.source_id,
            artifact_uri=artifact.locator.uri,
            artifact_filename=artifact.artifact_filename,
            package_format=artifact.package_format,
            descriptor_path=artifact.descriptor_path,
            expected_sha256=artifact.sha256,
            runtime_package=artifact.runtime_package,
            verifier_id=artifact.verifier_id,
            authentication_profile_id=artifact.authentication_profile_id,
            sidecars=artifact.sidecars,
            metadata={
                **dict(artifact.metadata),
                "catalog_product_id": product_id,
                "catalog_technology_id": technology_id,
                "catalog_artifact_id": artifact.id,
            },
            name=entry.component.name,
            description=entry.component.description,
        )

    def download_catalog_package(
        self, source_id: str, product_id: str, technology_id: str, component_id: str, component_version: int, artifact_id: str
    ) -> AIcStoredPackage:
        candidate = self.catalog_package_candidate(
            source_id, product_id, technology_id, component_id, component_version, artifact_id
        )
        downloaded = self.download_package(candidate)
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        descriptor = self.package_manager.descriptor_from_artifact(downloaded)
        self._verify_catalog_descriptor(
            self._catalog_entry(source_id, product_id, technology_id, component_id, component_version), descriptor
        )
        return downloaded

    def install_catalog_package(
        self, source_id: str, product_id: str, technology_id: str, component_id: str, component_version: int, artifact_id: str
    ) -> AIcStoredPackage:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        candidate = self.catalog_package_candidate(
            source_id, product_id, technology_id, component_id, component_version, artifact_id
        )
        downloaded = self.package_manager.package_store.find(
            component_id, component_version, candidate.expected_sha256 or "",
            state=AInStoredPackageState.DOWNLOADED,
        ) if candidate.expected_sha256 else None
        if downloaded is None:
            downloaded = self.download_catalog_package(
                source_id, product_id, technology_id, component_id, component_version, artifact_id
            )
        descriptor = self.package_manager.descriptor_from_artifact(downloaded)
        self._verify_catalog_descriptor(
            self._catalog_entry(source_id, product_id, technology_id, component_id, component_version), descriptor
        )
        return self.install_downloaded_package(candidate, downloaded)

    def configure_package_management(
        self, layout: AIcPackageStoreLayout, *, automation_policy: AIcPackageAutomationPolicy = AIcPackageAutomationPolicy()
    ) -> AIcPackageManager:
        self.package_manager = AIcPackageManager(
            layout, authentication=self.authentication, store=self.store, automation_policy=automation_policy
        )
        if (
            self.package_manager.transaction_recovery is not None
            and self.package_manager.transaction_recovery.action == "RESTORED_SOURCE_STATE"
        ):
            # Package-manager recovery may have restored the persisted Core snapshot after this Core
            # object was constructed.  Re-read all Core-owned registries from that restored store.
            self._rebuild_runtime_services()
        self.package_manager.register_verifier("_AAC.core.default", self.verifier)
        return self.package_manager

    def apply_package_bootstrap(self, bootstrap: AIcPackageBootstrap) -> None:
        self.package_bootstrap = bootstrap
        manager = self.configure_package_management(bootstrap.layout, automation_policy=bootstrap.automation_policy)
        for source in bootstrap.sources:
            if source.authentication_profile_id is not None and not self.authentication.profiles.contains(source.authentication_profile_id):
                raise ValueError(
                    f"package source {source.id!r} references unknown authentication profile {source.authentication_profile_id!r}"
                )
            kind = source.type.upper()
            if kind not in {"MANIFEST", "FILE_MANIFEST", "HTTP_MANIFEST", "HTTPS_MANIFEST"}:
                raise ValueError(f"no package-source factory registered for type {source.type!r}")
            manager.register_source(
                source.id,
                AIcManifestPackageSource(
                    source.id, source.uri, authentication=self.authentication,
                    authentication_profile_id=source.authentication_profile_id, verifier_id=source.verifier_id,
                    priority=source.priority, timeout_seconds=float(source.settings.get("timeout_seconds", 30.0)),
                    context=self.application_context,
                ),
                priority=source.priority,
            )

    def register_package_source(self, source_id: str, source, *, priority: int = 0) -> None:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        self.package_manager.register_source(source_id, source, priority=priority)

    def register_package_verifier(self, verifier_id: str, verifier: AIiPackageVerifier) -> None:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        self.package_manager.register_verifier(verifier_id, verifier)

    def plan_workspace_packages(
        self, requirements: AIcWorkspaceComponentRequirements, lock: AIcWorkspaceComponentLock | None = None
    ) -> AIcPackageReconciliationPlan:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.plan_workspace(requirements, lock)

    def download_package(self, candidate: AIcPackageCandidate) -> AIcStoredPackage:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.download(candidate, fallback_verifier=self.verifier, context=self.application_context)

    def install_downloaded_package(self, candidate: AIcPackageCandidate, downloaded: AIcStoredPackage) -> AIcStoredPackage:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.install(candidate, downloaded, fallback_verifier=self.verifier)

    def select_package(self, application_scope_id: str, package: AIcStoredPackage):
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.selections.select(application_scope_id, package)

    def rollback_package_selection(self, application_scope_id: str, component_id: str):
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.selections.rollback(application_scope_id, component_id, self.package_manager.package_store)

    def mark_package_obsolete(self, package: AIcStoredPackage) -> AIcStoredPackage:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.mark_obsolete(package)

    def restore_obsolete_package(self, package: AIcStoredPackage) -> AIcStoredPackage:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        return self.package_manager.restore_obsolete(package)

    def reconcile_workspace_packages(
        self, requirements: AIcWorkspaceComponentRequirements, lock: AIcWorkspaceComponentLock | None = None,
        *, application_scope_id: str | None = None, execute_automatic: bool = False,
    ) -> AIcPackageReconciliationPlan:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        plan = self.package_manager.plan_workspace(requirements, lock)
        if not execute_automatic:
            return plan
        scope_id = application_scope_id or requirements.workspace_id
        rewritten = []
        for action in plan.actions:
            if action.action != "AUTO_INSTALL" or action.candidate is None:
                rewritten.append(action)
                continue
            if not self.package_manager.automation_policy.allow_automatic_download or not self.package_manager.automation_policy.allow_automatic_install:
                rewritten.append(replace(action, action="AUTO_BLOCKED_POLICY", reason="automatic package actions disabled by product policy"))
                continue
            downloaded = self.download_package(action.candidate)
            descriptor = self.package_manager.descriptor_from_artifact(downloaded)
            if self.package_manager.automation_policy.require_entitlement_for_automatic_paid_component:
                context = self.entitlement.evaluate_component(
                    descriptor, licensing_scopes=self.active_licensing_scopes, context=self.application_context
                )
                effective = {
                    (capability.capability_id, capability.capability_version, permission_id)
                    for capability in context.capabilities for permission_id in capability.permissions
                }
                if not self.package_manager.automatic_entitlement_allows(descriptor, effective):
                    rewritten.append(replace(
                        action, action="AUTO_BLOCKED_ENTITLEMENT",
                        reason="component declares paid entitlement permissions and no implicit/effective entitlement allows automatic install",
                    ))
                    continue
            installed = self.install_downloaded_package(action.candidate, downloaded)
            self.select_package(scope_id, installed)
            rewritten.append(replace(action, action="AUTO_INSTALLED", reason=f"installed sha256:{installed.sha256}"))
        return AIcPackageReconciliationPlan(plan.workspace_id, plan.policy, tuple(rewritten))


    def solve_compatible_target_state(
        self, application_scope_id: str, requests: tuple[AIcTargetStateRequest, ...], *,
        workspace_requirements: AIcWorkspaceComponentRequirements | None = None,
        workspace_lock: AIcWorkspaceComponentLock | None = None,
        max_alternatives: int = 3,
    ) -> AIcTargetStateSolverResult:
        return AIcCompatibleTargetStateSolver(self).solve(
            application_scope_id, requests, workspace_requirements=workspace_requirements,
            workspace_lock=workspace_lock, max_alternatives=max_alternatives,
        )

    @staticmethod
    def _candidate_from_stored_package(package: AIcStoredPackage) -> AIcPackageCandidate:
        return AIcPackageCandidate(
            component_id=package.component_id, component_version=package.component_version,
            source_id=package.provenance.source_id, source_uri=package.provenance.source_uri,
            artifact_uri=package.provenance.artifact_uri, artifact_filename=Path(package.artifact_path).name,
            package_format=package.package_format, descriptor_path=package.descriptor_path,
            expected_sha256=package.sha256, runtime_package=package.runtime_package,
            verifier_id=package.provenance.verifier_id, sidecars=tuple(
                AIcPackageSidecar(uri=path, suffix=suffix) for suffix, path in package.sidecar_paths.items()
            ), metadata=dict(package.metadata),
        )

    def apply_target_state_solution(
        self, application_scope_id: str, solution: AIcTargetStateSolution, *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
    ) -> AIcComponentUpgradeTransactionOutcome:
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        targets: list[AIcStoredPackage] = []
        for selection in solution.changed:
            if selection.target_sha256 is None:
                raise AIxUpgradeError(f"solver target {selection.component_id}/{selection.target_version} has no artifact digest")
            package = self.package_manager.package_store.find(
                selection.component_id, selection.target_version, selection.target_sha256,
                state=AInStoredPackageState.INSTALLED,
            )
            if package is None:
                obsolete = self.package_manager.package_store.find(
                    selection.component_id, selection.target_version, selection.target_sha256,
                    state=AInStoredPackageState.OBSOLETE,
                )
                if obsolete is not None:
                    package = self.restore_obsolete_package(obsolete)
            if package is None:
                downloaded = self.package_manager.package_store.find(
                    selection.component_id, selection.target_version, selection.target_sha256,
                    state=AInStoredPackageState.DOWNLOADED,
                )
                if downloaded is not None:
                    package = self.install_downloaded_package(self._candidate_from_stored_package(downloaded), downloaded)
            if package is None and selection.source_id and selection.artifact_id:
                if self.catalog_product_id is None or self.catalog_technology_id is None:
                    raise RuntimeError("AAC catalog scope is not configured")
                package = self.install_catalog_package(
                    selection.source_id, self.catalog_product_id, self.catalog_technology_id,
                    selection.component_id, selection.target_version, selection.artifact_id,
                )
            if package is None:
                raise AIxUpgradeError(
                    f"solver target artifact unavailable for {selection.component_id}/{selection.target_version}"
                )
            targets.append(package)
        if not targets:
            return AIcComponentUpgradeTransactionOutcome(application_scope_id, (), False, ("solver target already active",))
        # Download/install preparation is intentionally outside the cutover transaction.  The same
        # crash-safe multi-component replacement primitive remains the sole activation mechanism.
        return self.upgrade_stored_packages(
            application_scope_id, tuple(targets), trusted_namespace_prefixes=trusted_namespace_prefixes
        )

    def register_entitlement_evidence_verifier(self, evidence_type: str, verifier: AIiEntitlementEvidenceVerifier) -> None:
        self.entitlement_verifiers.register(evidence_type, verifier)

    def register_trusted_entitlement_issuer(self, rule: AIcTrustedEntitlementIssuerRule) -> None:
        self.trusted_entitlement_issuers.register(rule)

    def register_file_entitlement_provider(
        self, entitlement_provider_id: str, root: str, *, pattern: str = "*.entitlement.yml",
        evidence_type: str = "SIGNED_FILE", sidecar_suffix: str = ".sigstore.json",
    ) -> None:
        self.register_entitlement_provider(
            entitlement_provider_id,
            AIcFileEntitlementProvider(root, pattern=pattern, evidence_type=evidence_type, sidecar_suffix=sidecar_suffix),
        )

    def _refresh_entitlements_after_remediation(self) -> None:
        for application_scope_id in tuple(self._active_application_scope_ids):
            self.revalidate_entitlements(application_scope_id)

    def refresh_entitlements_if_due(self, now=None) -> tuple[str, ...]:
        if not AIcEntitlementRefreshPlanner.due(self.entitlement.cached_contexts(), now):
            return ()
        updated: list[str] = []
        for application_scope_id in tuple(self._active_application_scope_ids):
            updated.extend(self.revalidate_entitlements(application_scope_id))
        return tuple(updated)

    def register_secret_provider(self, secret_provider_id: str, provider: AIiSecretProvider, *, bootstrap_safe: bool = False) -> None:
        self.authentication.secret_providers.register(secret_provider_id, provider)
        if bootstrap_safe:
            self._bootstrap_safe_secret_provider_ids.add(secret_provider_id)

    def register_authentication_handler(self, mechanism: str, handler: AIiAuthenticationHandler) -> None:
        self.authentication.handlers.register(mechanism, handler)

    def apply_security_bootstrap(self, bootstrap: AIcSecurityBootstrap) -> None:
        self.security_bootstrap = bootstrap
        for registration in bootstrap.secret_providers:
            if not self.authentication.secret_providers.contains(registration.id):
                kind = registration.type.upper()
                settings = dict(registration.settings)
                if kind == "ENVIRONMENT":
                    provider = AIcEnvironmentSecretProvider(str(settings.get("prefix", "")))
                elif kind in {"FILE", "FILESYSTEM"}:
                    provider = AIcFileSecretProvider(
                        str(settings["root"]), read_only=bool(settings.get("read_only", True)),
                        encoding=str(settings.get("encoding", "utf-8")),
                    )
                else:
                    raise ValueError(f"no secret-provider factory registered for type {registration.type!r}")
                self.register_secret_provider(registration.id, provider, bootstrap_safe=registration.bootstrap_safe)
            elif registration.bootstrap_safe:
                self._bootstrap_safe_secret_provider_ids.add(registration.id)
        for profile in bootstrap.authentication_profiles:
            if not self.authentication.profiles.contains(profile.id):
                for parameter in profile.parameters.values():
                    if parameter.secret_reference is not None and not self.authentication.secret_providers.contains(parameter.secret_reference.secret_provider_id):
                        raise ValueError(
                            f"authentication profile {profile.id!r} references unknown secret-provider "
                            f"{parameter.secret_reference.secret_provider_id!r}"
                        )
                self.authentication.register_profile(profile)

    def _authentication_profile_is_bootstrap_safe(self, profile_id: str) -> bool:
        profile = self.authentication.profiles.get(profile_id)
        return all(
            parameter.secret_reference is None or parameter.secret_reference.secret_provider_id in self._bootstrap_safe_secret_provider_ids
            for parameter in profile.parameters.values()
        )

    def register_configuration_provider(self, configuration_provider_id: str, provider: AIiConfigurationProvider) -> None:
        self.configuration_providers.register(configuration_provider_id, provider)

    def register_configuration_scope_resolver(self, configuration_scope_resolver_id: str, resolver: AIiConfigurationScopeResolver) -> None:
        self.configuration_scope_resolvers.register(configuration_scope_resolver_id, resolver)

    def configure_entity_extension_store(self, store: AIiEntityExtensionDataStore | None) -> None:
        """Attach the product-owned semantic extension-data store.

        Stored extension payloads may remain at older readable/migratable schema versions. Core
        normalizes them on read; persistence convergence is independent from component cutover.
        """
        self.entity_extension_store = store

    def register_entity_context(self, context: AIcCoreEntityContext) -> None:
        """Expose an active Core entity to AAC for extension-data compatibility/migration."""
        self._entity_contexts[(context.entity.entity_type_id, context.entity.entity_id)] = context

    def unregister_entity_context(self, entity_type_id: str, entity_id: str) -> None:
        self._entity_contexts.pop((entity_type_id, entity_id), None)

    @property
    def entity_contexts(self) -> tuple[AIcCoreEntityContext, ...]:
        return tuple(self._entity_contexts[key] for key in sorted(self._entity_contexts))

    def read_entity_extension_data(
        self, entity_type_id: str, entity_id: str, component_id: str, *, persist_migration: bool = True
    ):
        """Return extension data interpretable by the currently installed component.

        A transformation-required stored envelope is transformed and validated in memory first. If the
        store permits conditional mutation, Core may then try to persist the normalized envelope
        with the snapshot's ``record_revision`` as ``expected_record_revision``. Persistence
        failure is deliberately ignored: the migrated in-memory representation remains usable and
        a later read can retry convergence.
        """
        if self.entity_extension_store is None:
            return None
        context = self._entity_contexts.get((entity_type_id, entity_id))
        if context is None:
            raise KeyError(f"unknown Core entity context {entity_type_id!r}/{entity_id!r}")
        extension_record = self.entity_extension_store.get_record(context.entity, component_id)
        if extension_record is None:
            return None
        envelope = extension_record.envelope
        installed = self._installed.get(component_id)
        if installed is None:
            raise KeyError(f"component {component_id!r} is not installed")
        extension = next(
            (item for item in installed.descriptor.entity_extensions if item.entity_type_id == entity_type_id),
            None,
        )
        declaration = extension.extension_data.component_extension_schema if extension is not None else None
        if declaration is None:
            raise AIxPersistedPayloadMigrationError(
                f"component {component_id!r} does not declare extension data for {entity_type_id!r}"
            )
        assessment = self.entity_extension_migrations.assess(context, envelope, extension.extension_data)
        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED:
            # Unsupported semantic extension data remains owned/preserved by the store but is
            # unavailable to this component version.  This is a forward-compatibility condition,
            # not a Core failure.
            return None
        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.DIRECT:
            return envelope

        migrated = self.entity_extension_migrations.migrate_to_write_version(
            context, envelope, extension.extension_data,
            written_by_component_version=installed.descriptor.version,
        )
        if declaration.resource_name is not None:
            self.schemas.normalize_value(declaration.resource_name, migrated.payload, apply_defaults=False)
        if persist_migration and self.configuration_reads.persist_migrations:
            try:
                self.entity_extension_store.put(
                    migrated, expected_record_revision=extension_record.record_revision
                )
            except Exception:
                pass
        return migrated

    def converge_persisted_component_data(self, component_ids: tuple[str, ...] | None = None):
        """Retry best-effort persistence convergence for currently installed components.

        This operation is intentionally outside component replacement transactions. It is safe to
        retry after startup or administrative request because each payload is persisted
        independently with provider/store concurrency checks where available.
        """
        selected = tuple(component_ids) if component_ids is not None else tuple(sorted(self._installed))
        candidates = tuple(self._installed[component_id].discovered for component_id in selected)
        coordinator = AIcUpgradeMigrationCoordinator()
        stage = coordinator.stage(self, candidates)
        if not stage.compatible:
            detail = "; ".join(f"{item.component_id}: {item.message}" for item in stage.diagnostics)
            raise AIxUpgradeError(f"persisted-data convergence preflight failed: {detail}")
        return coordinator.converge(self, stage)

    def register_entitlement_provider(self, entitlement_provider_id: str, provider: AIiEntitlementProvider) -> None:
        self.entitlement_providers.register(entitlement_provider_id, provider)

    def register_licensing_scope_resolver(self, licensing_scope_resolver_id: str, resolver: AIiEntitlementLicensingScopeResolver) -> None:
        self.licensing_scope_resolvers.register(licensing_scope_resolver_id, resolver)

    def _install_configuration_bootstrap_registrations(self, bootstrap: AIcConfigurationBootstrap) -> None:
        for registration in bootstrap.configuration_scope_resolvers:
            if self.configuration_scope_resolvers.contains(registration.id):
                continue
            if registration.type.upper() in {"MAPPING", "STATIC_MAPPING"}:
                self.register_configuration_scope_resolver(registration.id, AIcStaticConfigurationScopeResolver())
            else:
                raise ValueError(f"no configuration-scope resolver factory registered for type {registration.type!r}")
        for registration in bootstrap.configuration_providers:
            if self.configuration_providers.contains(registration.id):
                continue
            if registration.authentication_profile_id is not None:
                if not self.authentication.profiles.contains(registration.authentication_profile_id):
                    raise ValueError(
                        f"configuration-provider {registration.id!r} references unknown authentication profile "
                        f"{registration.authentication_profile_id!r}"
                    )
                if not self._authentication_profile_is_bootstrap_safe(registration.authentication_profile_id):
                    raise ValueError(
                        f"configuration-provider {registration.id!r} authentication profile is not bootstrap-safe"
                    )
            settings = dict(registration.settings)
            kind = registration.type.upper()
            if kind in {"FILE", "FILESYSTEM"}:
                provider = AIcFileSystemConfigurationProvider(
                    str(settings["root"]), read_only=bool(settings.get("read_only", False)),
                    allow_policy_write=bool(settings.get("allow_policy_write", True)),
                )
            elif kind in {"HTTP", "HTTPS"}:
                provider = AIcHttpConfigurationProvider(
                    str(settings["base_url"]), authentication=self.authentication,
                    authentication_profile_id=registration.authentication_profile_id,
                    read_only=bool(settings.get("read_only", False)),
                    allow_policy_write=bool(settings.get("allow_policy_write", True)),
                    timeout_seconds=float(settings.get("timeout_seconds", 10.0)),
                    mutation_method=str(settings.get("mutation_method", "PATCH")),
                )
            else:
                raise ValueError(f"no configuration-provider factory registered for type {registration.type!r}")
            self.register_configuration_provider(registration.id, provider)

    def _load_external_configuration_profiles(self, bootstrap: AIcConfigurationBootstrap) -> AIcConfigurationBootstrap:
        if not bootstrap.configuration_profile_sources:
            return bootstrap
        profiles = list(bootstrap.configuration_profiles)
        by_id = {item.id for item in profiles}
        loader = AIcBootstrapResourceLoader(self.authentication)
        provider_ids = {item.id for item in bootstrap.configuration_providers}
        resolver_ids = {item.id for item in bootstrap.configuration_scope_resolvers} | {"_AAC.context.mapping"}
        for source in bootstrap.configuration_profile_sources:
            if source.authentication_profile_id is not None:
                if not self.authentication.profiles.contains(source.authentication_profile_id):
                    raise ValueError(f"configuration-profile source {source.id!r} references unknown authentication profile")
                if not self._authentication_profile_is_bootstrap_safe(source.authentication_profile_id):
                    raise ValueError(f"configuration-profile source {source.id!r} authentication profile is not bootstrap-safe")
            try:
                text = loader.read_text(
                    source.uri, authentication_profile_id=source.authentication_profile_id, context=self.application_context
                )
                profile = AIcConfigurationProfileLoader.load_text(text, source=source.uri)
            except Exception:
                if source.required:
                    raise
                continue
            if profile.id in by_id:
                raise ValueError(f"configuration profile {profile.id!r} is defined more than once")
            for definition in profile.configuration_scopes:
                if definition.configuration_scope_resolver_id not in resolver_ids:
                    raise ValueError(f"external configuration profile {profile.id!r} references unknown resolver {definition.configuration_scope_resolver_id!r}")
                for binding in definition.configuration_providers:
                    if binding.configuration_provider_id not in provider_ids and not self.configuration_providers.contains(binding.configuration_provider_id):
                        raise ValueError(f"external configuration profile {profile.id!r} references unknown provider {binding.configuration_provider_id!r}")
            by_id.add(profile.id); profiles.append(profile)
        return replace(bootstrap, configuration_profiles=tuple(profiles))

    def apply_configuration_bootstrap(
        self,
        bootstrap: AIcConfigurationBootstrap,
        *,
        context: dict[str, object] | None = None,
        configuration_profile_id: str | None = None,
    ) -> tuple:
        self.application_context = dict(context or {})
        self._install_configuration_bootstrap_registrations(bootstrap)
        bootstrap = self._load_external_configuration_profiles(bootstrap)
        self.configuration_bootstrap = bootstrap
        profile = bootstrap.profile(configuration_profile_id)
        self.active_configuration_scopes = self.configuration_context_resolver.resolve(profile, self.application_context)
        mandatory = set(bootstrap.mandatory_configuration_scope_definition_ids)
        present = {item.definition_id for item in self.active_configuration_scopes}
        missing = mandatory - present
        if missing:
            raise ValueError(f"mandatory configuration-scope definitions are absent from active profile/context: {sorted(missing)}")
        self.lifecycle.entitlement_context = dict(self.application_context)
        return self.active_configuration_scopes

    def apply_entitlement_bootstrap(
        self,
        bootstrap: AIcEntitlementBootstrap,
        *,
        context: dict[str, object] | None = None,
        entitlement_profile_id: str | None = None,
    ) -> tuple[AIcResolvedEntitlementLicensingScope, ...]:
        self.entitlement_bootstrap = bootstrap
        if context is not None:
            self.application_context = dict(context)
        for registration in bootstrap.entitlement_providers:
            if registration.id in self.entitlement_providers._providers:
                continue
            kind = registration.type.upper()
            settings = dict(registration.settings)
            if kind in {"FILE", "FILESYSTEM"}:
                self.register_file_entitlement_provider(
                    registration.id, str(settings["root"]),
                    pattern=str(settings.get("pattern", "*.entitlement.yml")),
                    evidence_type=str(settings.get("evidence_type", "SIGNED_FILE")),
                    sidecar_suffix=str(settings.get("sidecar_suffix", ".sigstore.json")),
                )
            else:
                raise ValueError(f"no entitlement-provider factory registered for type {registration.type!r}")
        for rule in bootstrap.trusted_issuers:
            self.register_trusted_entitlement_issuer(rule)
        profile = bootstrap.profile(entitlement_profile_id)
        self.active_licensing_scopes = self.entitlement_context_resolver.resolve(profile, self.application_context)
        self.lifecycle.licensing_scopes = self.active_licensing_scopes
        self.lifecycle.entitlement_context = dict(self.application_context)
        return self.active_licensing_scopes

    def resolve_scoped_configuration(
        self,
        *,
        configuration_target: AIcConfigurationTarget,
        property_ids,
        accepted_configuration_scope_types=None,
        schema_defaults=None,
    ) -> AIcEffectiveConfiguration:
        return self.configuration_resolver.resolve(
            configuration_target=configuration_target,
            configuration_scopes=self.active_configuration_scopes,
            property_ids=property_ids,
            accepted_configuration_scope_types=accepted_configuration_scope_types,
            schema_defaults=schema_defaults,
            context=self.application_context,
        )

    def apply_configuration_changes(self, change_set: AIcConfigurationChangeSet):
        declaration, component_version = self._configuration_schema_for_target(change_set.configuration_target)
        if declaration is None:
            raise ValueError("scoped configuration mutation requires a declared persisted configuration schema")
        if change_set.configuration_schema_id is None:
            change_set = replace(
                change_set,
                configuration_schema_id=declaration.schema_id,
                configuration_schema_version=declaration.write_version,
                written_by_component_version=component_version,
            )
        if change_set.configuration_schema_id != declaration.schema_id or change_set.configuration_schema_version != declaration.write_version:
            raise ValueError("configuration mutation must target the current writable configuration schema")
        provider = self.configuration_providers.get(change_set.configuration_provider_id)
        request = AIcConfigurationProviderRequest(
            change_set.configuration_target, change_set.configuration_scope, change_set.actor_context
        )
        snapshot = provider.snapshot(request)
        candidate = dict(snapshot.payload.values) if snapshot is not None else {}
        for change in change_set.changes:
            if change.operation is AInConfigurationMutationOperation.SET_VALUE:
                candidate[change.property_id] = change.value
            elif change.operation is AInConfigurationMutationOperation.DELETE_VALUE:
                candidate.pop(change.property_id, None)
        if declaration.resource_name is not None:
            self.schemas.normalize(declaration.resource_name, candidate, apply_defaults=False)
        result = self.configuration_mutations.apply(change_set)
        for application_scope_id in tuple(self._active_application_scope_ids):
            if change_set.configuration_target.kind is AInConfigurationTargetKind.PROVIDER_INSTANCE:
                instance_id = str(change_set.configuration_target.provider_instance_id)
                if self.lifecycle.provider_readiness(application_scope_id, instance_id) is not None:
                    self.refresh_provider_readiness(application_scope_id, instance_id)
            else:
                self.refresh_component_readiness(application_scope_id, change_set.configuration_target.component_id)
        return result

    def configuration_provider_access(self, configuration_provider_id, configuration_scope, configuration_target, actor_context=None):
        from algites.lib.aac.coreintf.configuration import AIcConfigurationProviderRequest
        return self.configuration_mutations.access_for(
            configuration_provider_id,
            AIcConfigurationProviderRequest(configuration_target, configuration_scope, dict(actor_context or {})),
            dict(actor_context or {}),
        )

    def _configuration_schema_for_target(self, target: AIcConfigurationTarget):
        installed = self.installed(target.component_id)
        if target.kind is AInConfigurationTargetKind.COMPONENT:
            return installed.descriptor.component_configuration_schema, installed.descriptor.version
        instance = self.instances.get(str(target.provider_instance_id))
        provider = installed.descriptor.provider(instance.provider_definition_id)
        return provider.configuration_schema, installed.descriptor.version

    def resolve_component_scoped_configuration(self, component_id: str) -> AIcEffectiveConfiguration:
        descriptor = self.installed(component_id).descriptor
        target = AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, component_id)
        if descriptor.component_configuration_schema is None:
            return self.resolve_scoped_configuration(configuration_target=target, property_ids=())
        property_ids, accepted, defaults = self.schemas.configuration_property_metadata(descriptor.component_configuration_schema.resource_name)
        return self.resolve_scoped_configuration(
            configuration_target=target, property_ids=property_ids,
            accepted_configuration_scope_types=accepted, schema_defaults=defaults,
        )

    def resolve_provider_scoped_configuration(self, instance_id: str) -> AIcEffectiveConfiguration:
        instance = self.instances.get(instance_id)
        target = AIcConfigurationTarget(
            AInConfigurationTargetKind.PROVIDER_INSTANCE, instance.component_id, instance.id
        )
        if instance.configuration_schema is None:
            return self.resolve_scoped_configuration(
                configuration_target=target, property_ids=tuple(instance.configuration),
            )
        property_ids, accepted, defaults = self.schemas.configuration_property_metadata(instance.configuration_schema)
        return self.resolve_scoped_configuration(
            configuration_target=target, property_ids=property_ids,
            accepted_configuration_scope_types=accepted, schema_defaults=defaults,
        )

    def _admit_discovered(
        self,
        discovered: AIcDiscoveredComponent,
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
        origin: AInComponentOrigin = AInComponentOrigin.PACKAGE,
    ) -> AIcInstalledComponent:
        descriptor = discovered.descriptor
        package = discovered.package
        self.namespaces.validate(descriptor, trusted_namespace_prefixes)
        if package is None:
            raise ValueError("Python package installation requires a package-backed descriptor")

        for resource_name, text, source in iter_discovered_resources(discovered, "schemas", suffix=".json"):
            self.schemas.register_text(resource_name, text, source=source)

        if descriptor.component_configuration_schema is not None:
            self.schemas.get(descriptor.component_configuration_schema.resource_name)
        for provider in descriptor.providers:
            if provider.configuration_schema is not None:
                self.schemas.get(provider.configuration_schema.resource_name)
        for contract_resource in descriptor.contract_resources:
            text, source = read_discovered_resource(discovered, contract_resource)
            self.contracts.admit_text(text, source=source)

        for provider in descriptor.providers:
            for requirement in provider.requirements:
                for version in requirement.versions:
                    if not self.contracts.contains(requirement.capability_id, version):
                        continue
                    contract = self.contracts.get(requirement.capability_id, version)
                    known = {permission.id for permission in contract.authorization_permissions}
                    unknown = set(requirement.requested_authorizations) - known
                    if unknown:
                        raise ValueError(
                            f"requirement {provider.id}:{requirement.id} requests authorization permissions "
                            f"not declared by {requirement.capability_id}/{version}: {sorted(unknown)!r}"
                        )

        installed = AIcInstalledComponent(discovered, origin)
        self._installed[descriptor.id] = installed
        return installed


    def verify_python_artifact(
        self,
        wheel_path: str,
        package: str,
        resource_name: str = "component.yml",
    ) -> AIcDiscoveredComponent:
        """Verify a wheel before importing any code from the component package."""
        discovered = AIcDescriptorLoader.discover_wheel(wheel_path, package, resource_name)
        descriptor = discovered.descriptor
        output = self.verifier.verify(AIcVerificationInput(
            descriptor.id, descriptor.version, package, discovered.source, descriptor.metadata, str(wheel_path)
        ))
        if not output.valid:
            raise AIxVerificationError("artifact verification failed: " + "; ".join(output.diagnostics))
        return discovered

    def install_verified_python_package(
        self,
        verified: AIcDiscoveredComponent,
        resource_name: str = "component.yml",
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
    ) -> AIcInstalledComponent:
        if verified.package is None or verified.artifact_path is None:
            raise AIxVerificationError("verified artifact must identify both package and artifact path")
        installed_descriptor = AIcDescriptorLoader.discover_package(
            verified.package, resource_name, artifact_path=verified.artifact_path
        )
        if installed_descriptor.descriptor != verified.descriptor:
            raise AIxVerificationError("installed component descriptor differs from the descriptor verified inside the wheel")
        return self._admit_discovered(installed_descriptor, trusted_namespace_prefixes=trusted_namespace_prefixes)

    def install_python_package(
        self,
        package: str,
        resource_name: str = "component.yml",
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
        artifact_path: str | None = None,
    ) -> AIcInstalledComponent:
        discovered = AIcDescriptorLoader.discover_package(package, resource_name, artifact_path=artifact_path)
        return self._admit_discovered(discovered, trusted_namespace_prefixes=trusted_namespace_prefixes)

    def install_aac_package(
        self,
        package: str,
        resource_name: str = "component.yml",
        *,
        artifact_path: str | None = None,
    ) -> AIcInstalledComponent:
        return self.install_python_package(
            package,
            resource_name,
            trusted_namespace_prefixes=("_AAC.",),
            artifact_path=artifact_path,
        )

    def register_builtin_python_component(
        self,
        package: str,
        resource_name: str = "component.yml",
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
    ) -> AIcInstalledComponent:
        """Admit product-shipped code as a first-class AAC component without package installation.

        Built-in components use the same contracts, configuration, entitlement, bindings and
        Core bridge as external components. Their requested capability authorizations are
        pre-approved by product trust when provider instances are provisioned.
        """
        discovered = AIcDescriptorLoader.discover_package(package, resource_name)
        installed = self._admit_discovered(
            discovered, trusted_namespace_prefixes=trusted_namespace_prefixes, origin=AInComponentOrigin.BUILTIN
        )
        self._builtin_component_ids.add(installed.descriptor.id)
        return installed

    def authorization_context(self, principal: AIcAuthorizationPrincipal | None):
        return authorization_principal_context(principal)

    def set_component_authorization_grant(
        self,
        consumer_instance_id: str,
        requirement_id: str,
        permission_ids: tuple[str, ...],
        *,
        approved_by: str | None = None,
    ) -> AIcComponentAuthorizationGrant:
        instance = self.instances.get(consumer_instance_id)
        descriptor = self.installed(instance.component_id).descriptor
        provider = descriptor.provider(instance.provider_definition_id)
        requirement = next((item for item in provider.requirements if item.id == requirement_id), None)
        if requirement is None:
            raise KeyError(f"unknown requirement {requirement_id!r} for consumer {consumer_instance_id!r}")
        requested = set(requirement.requested_authorizations)
        unknown = set(permission_ids) - requested
        if unknown:
            raise ValueError(f"cannot grant authorization permissions not requested by the component: {sorted(unknown)!r}")
        grant = AIcComponentAuthorizationGrant(
            consumer_instance_id, requirement_id, tuple(permission_ids), approved_by=approved_by
        )
        self.component_authorizations.put(grant)
        return grant

    def component_authorization_grant(self, consumer_instance_id: str, requirement_id: str):
        return self.component_authorizations.get(consumer_instance_id, requirement_id)

    def _preapprove_builtin_authorizations(self) -> None:
        for component_id in sorted(self._builtin_component_ids):
            descriptor = self.installed(component_id).descriptor
            for instance in self.instances.find(component_id=component_id):
                provider = descriptor.provider(instance.provider_definition_id)
                for requirement in provider.requirements:
                    if requirement.requested_authorizations:
                        self.component_authorizations.put(AIcComponentAuthorizationGrant(
                            instance.id, requirement.id, requirement.requested_authorizations, approved_by="BUILTIN_PRODUCT_TRUST"
                        ))

    def installed(self, component_id: str) -> AIcInstalledComponent:
        return self._installed[component_id]

    def installed_components(self) -> tuple[AIcInstalledComponent, ...]:
        return tuple(self._installed[key] for key in sorted(self._installed))

    def create_provider_instance(
        self, component_id: str, provider_definition_id: str, *, name: str = "default", configuration: dict[str, object] | None = None
    ) -> AIcProviderInstance:
        descriptor = self.installed(component_id).descriptor
        provider = descriptor.provider(provider_definition_id)
        normalized = dict(configuration or {})
        state = AInProviderInstanceState.CONFIGURED
        if provider.configuration_schema is not None:
            try:
                normalized = self.schemas.normalize(provider.configuration_schema.resource_name, normalized)
            except AIxSchemaValidationError:
                # Creating the stable provider-instance identity is allowed before mandatory
                # user configuration exists. The instance is simply excluded from provider
                # candidates until configuration is completed and validated.
                state = AInProviderInstanceState.UNCONFIGURED
        return self.instances.create(component_id, provider, name=name, configuration=normalized, state=state)

    def rename_provider_instance(self, instance_id: str, name: str) -> AIcProviderInstance:
        name = name.strip()
        if not name:
            raise ValueError("provider instance name must not be empty")
        return self.instances.update(instance_id, name=name)

    def remove_provider_instance(self, instance_id: str) -> None:
        references = self.bindings.references_instance(instance_id)
        if references:
            raise ValueError(f"provider instance {instance_id!r} is referenced by resolved bindings")
        for preference in self.preferences.all() if hasattr(self.preferences, "all") else ():
            if instance_id == preference.consumer_instance_id or instance_id in preference.provider_instance_ids:
                raise ValueError(f"provider instance {instance_id!r} is referenced by binding preferences")
        if self.observation_topology.get(instance_id) is not None:
            raise ValueError(f"provider instance {instance_id!r} has observation topology configured")
        self.instances.remove_ids((instance_id,))

    def configure_provider_instance(self, instance_id: str, configuration: dict[str, object]) -> AIcProviderInstance:
        instance = self.instances.get(instance_id)
        if instance.configuration_schema is None:
            updated = self.instances.update(
                instance_id,
                configuration=dict(configuration),
                state=AInProviderInstanceState.CONFIGURED,
            )
        else:
            normalized = self.schemas.normalize(instance.configuration_schema, configuration)
            updated = self.instances.update(
                instance_id,
                configuration=normalized,
                state=AInProviderInstanceState.CONFIGURED,
            )
        for application_scope_id in self.active_application_scope_ids():
            if self.lifecycle.provider_readiness(application_scope_id, instance_id) is not None:
                self.refresh_provider_readiness(application_scope_id, instance_id)
        return updated

    def set_binding_preference(self, preference: AIcBindingPreference) -> None:
        self.preferences.put(preference)

    def configure_observer(self, binding: AIcObservationBinding) -> None:
        self.observation_topology.put(binding)

    def activate_application(self, application_scope_id: str) -> AIcResolvedApplicationGraph:
        self._active_application_scope_ids.add(application_scope_id)
        for component in self._installed.values():
            self.lifecycle.prepare_component(application_scope_id, component.discovered)

        self._preapprove_builtin_authorizations()
        descriptors = {component_id: installed.descriptor for component_id, installed in self._installed.items()}
        graph = self.graph.resolve(descriptors)
        for descriptor in descriptors.values():
            self.lifecycle.mark_resolved(application_scope_id, descriptor)

        ordered = list(graph.provider_first_order)
        all_ids = {instance.id for instance in self.instances.all()}
        ordered.extend(sorted(all_ids - set(ordered)))
        for instance_id in ordered:
            instance = self.instances.get(instance_id)
            descriptor = descriptors[instance.component_id]
            self.lifecycle.activate_instance(
                application_scope_id, descriptor, instance_id, graph.bindings,
                component_configuration=self.resolve_component_scoped_configuration(instance.component_id),
                provider_instance_configuration=self.resolve_provider_scoped_configuration(instance.id),
            )
        return AIcResolvedApplicationGraph(graph.bindings, tuple(ordered))

    @staticmethod
    def _matches_python_package(module_name: str, package_prefixes: tuple[str, ...]) -> bool:
        return any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in package_prefixes)

    def _begin_python_candidate_import_cutover(
        self, candidates: tuple[AIcDiscoveredComponent, ...]
    ) -> AIcPythonCandidateImportSnapshot:
        """Make exact candidate wheel namespaces importable without retaining the old module cache.

        Descriptor, schema and contract preflight never needs this operation because those resources
        are read directly from the candidate artifact.  The cutover is deliberately delayed until
        after the current runtime has been deactivated.
        """
        exact_candidates = tuple(
            candidate for candidate in candidates
            if candidate.package is not None and candidate.artifact_path is not None
        )
        package_prefixes = tuple(sorted({candidate.package for candidate in exact_candidates if candidate.package}))
        snapshot = AIcPythonCandidateImportSnapshot(
            tuple(sys.path),
            {
                name: module for name, module in sys.modules.items()
                if self._matches_python_package(name, package_prefixes)
            },
            package_prefixes,
        )
        if not exact_candidates:
            return snapshot

        target_paths = tuple(dict.fromkeys(str(candidate.artifact_path) for candidate in exact_candidates))
        replaced_paths: set[str] = set()
        for candidate in exact_candidates:
            installed = self._installed.get(candidate.descriptor.id)
            if installed is not None and installed.discovered.artifact_path is not None:
                replaced_paths.add(str(installed.discovered.artifact_path))
        excluded_paths = set(target_paths) | replaced_paths
        sys.path[:] = list(target_paths) + [path for path in sys.path if path not in excluded_paths]
        for name in tuple(sys.modules):
            if self._matches_python_package(name, package_prefixes):
                sys.modules.pop(name, None)
        importlib.invalidate_caches()
        return snapshot

    @staticmethod
    def _rollback_python_candidate_import_cutover(snapshot: AIcPythonCandidateImportSnapshot) -> None:
        for name in tuple(sys.modules):
            if AIcApplicationComponentCore._matches_python_package(name, snapshot.package_prefixes):
                sys.modules.pop(name, None)
        sys.modules.update(snapshot.modules)
        sys.path[:] = list(snapshot.sys_path)
        importlib.invalidate_caches()

    def plan_python_package_upgrades(
        self,
        application_scope_id: str,
        packages: tuple[str, ...],
        resource_name: str = "component.yml",
        *,
        artifact_paths: dict[str, str] | None = None,
    ) -> AIcComponentUpgradePlan:
        """Validate a complete multi-component target state without changing the live state.

        All replacements participate in one hypothetical graph.  Intermediate states obtained by
        applying replacements one at a time are intentionally irrelevant.
        """
        artifact_paths = dict(artifact_paths or {})
        candidates = tuple(
            AIcDescriptorLoader.discover_package(package, resource_name, artifact_path=artifact_paths.get(package))
            for package in packages
        )
        return AIcTargetStateUpgradeAnalyzer().analyze(self, application_scope_id, candidates)

    def upgrade_python_packages(
        self,
        application_scope_id: str,
        packages: tuple[str, ...],
        resource_name: str = "component.yml",
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
        artifact_paths: dict[str, str] | None = None,
    ) -> AIcComponentUpgradeTransactionOutcome:
        """Replace one or more components as one logical transaction.

        The complete target contract catalog and provider graph are preflighted before any runtime
        is deactivated.  During commit, every candidate is admitted before the graph is resolved,
        so no intermediate one-component state is required to be valid.  Core state, schemas,
        contracts and descriptors are restored together if commit or target activation fails.
        """
        artifact_paths = dict(artifact_paths or {})
        candidates = tuple(
            AIcDescriptorLoader.discover_package(package, resource_name, artifact_path=artifact_paths.get(package))
            for package in packages
        )
        plan = AIcTargetStateUpgradeAnalyzer().analyze(self, application_scope_id, candidates)
        if not plan.compatible:
            detail = "; ".join(
                f"{item.component_id}: {item.message}" for item in plan.diagnostics
            )
            raise AIxUpgradeError(f"upgrade target state is incompatible: {detail}")
        migration_coordinator = AIcUpgradeMigrationCoordinator()
        migration_stage = migration_coordinator.stage(self, candidates)
        if not migration_stage.compatible:
            detail = "; ".join(f"{item.component_id}: {item.message}" for item in migration_stage.diagnostics)
            raise AIxUpgradeError(f"upgrade persisted-state compatibility is invalid: {detail}")

        state_snapshot = self.store.snapshot()
        schema_snapshot = self.schemas.snapshot()
        contract_snapshot = self.contracts.snapshot()
        installed_snapshot = dict(self._installed)
        import_snapshot = AIcPythonCandidateImportSnapshot(tuple(sys.path), {}, ())
        persist_migrations_before = self.configuration_reads.persist_migrations
        self.configuration_reads.persist_migrations = False

        try:
            self.lifecycle.deactivate_all_runtimes("component upgrade transaction")
            import_snapshot = self._begin_python_candidate_import_cutover(candidates)
            # Admit every target descriptor before reconciling runtime. Persisted data is not
            # mutated inside this transaction; the preflight already proved that target runtime
            # can operate on current data through direct/on-the-fly interpretation.
            for candidate in candidates:
                self._admit_discovered(candidate, trusted_namespace_prefixes=trusted_namespace_prefixes)
            for candidate in candidates:
                self.instances.reconcile_descriptor(candidate.descriptor)
            self.activate_application(application_scope_id)
        except Exception as exc:
            try:
                self.lifecycle.deactivate_all_runtimes("upgrade transaction rollback")
            except Exception:
                pass
            self.store.restore(state_snapshot)
            self.schemas.restore(schema_snapshot)
            self.contracts.restore(contract_snapshot)
            self._installed = installed_snapshot
            self._rollback_python_candidate_import_cutover(import_snapshot)
            self._rebuild_runtime_services()
            self.configuration_reads.persist_migrations = persist_migrations_before
            try:
                self.activate_application(application_scope_id)
            except Exception as rollback_exc:
                raise AIxUpgradeError(
                    f"upgrade transaction failed and rollback activation also failed: {rollback_exc}"
                ) from rollback_exc
            raise AIxUpgradeError(f"upgrade transaction failed and was rolled back: {exc}") from exc

        self.configuration_reads.persist_migrations = persist_migrations_before
        # Component cutover is already committed. Persistence convergence is independent and
        # cannot cause the successful component transaction to be rolled back.
        convergence = migration_coordinator.converge(self, migration_stage)
        notes = [f"activated {len(plan.replacements)} component replacement(s)"]
        notes.append(
            f"post-upgrade persistence convergence: configuration {convergence.configuration_persisted} persisted/"
            f"{convergence.configuration_deferred} deferred; extension data "
            f"{convergence.entity_extensions_persisted} persisted/{convergence.entity_extensions_deferred} deferred"
        )
        notes.extend(convergence.diagnostics)
        return AIcComponentUpgradeTransactionOutcome(
            application_scope_id, plan.replacements, False, tuple(notes),
        )

    def upgrade_python_package(
        self,
        application_scope_id: str,
        package: str,
        resource_name: str = "component.yml",
        *,
        trusted_namespace_prefixes: tuple[str, ...] = (),
        artifact_path: str | None = None,
    ) -> AIcUpgradeOutcome:
        """Compatibility wrapper over the multi-component transaction primitive."""
        previous = AIcDescriptorLoader.discover_package(package, resource_name, artifact_path=artifact_path).descriptor
        old = self._installed.get(previous.id)
        if old is None:
            raise AIxUpgradeError(f"component {previous.id!r} is not installed")
        outcome = self.upgrade_python_packages(
            application_scope_id, (package,), resource_name,
            trusted_namespace_prefixes=trusted_namespace_prefixes,
            artifact_paths={package: artifact_path} if artifact_path is not None else None,
        )
        graph = self.graph.resolve({component_id: installed.descriptor for component_id, installed in self._installed.items()})
        return AIcUpgradeOutcome(previous.id, old.descriptor.version, previous.version, graph)

    def plan_aac_package_upgrades(
        self, application_scope_id: str, packages: tuple[str, ...], resource_name: str = "component.yml"
    ) -> AIcComponentUpgradePlan:
        return self.plan_python_package_upgrades(application_scope_id, packages, resource_name)

    def upgrade_aac_packages(
        self, application_scope_id: str, packages: tuple[str, ...], resource_name: str = "component.yml"
    ) -> AIcComponentUpgradeTransactionOutcome:
        return self.upgrade_python_packages(
            application_scope_id, packages, resource_name, trusted_namespace_prefixes=("_AAC.",)
        )

    def upgrade_aac_package(
        self,
        application_scope_id: str,
        package: str,
        resource_name: str = "component.yml",
        *,
        artifact_path: str | None = None,
    ) -> AIcUpgradeOutcome:
        return self.upgrade_python_package(
            application_scope_id, package, resource_name,
            trusted_namespace_prefixes=("_AAC.",), artifact_path=artifact_path,
        )

    def _discovered_from_stored_package(self, package: AIcStoredPackage):
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        if package.state.value != "INSTALLED":
            raise AIxUpgradeError("only installed/staged target packages can participate in an upgrade transaction")
        if not package.runtime_package:
            raise AIxUpgradeError(f"stored package {package.component_id!r} has no Python runtime_package")
        descriptor = self.package_manager.descriptor_from_artifact(package)
        return AIcDiscoveredComponent(
            descriptor, package.runtime_package,
            f"{package.artifact_path}!/{package.descriptor_path}", package.artifact_path,
        )

    def plan_stored_package_upgrades(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...]
    ) -> AIcComponentUpgradePlan:
        candidates = tuple(self._discovered_from_stored_package(package) for package in packages)
        return AIcTargetStateUpgradeAnalyzer().analyze(self, application_scope_id, candidates)

    def upgrade_stored_packages(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...],
        *, trusted_namespace_prefixes: tuple[str, ...] = (),
    ) -> AIcComponentUpgradeTransactionOutcome:
        """Crash-safe transactional replacement of a complete stored-package target set.

        Target artifacts are verified/staged before this method.  Preflight and persisted-data
        interpretability are side-effect free.  Before runtime cutover Core writes a durable journal
        containing the source Core state and the planned source/target package-set generations.
        The atomic active-package-set manifest replacement is the durable commit boundary.
        """
        if self.package_manager is None:
            raise RuntimeError("package management is not configured")
        candidates = tuple(self._discovered_from_stored_package(package) for package in packages)
        plan = AIcTargetStateUpgradeAnalyzer().analyze(self, application_scope_id, candidates)
        if not plan.compatible:
            detail = "; ".join(f"{item.component_id}: {item.message}" for item in plan.diagnostics)
            raise AIxUpgradeError(f"upgrade target state is incompatible: {detail}")
        migration_coordinator = AIcUpgradeMigrationCoordinator()
        migration_stage = migration_coordinator.stage(self, candidates)
        if not migration_stage.compatible:
            detail = "; ".join(f"{item.component_id}: {item.message}" for item in migration_stage.diagnostics)
            raise AIxUpgradeError(f"upgrade persisted-state compatibility is invalid: {detail}")

        state_snapshot = self.store.snapshot()
        schema_snapshot = self.schemas.snapshot()
        contract_snapshot = self.contracts.snapshot()
        installed_snapshot = dict(self._installed)
        transaction = self.package_manager.begin_replacement_transaction(
            application_scope_id, packages, state_snapshot
        )
        durable_target_committed = False
        cutover_started = False
        commit_diagnostics: list[str] = []
        import_snapshot = AIcPythonCandidateImportSnapshot(tuple(sys.path), {}, ())
        persist_migrations_before = self.configuration_reads.persist_migrations
        self.configuration_reads.persist_migrations = False
        try:
            self.package_manager.mark_replacement_cutover_started(transaction)
            cutover_started = True
            self.lifecycle.deactivate_all_runtimes("package upgrade transaction")
            import_snapshot = self._begin_python_candidate_import_cutover(candidates)
            for candidate in candidates:
                self._admit_discovered(candidate, trusted_namespace_prefixes=trusted_namespace_prefixes)
            for candidate in candidates:
                self.instances.reconcile_descriptor(candidate.descriptor)
            self.activate_application(application_scope_id)
            _, durable_notes = self.package_manager.commit_replacement_selections(transaction)
            durable_target_committed = True
            commit_diagnostics.extend(durable_notes)
        except Exception as exc:
            if durable_target_committed:
                # No normal execution path should arrive here after the manifest commit.  If a future
                # post-commit operation is added and fails, never compensate the committed selection:
                # startup recovery must complete forward from the durable target manifest.
                self.configuration_reads.persist_migrations = persist_migrations_before
                self.package_manager.release_replacement_cutover_lock()
                raise AIxUpgradeError(
                    f"package target set was durably committed but post-commit processing failed: {exc}"
                ) from exc
            if cutover_started:
                try:
                    self.lifecycle.deactivate_all_runtimes("package upgrade rollback")
                except Exception:
                    pass
                self.store.restore(state_snapshot)
                self.schemas.restore(schema_snapshot)
                self.contracts.restore(contract_snapshot)
                self._installed = installed_snapshot
                self._rollback_python_candidate_import_cutover(import_snapshot)
                self._rebuild_runtime_services()
            self.configuration_reads.persist_migrations = persist_migrations_before
            try:
                self.package_manager.rollback_replacement_transaction(
                    transaction, (f"in-process cutover rollback: {exc}",)
                )
            except Exception:
                # Leave the durable active-transaction pointer in place.  Startup recovery will see
                # that no target manifest was committed and restore the source snapshot again.
                pass
            try:
                self.activate_application(application_scope_id)
            except Exception as rollback_exc:
                raise AIxUpgradeError(
                    f"package upgrade failed and rollback activation also failed: {rollback_exc}"
                ) from rollback_exc
            raise AIxUpgradeError(f"package upgrade failed and was rolled back: {exc}") from exc

        self.configuration_reads.persist_migrations = persist_migrations_before
        cleanup_diagnostics: tuple[str, ...] = ()
        try:
            _, cleanup_diagnostics = self.package_manager.complete_replacement_transaction(transaction, packages)
        except Exception as exc:
            # Selection is already durably committed. The unfinished journal intentionally remains
            # active so the next startup can complete package-file cleanup idempotently.
            self.package_manager.release_replacement_cutover_lock()
            cleanup_diagnostics = (f"post-commit cleanup deferred to startup recovery: {exc}",)

        # Persistence convergence is intentionally outside the component transaction.  Failures are
        # diagnostics only and can be retried independently.
        try:
            convergence = migration_coordinator.converge(self, migration_stage)
            convergence_note = (
                f"post-upgrade persistence convergence: configuration {convergence.configuration_persisted} persisted/"
                f"{convergence.configuration_deferred} deferred; extension data "
                f"{convergence.entity_extensions_persisted} persisted/{convergence.entity_extensions_deferred} deferred"
            )
            convergence_diagnostics = convergence.diagnostics
        except Exception as exc:
            convergence_note = "post-upgrade persistence convergence deferred"
            convergence_diagnostics = (str(exc),)

        notes = [f"committed {len(plan.replacements)} package/component replacement(s)"]
        notes.extend(commit_diagnostics)
        notes.extend(cleanup_diagnostics)
        notes.append(convergence_note)
        notes.extend(convergence_diagnostics)
        return AIcComponentUpgradeTransactionOutcome(
            application_scope_id, plan.replacements, False, tuple(notes),
        )

    def revalidate_entitlements(self, application_scope_id: str) -> tuple[str, ...]:
        suspended: list[str] = []
        for installed in self._installed.values():
            suspended.extend(self.lifecycle.revalidate_entitlements(application_scope_id, installed.descriptor))
        return tuple(suspended)

    def unprovision_component(self, application_scope_id: str, component_id: str) -> None:
        installed = self._installed[component_id]
        for instance in self.instances.find(component_id=component_id):
            if instance.state in {
                AInProviderInstanceState.ACTIVE,
                AInProviderInstanceState.ACTIVATABLE,
                AInProviderInstanceState.SUSPENDED,
            }:
                self.lifecycle.deactivate_instance(instance.id, "unprovision")
        self.provisioning.unprovision(application_scope_id, installed.descriptor)

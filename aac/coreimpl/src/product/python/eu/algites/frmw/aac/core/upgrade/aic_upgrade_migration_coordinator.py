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

from .aic_persistence_convergence_outcome import AIcPersistenceConvergenceOutcome
from .aic_staged_configuration_migration import AIcStagedConfigurationMigration
from .aic_upgrade_migration_stage import AIcUpgradeMigrationStage

class AIcUpgradeMigrationCoordinator:
    """Validate persisted data for a target state and optionally converge it afterwards.

    ``stage`` is strictly side-effect free. It validates configuration persistence and the
    declarative Data Entity schema model of the target component set. Data Entity persistence
    itself is intentionally not accessed here; generic data-storage capabilities are defined in a
    later AAC layer.

    ``converge`` therefore performs only best-effort configuration persistence convergence.
    """

    def stage(
        self, core, replacements: tuple[AIcDiscoveredComponent, ...]
    ) -> AIcUpgradeMigrationStage:
        diagnostics: list[AIcUpgradeCompatibilityDiagnostic] = []
        configuration: list[AIcStagedConfigurationMigration] = []
        target_schemas = self._target_schema_registry(core, replacements, diagnostics)
        if any(item.blocking for item in diagnostics):
            return AIcUpgradeMigrationStage(diagnostics=tuple(diagnostics))

        for candidate in replacements:
            descriptor = candidate.descriptor
            component_id = descriptor.id
            targets: list[tuple[AIcConfigurationTarget, object]] = []
            if descriptor.component_configuration_schema is not None:
                targets.append((
                    AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, component_id),
                    descriptor.component_configuration_schema,
                ))
            for instance in core.instances.find(component_id=component_id):
                try:
                    provider_definition = descriptor.provider(instance.provider_definition_id)
                except KeyError:
                    continue
                if provider_definition.configuration_schema is not None:
                    targets.append((
                        AIcConfigurationTarget(
                            AInConfigurationTargetKind.PROVIDER_INSTANCE, component_id, instance.id
                        ),
                        provider_definition.configuration_schema,
                    ))

            for target, declaration in targets:
                for resolved_scope in core.active_configuration_scopes:
                    for binding in resolved_scope.configuration_providers:
                        provider = core.configuration_providers.get(binding.configuration_provider_id)
                        request = AIcConfigurationProviderRequest(
                            target, resolved_scope.configuration_scope, core.application_context
                        )
                        try:
                            snapshot = provider.snapshot(request)
                        except Exception as exc:
                            diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                component_id,
                                f"cannot inspect configuration provider {binding.configuration_provider_id!r} "
                                f"for {target.key}: {exc}",
                            ))
                            continue
                        if snapshot is None:
                            continue
                        try:
                            assessment = core.configuration_migrations.compatibility.assess(
                                snapshot.payload.configuration_schema_id,
                                snapshot.payload.configuration_schema_version,
                                declaration,
                            )
                        except Exception as exc:
                            diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                component_id, f"cannot assess configuration {target.key}: {exc}"
                            ))
                            continue

                        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED:
                            diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                component_id,
                                f"configuration {target.key} in scope "
                                f"{resolved_scope.configuration_scope.type}/{resolved_scope.configuration_scope.id} "
                                f"uses an unsupported persisted representation and will be unavailable to the target; "
                                f"resolution will continue with other providers/defaults/UNDEFINED: "
                                f"{'; '.join(assessment.diagnostics)}",
                                blocking=False, code="CONFIGURATION_UNSUPPORTED",
                            ))
                            continue

                        migrated = None
                        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.TRANSFORMED:
                            try:
                                migrated = core.configuration_migrations.migrate_to_write_version(
                                    snapshot.payload, declaration,
                                    written_by_component_version=descriptor.version,
                                )
                                if declaration.resource_name is not None:
                                    target_schemas.normalize(
                                        declaration.resource_name, migrated.values, apply_defaults=False
                                    )
                            except Exception as exc:
                                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                    component_id,
                                    f"configuration {target.key} cannot be transformed safely and will be unavailable "
                                    f"to the target component: {exc}",
                                    blocking=False, code="CONFIGURATION_TRANSFORMATION_FAILED",
                                ))
                                continue
                        else:
                            # DIRECT payloads participate exactly as stored.  A migration path, when
                            # present, is optional persistence convergence and does not change runtime
                            # interpretation.  Validate the current write representation when possible.
                            try:
                                if assessment.at_target_write_version and declaration.resource_name is not None:
                                    target_schemas.normalize(
                                        declaration.resource_name, snapshot.payload.values, apply_defaults=False
                                    )
                                elif not assessment.at_target_write_version:
                                    try:
                                        registered = target_schemas.get_identity(
                                            snapshot.payload.configuration_schema_id,
                                            snapshot.payload.configuration_schema_version,
                                        )
                                    except KeyError:
                                        registered = None
                                    if registered is not None:
                                        target_schemas.normalize(
                                            registered.resource_name, snapshot.payload.values, apply_defaults=False
                                        )
                            except Exception as exc:
                                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                    component_id,
                                    f"configuration {target.key} declares a directly readable representation but "
                                    f"the stored payload is unusable and will be ignored: {exc}",
                                    blocking=False, code="CONFIGURATION_DIRECT_PAYLOAD_INVALID",
                                ))
                                continue

                            # Optional convergence can still be prepared for directly readable old
                            # data.  Failure to prepare it is non-blocking because runtime is DIRECT.
                            if assessment.migration_path:
                                try:
                                    migrated = core.configuration_migrations.migrate_to_write_version(
                                        snapshot.payload, declaration,
                                        written_by_component_version=descriptor.version,
                                    )
                                    if declaration.resource_name is not None:
                                        target_schemas.normalize(
                                            declaration.resource_name, migrated.values, apply_defaults=False
                                        )
                                except Exception as exc:
                                    diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                                        component_id,
                                        f"optional persistence convergence for configuration {target.key} "
                                        f"cannot currently be prepared: {exc}",
                                        blocking=False, code="CONFIGURATION_CONVERGENCE_NOT_AVAILABLE",
                                    ))
                                    migrated = None

                        if migrated is not None and not assessment.at_target_write_version:
                            configuration.append(AIcStagedConfigurationMigration(
                                component_id, binding.configuration_provider_id, request, snapshot.record_revision,
                                snapshot.payload, migrated,
                            ))

                try:
                    effective_diagnostics = self._validate_effective_configuration(
                        core, target, declaration, descriptor.version, target_schemas
                    )
                    diagnostics.extend(
                        AIcUpgradeCompatibilityDiagnostic(
                            component_id, message, blocking=False, code="CONFIGURATION_INPUT_UNAVAILABLE"
                        )
                        for message in effective_diagnostics
                    )
                except Exception as exc:
                    diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                        component_id,
                        f"effective configuration {target.key} is not valid in target state: {exc}",
                    ))

            for support in descriptor.data_entity_support:
                for version in sorted(set(support.readable_versions) | set(support.writable_versions)):
                    try:
                        target_schemas.get_identity(support.schema_id, version)
                    except KeyError:
                        diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                            component_id,
                            f"data entity schema {support.schema_id}/{version} declared by the target component "
                            "is not available in the target canonical schema registry",
                            code="DATA_ENTITY_SCHEMA_MISSING",
                        ))
                for requirement in support.data_entity_requirements:
                    if not requirement.required:
                        continue
                    versions = set(requirement.readable_versions) | set(requirement.writable_versions)
                    if versions and not any(
                        target_schemas.contains_identity(requirement.schema_id, version) for version in versions
                    ):
                        diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                            component_id,
                            f"required data entity schema {requirement.schema_id} has no declared compatible version "
                            f"available in the target canonical schema registry",
                            code="DATA_ENTITY_REQUIREMENT_UNRESOLVED",
                        ))

        return AIcUpgradeMigrationStage(tuple(configuration), tuple(diagnostics))

    @staticmethod
    def _target_schema_registry(core, replacements, diagnostics) -> AIcSchemaRegistry:
        registry = AIcSchemaRegistry()
        registry.restore(core.schemas.snapshot())
        for candidate in replacements:
            if candidate.package is None:
                continue
            try:
                for resource_name, text, source in iter_discovered_resources(candidate, "schemas", suffix=".json"):
                    registry.register_text(resource_name, text, source=source)
            except Exception as exc:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                    candidate.descriptor.id,
                    f"target schema catalog is invalid: {exc}",
                ))
        return registry

    @staticmethod
    def _validate_effective_configuration(core, target, declaration, component_version, target_schemas) -> tuple[str, ...]:
        if declaration.resource_name is None:
            return ()
        property_ids, accepted_scopes, defaults = target_schemas.configuration_property_metadata(
            declaration.resource_name
        )
        read_service = AIcConfigurationReadService(
            core.configuration_providers,
            core.configuration_migrations,
            lambda _target: (declaration, component_version),
            target_schemas,
            persist_migrations=False,
        )
        resolver = AIcConfigurationResolver(core.configuration_providers, read_service)
        effective = resolver.resolve(
            configuration_target=target,
            configuration_scopes=core.active_configuration_scopes,
            property_ids=property_ids,
            accepted_configuration_scope_types=accepted_scopes,
            schema_defaults=defaults,
            context=core.application_context,
        )
        errors = target_schemas.validate_resolved_configuration(declaration.resource_name, effective.plain_values())
        if errors:
            raise ValueError("; ".join(errors))
        return effective.diagnostics

    def converge(self, core, stage: AIcUpgradeMigrationStage) -> AIcPersistenceConvergenceOutcome:
        """Try to persist validated migrations independently, never rolling back component cutover."""
        if any(item.blocking for item in stage.diagnostics):
            raise ValueError("cannot converge an incompatible persisted-data stage")
        configuration_persisted = 0
        configuration_deferred = 0
        diagnostics: list[str] = []

        for item in stage.configuration:
            try:
                provider = core.configuration_providers.get(item.configuration_provider_id)
                persistence_capabilities = set(provider.persistence_capabilities(item.request))
                if AInPersistenceCapability.SINGLE_RECORD_CAS not in persistence_capabilities:
                    configuration_deferred += 1
                    diagnostics.append(
                        f"configuration {item.request.configuration_target.key} at provider "
                        f"{item.configuration_provider_id!r} remains in its source schema "
                        "(provider is read-only or does not support conditional record replacement)"
                    )
                    continue
                provider.replace_payload(
                    item.request, item.target_payload, expected_record_revision=item.source_revision
                )
                configuration_persisted += 1
            except Exception as exc:
                configuration_deferred += 1
                diagnostics.append(
                    f"configuration convergence deferred for {item.request.configuration_target.key} at "
                    f"provider {item.configuration_provider_id!r}: {exc}"
                )


        return AIcPersistenceConvergenceOutcome(
            configuration_persisted,
            configuration_deferred,
            tuple(diagnostics),
        )

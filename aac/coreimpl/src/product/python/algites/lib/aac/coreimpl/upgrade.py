from __future__ import annotations

from dataclasses import dataclass, replace

from algites.lib.aac.coreintf.configuration import (
    AInConfigurationTargetKind,
    AIcConfigurationPersistedPayload,
    AIcConfigurationProviderRequest,
    AIcConfigurationTarget,
)
from algites.lib.aac.coreintf.instances import AIcBinding, AIcProviderInstance, AInProviderInstanceState
from algites.lib.aac.coreintf.migration import AInSchemaRuntimeInterpretation
from algites.lib.aac.coreintf.persistence import AInPersistenceCapability
from algites.lib.aac.coreintf.readiness import AInReadinessState
from algites.lib.aac.coreintf.packages import (
    AIcComponentUpgradePlan,
    AIcComponentUpgradeReplacement,
    AIcUpgradeCompatibilityDiagnostic,
)

from .configuration import AIcConfigurationReadService, AIcConfigurationResolver
from .contracts import AIcActiveContractCatalog
from .descriptor import AIcDiscoveredComponent, iter_discovered_resources, read_discovered_resource
from .errors import AIxBindingResolutionError
from .resolution import AIcBindingResolver, validate_instance_dag
from .readiness import AIcReadinessEvaluator
from .schemas import AIcSchemaRegistry


class AIcTargetStateUpgradeAnalyzer:
    """Build and validate one complete hypothetical component target state.

    The analyzer is deliberately side-effect free with respect to the live Core state.  It
    rebuilds the active contract catalog from the complete target component set and projects
    provider instances onto the target descriptors before resolving mandatory requirements.
    No intermediate one-component-at-a-time state is required to be valid.
    """

    def analyze(self, core, application_scope_id: str, replacements: tuple[AIcDiscoveredComponent, ...]) -> AIcComponentUpgradePlan:
        replacement_by_id = {item.descriptor.id: item for item in replacements}
        if len(replacement_by_id) != len(replacements):
            raise ValueError("upgrade candidates must be unique by component id")

        target_components = {component_id: item.discovered for component_id, item in core._installed.items()}
        replacement_records: list[AIcComponentUpgradeReplacement] = []
        diagnostics: list[AIcUpgradeCompatibilityDiagnostic] = []
        for component_id, candidate in replacement_by_id.items():
            previous = core._installed.get(component_id)
            if previous is None:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(component_id, "component is not currently installed"))
                continue
            if candidate.descriptor.version == previous.descriptor.version:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                    component_id,
                    f"target version {candidate.descriptor.version} must differ from installed version {previous.descriptor.version}",
                ))
                continue
            target_components[component_id] = candidate
            replacement_records.append(AIcComponentUpgradeReplacement(
                component_id, previous.descriptor.version, candidate.descriptor.version
            ))

        if diagnostics:
            return AIcComponentUpgradePlan(application_scope_id, tuple(replacement_records), False, tuple(diagnostics))

        try:
            catalog = self._target_contract_catalog(tuple(target_components.values()))
        except Exception as exc:
            # Contract conflicts are target-state failures too; associate them with all replacements
            # because the conflicting definition can be supplied by either side of the transaction.
            for item in replacement_records:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(item.component_id, f"target contract catalog is invalid: {exc}"))
            return AIcComponentUpgradePlan(application_scope_id, tuple(replacement_records), False, tuple(diagnostics))

        descriptors = {component_id: item.descriptor for component_id, item in target_components.items()}
        instances, instance_diagnostics = self._target_instances(core, descriptors)
        diagnostics.extend(instance_diagnostics)
        if diagnostics:
            return AIcComponentUpgradePlan(application_scope_id, tuple(replacement_records), False, tuple(diagnostics))

        resolver = AIcBindingResolver(catalog)
        resolved: list[AIcBinding] = []
        for consumer in sorted(instances, key=lambda item: item.id):
            descriptor = descriptors[consumer.component_id]
            provider = descriptor.provider(consumer.provider_definition_id)
            for requirement in provider.requirements:
                candidates = instances
                preference = core.preferences.get(consumer.id, requirement.id)
                if preference is not None:
                    selected_ids = set(preference.provider_instance_ids)
                    candidates = tuple(item for item in instances if item.id in selected_ids)
                    missing = selected_ids - {item.id for item in candidates}
                    if missing:
                        diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                            consumer.component_id,
                            f"binding preference references provider instances absent from target state: {sorted(missing)}",
                            consumer.id, requirement.id, requirement.capability_id, requirement.versions,
                        ))
                        continue
                try:
                    bindings = resolver.resolve(consumer.id, requirement, candidates, tuple(resolved))
                except AIxBindingResolutionError as exc:
                    if not requirement.mandatory:
                        continue
                    matching = tuple(item for item in instances if item.capability_id == requirement.capability_id and item.id != consumer.id)
                    provider_versions = tuple(sorted({version for item in matching for version in item.capability_versions}))
                    provider_components = tuple(sorted({item.component_id for item in matching}))
                    diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                        consumer.component_id,
                        str(exc),
                        consumer.id,
                        requirement.id,
                        requirement.capability_id,
                        requirement.versions,
                        provider_versions,
                        provider_components,
                    ))
                    continue
                resolved.extend(bindings)

        if not diagnostics:
            try:
                validate_instance_dag(tuple(resolved))
            except Exception as exc:
                for item in replacement_records:
                    diagnostics.append(AIcUpgradeCompatibilityDiagnostic(item.component_id, f"target provider graph is invalid: {exc}"))

        if not diagnostics:
            migration_stage = AIcUpgradeMigrationCoordinator().stage(core, replacements)
            diagnostics.extend(migration_stage.diagnostics)

        if not any(item.blocking for item in diagnostics):
            diagnostics.extend(self._target_readiness_diagnostics(
                core, application_scope_id, replacements, descriptors, instances
            ))

        return AIcComponentUpgradePlan(
            application_scope_id,
            tuple(replacement_records),
            not any(item.blocking for item in diagnostics),
            tuple(diagnostics),
        )

    @staticmethod
    def _target_readiness_diagnostics(core, application_scope_id, replacements, descriptors, instances):
        diagnostics: list[AIcUpgradeCompatibilityDiagnostic] = []
        schema_diagnostics: list[AIcUpgradeCompatibilityDiagnostic] = []
        target_schemas = AIcUpgradeMigrationCoordinator._target_schema_registry(core, replacements, schema_diagnostics)
        diagnostics.extend(schema_diagnostics)
        if any(item.blocking for item in diagnostics):
            return tuple(diagnostics)

        def resolve(target, declaration, component_version):
            if declaration is None or declaration.resource_name is None:
                return core.resolve_scoped_configuration(configuration_target=target, property_ids=())
            property_ids, accepted, defaults = target_schemas.configuration_property_metadata(declaration.resource_name)
            read_service = AIcConfigurationReadService(
                core.configuration_providers, core.configuration_migrations,
                lambda _target: (declaration, component_version), target_schemas, persist_migrations=False,
            )
            resolver = AIcConfigurationResolver(core.configuration_providers, read_service)
            return resolver.resolve(
                configuration_target=target, configuration_scopes=core.active_configuration_scopes,
                property_ids=property_ids, accepted_configuration_scope_types=accepted,
                schema_defaults=defaults, context=core.application_context,
            )

        for instance in instances:
            descriptor = descriptors[instance.component_id]
            provider = descriptor.provider(instance.provider_definition_id)
            if not provider.readiness_requirements:
                continue
            component_target = AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, descriptor.id)
            provider_target = AIcConfigurationTarget(
                AInConfigurationTargetKind.PROVIDER_INSTANCE, descriptor.id, instance.id
            )
            try:
                component_configuration = resolve(
                    component_target, descriptor.component_configuration_schema, descriptor.version
                )
                provider_configuration = resolve(
                    provider_target, provider.configuration_schema, descriptor.version
                )
                report = AIcReadinessEvaluator.static_provider_readiness(
                    application_scope_id, descriptor.id, instance.id, provider,
                    component_configuration, provider_configuration, core.application_context, instance.configuration,
                )
            except Exception as exc:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                    descriptor.id,
                    f"target readiness could not be evaluated for provider instance {instance.id!r}: {exc}",
                    consumer_instance_id=instance.id, capability_id=provider.capability_id,
                    blocking=False, code="READINESS_EVALUATION_WARNING",
                ))
                continue
            if report.state is AInReadinessState.READY:
                continue
            detail = "; ".join(reason.message for reason in report.reasons)
            diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                descriptor.id,
                f"target provider {instance.name!r} readiness is {report.state.value}: {detail}",
                consumer_instance_id=instance.id, capability_id=provider.capability_id,
                blocking=False, code=f"READINESS_{report.state.value}",
            ))
        return tuple(diagnostics)

    @staticmethod
    def _target_contract_catalog(components: tuple[AIcDiscoveredComponent, ...]) -> AIcActiveContractCatalog:
        catalog = AIcActiveContractCatalog(AIcSchemaRegistry())
        catalog.admit_builtin_contracts()
        for discovered in components:
            if discovered.descriptor.contract_resources and discovered.package is None:
                raise ValueError(f"component {discovered.descriptor.id!r} has contract resources but no package identity")
            for resource_name in discovered.descriptor.contract_resources:
                text, source = read_discovered_resource(discovered, resource_name)
                catalog.admit_text(text, source=source)
        return catalog

    @staticmethod
    def _target_instances(core, descriptors):
        diagnostics: list[AIcUpgradeCompatibilityDiagnostic] = []
        result: list[AIcProviderInstance] = []
        existing_keys: set[tuple[str, str, str]] = set()
        for instance in core.instances.all():
            descriptor = descriptors.get(instance.component_id)
            if descriptor is None:
                continue
            try:
                provider = descriptor.provider(instance.provider_definition_id)
            except KeyError:
                diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                    instance.component_id,
                    f"target component removes provider definition {instance.provider_definition_id!r} while provider instance {instance.id!r} still exists",
                    consumer_instance_id=instance.id,
                ))
                continue
            projected = replace(
                instance,
                capability_id=provider.capability_id,
                capability_versions=provider.capability_versions,
                implementation_class=provider.implementation_class,
                configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
                state=AInProviderInstanceState.INACTIVE,
            )
            result.append(projected)
            existing_keys.add((instance.component_id, instance.provider_definition_id, instance.name))

        # Initial instances newly introduced by a target descriptor must participate in preflight.
        for component_id, descriptor in descriptors.items():
            for provider in descriptor.providers:
                for index, declared in enumerate(provider.initial_instances):
                    key = (component_id, provider.id, declared.name)
                    if key in existing_keys:
                        continue
                    result.append(AIcProviderInstance(
                        id=f"_AAC.upgrade-preflight:{component_id}:{provider.id}:{index}",
                        component_id=component_id,
                        provider_definition_id=provider.id,
                        name=declared.name,
                        capability_id=provider.capability_id,
                        capability_versions=provider.capability_versions,
                        implementation_class=provider.implementation_class,
                        configuration=dict(declared.configuration),
                        configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
                        state=AInProviderInstanceState.CONFIGURED,
                    ))
                    existing_keys.add(key)
        return tuple(result), tuple(diagnostics)


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


@dataclass(frozen=True, slots=True)
class AIcUpgradeMigrationStage:
    """Side-effect-free persisted-data compatibility result for a target component set."""

    configuration: tuple[AIcStagedConfigurationMigration, ...] = ()
    diagnostics: tuple[AIcUpgradeCompatibilityDiagnostic, ...] = ()

    @property
    def compatible(self) -> bool:
        return not any(item.blocking for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class AIcPersistenceConvergenceOutcome:
    """Best-effort persistence convergence performed outside the component transaction."""

    configuration_persisted: int = 0
    configuration_deferred: int = 0
    diagnostics: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.configuration_deferred == 0


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

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

from .aic_upgrade_migration_coordinator import AIcUpgradeMigrationCoordinator

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
                    matching = tuple(
                        item for item in instances
                        if item.id != consumer.id and item.supports_capability(requirement.capability_id)
                    )
                    provider_versions = tuple(sorted({
                        version
                        for item in matching
                        for version in item.capability(requirement.capability_id).versions
                    }))
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
                    consumer_instance_id=instance.id, capability_id=None,
                    blocking=False, code="READINESS_EVALUATION_WARNING",
                ))
                continue
            if report.state is AInReadinessState.READY:
                continue
            detail = "; ".join(reason.message for reason in report.reasons)
            diagnostics.append(AIcUpgradeCompatibilityDiagnostic(
                descriptor.id,
                f"target provider {instance.name!r} readiness is {report.state.value}: {detail}",
                consumer_instance_id=instance.id, capability_id=None,
                blocking=False, code=f"READINESS_{report.state.value}",
            ))
        return tuple(diagnostics)

    @staticmethod
    def _target_contract_catalog(components: tuple[AIcDiscoveredComponent, ...]) -> AIcActiveContractCatalog:
        catalog = AIcActiveContractCatalog(AIcSchemaRegistry())
        catalog.admit_builtin_contracts()
        for discovered in components:
            if (discovered.descriptor.capability_group_resources or discovered.descriptor.contract_resources) and discovered.package is None:
                raise ValueError(
                    f"component {discovered.descriptor.id!r} has capability-group/contract resources but no package identity"
                )
            for resource_name in discovered.descriptor.capability_group_resources:
                text, source = read_discovered_resource(discovered, resource_name)
                catalog.groups.admit_text(text, source=source)
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
                    f"target component removes capability provider definition {instance.provider_definition_id!r} while provider instance {instance.id!r} still exists",
                    consumer_instance_id=instance.id,
                ))
                continue
            projected = replace(
                instance,
                capabilities=provider.capabilities,
                implementation_class=provider.implementation_class_for("python"),
                configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
                state=AInProviderInstanceState.INACTIVE,
            )
            result.append(projected)
            existing_keys.add((instance.component_id, instance.provider_definition_id, instance.name))

        # Initial instances newly introduced by a target descriptor must participate in preflight.
        for component_id, descriptor in descriptors.items():
            for provider in descriptor.capability_providers:
                for index, declared in enumerate(provider.initial_instances):
                    key = (component_id, provider.id, declared.name)
                    if key in existing_keys:
                        continue
                    result.append(AIcProviderInstance(
                        id=f"_AAC.upgrade-preflight:{component_id}:{provider.id}:{index}",
                        component_id=component_id,
                        provider_definition_id=provider.id,
                        name=declared.name,
                        capabilities=provider.capabilities,
                        implementation_class=provider.implementation_class_for("python"),
                        access_mode=declared.access_mode,
                        configuration=dict(declared.configuration),
                        configuration_schema=provider.configuration_schema.resource_name if provider.configuration_schema is not None else None,
                        state=AInProviderInstanceState.CONFIGURED,
                    ))
                    existing_keys.add(key)
        return tuple(result), tuple(diagnostics)

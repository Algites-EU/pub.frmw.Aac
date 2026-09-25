from __future__ import annotations
import json
from dataclasses import replace
from typing import Mapping
from eu.algites.frmw.aac.core.catalog.api import AIcCatalogQuery
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationMutationOperation, AInConfigurationTargetKind, AIcConfigurationChange,
    AIcConfigurationChangeSet, AIcConfigurationProviderRequest, AIcConfigurationTarget,
)
from eu.algites.frmw.aac.core.context.api import AIcConfigurationScope
from eu.algites.frmw.aac.core.instances.api import AIcBindingPreference
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText, normalize_display_text
from eu.algites.frmw.aac.core.packages.api import AInStoredPackageState
from eu.algites.frmw.aac.core.solver.api import AIcTargetStateRequest, AIcTargetStateSolution, AIcTargetStateSolverResult
from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationBinding,
    AIcObservationSelector,
    AInObservationPhase,
)
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
from eu.algites.frmw.aac.ui.api import (
    AIiAacUiController,
    AIcUiConfigurationProviderOption,
    AIcUiConfigurationScope,
    AInUiFieldType,
    AIcUiBinding,
    AIcUiChoice,
    AIcUiComponent,
    AIcUiField,
    AIcUiFieldGroup,
    AIcUiForm,
    AIcUiObservationBinding,
    AIcUiObservationSelector,
    AIcUiProviderInstance,
    AIcUiRequirement,
    AIcUiRequirementEditor,
    AIcUiEntitlementPermission,
    AIcUiEntitlementStatus,
    AIcUiCatalogPackageArtifact,
    AIcUiPackageArtifact,
    AIcUiUpgradeDiagnostic,
    AIcUiUpgradePlan,
    AIcUiUpgradeReplacement,
)

def _display_text(value: AIcDisplayText | None) -> AIcDisplayText | None:
    return value

def _display_text_value(value: AIcDisplayText | None) -> str | None:
    return None if value is None else value.fallback

def _schema_display_text(value: object | None) -> AIcDisplayText | None:
    if value is None:
        return None
    if isinstance(value, (str, Mapping, AIcDisplayText)):
        return normalize_display_text(value)
    return AIcDisplayText(text=str(value))

def _field_from_schema(field_id: str, raw: Mapping[str, object], value: object, required: bool) -> AIcUiField:
    title = _schema_display_text(raw.get("x-aac-name")) or AIcDisplayText(text=str(raw.get("title", field_id.replace("_", " ").title())))
    description = _schema_display_text(raw.get("x-aac-description"))
    if description is None and raw.get("description") is not None:
        description = AIcDisplayText(text=str(raw["description"]))
    ui_type = str(raw.get("x-aac-ui-type", "")).upper()
    secret = bool(raw.get("x-aac-secret", False))
    enum_values = raw.get("enum")
    choices = tuple(AIcUiChoice(item, AIcDisplayText(text=str(item))) for item in enum_values) if isinstance(enum_values, list) else ()
    if ui_type in AInUiFieldType.__members__:
        field_type = AInUiFieldType[ui_type]
    elif choices:
        field_type = AInUiFieldType.ENUM
    else:
        schema_type = raw.get("type")
        field_type = {
            "integer": AInUiFieldType.INTEGER,
            "number": AInUiFieldType.NUMBER,
            "boolean": AInUiFieldType.BOOLEAN,
            "string": AInUiFieldType.STRING,
        }.get(str(schema_type), AInUiFieldType.JSON)
    if secret and field_type is AInUiFieldType.STRING:
        field_type = AInUiFieldType.SECRET_REFERENCE
    if value is None and "default" in raw:
        value = raw["default"]
    if field_type is AInUiFieldType.JSON and value is not None and not isinstance(value, str):
        value = json.loads(json.dumps(value))
    accepted_scopes_raw = raw.get("x-aac-configuration-scopes", ())
    accepted_scopes = tuple(str(item) for item in accepted_scopes_raw) if isinstance(accepted_scopes_raw, list) else ()
    return AIcUiField(
        id=field_id, label=title, field_type=field_type, value=value, required=required,
        read_only=False, description=description, choices=choices, multiple=False, secret=secret,
        metadata=dict(raw), accepted_configuration_scope_types=accepted_scopes,
    )

class AIcCoreUiController(AIiAacUiController):
    """AAC Core-backed implementation of the technology-neutral administration contract."""

    def __init__(self, core: AIcApplicationComponentCore, actor_context: Mapping[str, object] | None = None) -> None:
        self.core = core
        self.actor_context = dict(actor_context or {})

    def components(self) -> tuple[AIcUiComponent, ...]:
        values = []
        for installed in self.core.installed_components():
            descriptor = installed.descriptor
            scope_ids = self.core.active_application_scope_ids()
            scope_id = scope_ids[0] if scope_ids else None
            readiness = None
            if scope_id is not None:
                try:
                    readiness = self.core.refresh_component_readiness(scope_id, descriptor.id)
                except (KeyError, RuntimeError):
                    readiness = self.core.component_readiness(scope_id, descriptor.id)
            values.append(AIcUiComponent(
                descriptor.id,
                descriptor.version,
                tuple(provider.id for provider in descriptor.capability_providers),
                sum(len(item.permissions) for item in descriptor.provided_capability_entitlements),
                name=_display_text(descriptor.name),
                description=_display_text(descriptor.description),
                origin=installed.origin.value,
                readiness_state=(readiness.state.value if readiness is not None else None),
                readiness_reasons=tuple(reason.message for reason in readiness.reasons) if readiness is not None else (),
            ))
        return tuple(values)

    def provider_instances(self, component_id: str | None = None) -> tuple[AIcUiProviderInstance, ...]:
        instances = self.core.instances.find(component_id=component_id) if component_id else self.core.instances.all()
        return tuple(self._instance(value) for value in sorted(instances, key=lambda item: (item.component_id, item.name, item.id)))

    def create_provider_instance(self, component_id: str, provider_definition_id: str, name: str = "default") -> AIcUiProviderInstance:
        return self._instance(self.core.create_provider_instance(component_id, provider_definition_id, name=name))

    def rename_provider_instance(self, instance_id: str, name: str) -> AIcUiProviderInstance:
        return self._instance(self.core.rename_provider_instance(instance_id, name))

    def remove_provider_instance(self, instance_id: str) -> None:
        self.core.remove_provider_instance(instance_id)

    def provider_configuration_form(self, instance_id: str) -> AIcUiForm:
        instance = self.core.instances.get(instance_id)
        effective = self.core.resolve_provider_scoped_configuration(instance_id)
        fields: list[AIcUiField] = []
        if instance.configuration_schema is None:
            fields.append(AIcUiField(
                "configuration", "Configuration", AInUiFieldType.JSON,
                value=effective.plain_values() or dict(instance.configuration), description="Provider configuration as JSON object.",
            ))
        else:
            schema = self.core.schemas.get(instance.configuration_schema).schema
            properties = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
            required = set(schema.get("required", ())) if isinstance(schema, Mapping) else set()
            for field_id, raw in properties.items():
                if not isinstance(raw, Mapping):
                    continue
                resolved = effective.values.get(str(field_id))
                value = resolved.value if resolved is not None else instance.configuration.get(field_id)
                field = _field_from_schema(str(field_id), raw, value, field_id in required)
                if resolved is not None:
                    provenance = resolved.provenance
                    field = replace(
                        field,
                        effective_configuration_scope=(
                            AIcUiConfigurationScope(provenance.configuration_scope.type, provenance.configuration_scope.id)
                            if provenance is not None else None
                        ),
                        effective_configuration_provider_id=(provenance.configuration_provider_id if provenance is not None else None),
                        value_source_kind=resolved.source_kind.value,
                        policy_modes=tuple(
                            {"mode": item.mode.value, "value": item.value} for item, _ in resolved.effective_policy.provenance
                        ),
                    )
                fields.append(field)
        target = AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, instance.component_id, instance.id)
        options: list[AIcUiConfigurationProviderOption] = []
        scopes = []
        for item in self.core.active_configuration_scopes:
            scope_ui = AIcUiConfigurationScope(
                item.configuration_scope.type, item.configuration_scope.id, editable=False, policy_authority=item.policy_authority
            )
            scopes.append(scope_ui)
            for binding in item.configuration_providers:
                access = self.core.configuration_provider_access(
                    binding.configuration_provider_id, item.configuration_scope, target, self.actor_context
                )
                provider = self.core.configuration_providers.get(binding.configuration_provider_id)
                snapshot = provider.snapshot(AIcConfigurationProviderRequest(target, item.configuration_scope, self.actor_context))
                option_scope = replace(scope_ui, editable=any(
                    capability.value.startswith("WRITE_") for capability in access.authorized_capabilities
                ))
                options.append(AIcUiConfigurationProviderOption(
                    option_scope, binding.configuration_provider_id,
                    tuple(item.value for item in access.technical_capabilities),
                    tuple(item.value for item in access.authorized_capabilities),
                    snapshot.record_revision if snapshot is not None else None, access.diagnostics,
                ))
        return AIcUiForm(
            id=f"provider-instance:{instance.id}",
            title=f"Configure {instance.name}",
            groups=(AIcUiFieldGroup("configuration", "Configuration", tuple(fields)),),
            configuration_scopes=tuple(scopes),
            active_configuration_profile_id=(
                self.core.configuration_bootstrap.default_configuration_profile_id
                if self.core.configuration_bootstrap is not None else None
            ),
            configuration_provider_options=tuple(options),
            description=f"{instance.component_id} / {instance.provider_definition_id} / {instance.id}",
        )

    def update_provider_configuration(self, instance_id: str, values: Mapping[str, object]) -> AIcUiProviderInstance:
        if set(values) == {"configuration"} and isinstance(values.get("configuration"), Mapping):
            values = values["configuration"]
        return self._instance(self.core.configure_provider_instance(instance_id, dict(values)))

    def update_provider_scoped_configuration(
        self, instance_id: str, configuration_scope_type: str, configuration_scope_id: str | None,
        configuration_provider_id: str, values: Mapping[str, object], expected_record_revision: str | int | None = None,
    ) -> AIcUiProviderInstance:
        instance = self.core.instances.get(instance_id)
        if set(values) == {"configuration"} and isinstance(values.get("configuration"), Mapping):
            values = values["configuration"]
        target = AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, instance.component_id, instance.id)
        changes = tuple(AIcConfigurationChange(
            str(key), AInConfigurationMutationOperation.SET_VALUE, value=value, has_value=True
        ) for key, value in values.items())
        if not changes:
            return self._instance(instance)
        self.core.apply_configuration_changes(AIcConfigurationChangeSet(
            AIcConfigurationScope(configuration_scope_type, configuration_scope_id), configuration_provider_id, target, changes,
            expected_record_revision=expected_record_revision, actor_context=self.actor_context,
        ))
        return self._instance(instance)

    def bindings(self) -> tuple[AIcUiBinding, ...]:
        return tuple(AIcUiBinding(
            value.consumer_instance_id, value.requirement_id, value.provider_instance_id,
            value.capability_id, value.capability_version,
        ) for value in self.core.bindings.all())

    def requirements(self) -> tuple[AIcUiRequirement, ...]:
        values = []
        for consumer in self.core.instances.all():
            descriptor = self.core.installed(consumer.component_id).descriptor
            provider = descriptor.provider(consumer.provider_definition_id)
            for requirement in provider.requirements:
                preference = self.core.preferences.get(consumer.id, requirement.id)
                selected = preference.provider_instance_ids if preference else tuple(
                    binding.provider_instance_id for binding in self.core.bindings.for_consumer(consumer.id)
                    if binding.requirement_id == requirement.id
                )
                grant = self.core.component_authorization_grant(consumer.id, requirement.id)
                values.append(AIcUiRequirement(
                    consumer.id, consumer.name, requirement.id, requirement.capability_id, requirement.versions,
                    requirement.cardinality.value, requirement.mandatory, tuple(selected),
                    requirement.requested_authorizations, tuple(() if grant is None else grant.permission_ids),
                    _display_text(requirement.name), _display_text(requirement.description),
                ))
        return tuple(values)

    def requirement_editor(self, consumer_instance_id: str, requirement_id: str) -> AIcUiRequirementEditor:
        consumer = self.core.instances.get(consumer_instance_id)
        descriptor = self.core.installed(consumer.component_id).descriptor
        provider = descriptor.provider(consumer.provider_definition_id)
        requirement = next((item for item in provider.requirements if item.id == requirement_id), None)
        if requirement is None:
            raise KeyError(requirement_id)
        preference = self.core.preferences.get(consumer_instance_id, requirement_id)
        selected = preference.provider_instance_ids if preference else tuple(
            binding.provider_instance_id for binding in self.core.bindings.for_consumer(consumer_instance_id)
            if binding.requirement_id == requirement_id
        )
        choices = []
        for candidate in self.core.instances.find(capability_id=requirement.capability_id):
            if candidate.id == consumer_instance_id:
                continue
            if not set(candidate.capability(requirement.capability_id).versions).intersection(requirement.versions):
                continue
            choices.append(AIcUiChoice(candidate.id, f"{candidate.name} — {candidate.component_id} [{candidate.id}]"))
        grant = self.core.component_authorization_grant(consumer_instance_id, requirement_id)
        granted = tuple(() if grant is None else grant.permission_ids)
        authorization_choices = []
        seen_permissions = set()
        versions = requirement.versions or self.core.contracts.versions(requirement.capability_id)
        for version in sorted(versions, reverse=True):
            if not self.core.contracts.contains(requirement.capability_id, version):
                continue
            contract = self.core.contracts.get(requirement.capability_id, version)
            for permission in contract.authorization_permissions:
                if permission.id in seen_permissions or permission.id not in requirement.requested_authorizations:
                    continue
                seen_permissions.add(permission.id)
                authorization_choices.append(AIcUiChoice(
                    permission.id, _display_text(permission.name) or permission.id, _display_text(permission.description)
                ))
        return AIcUiRequirementEditor(
            consumer_instance_id, requirement.id, requirement.capability_id, requirement.versions,
            requirement.cardinality.value, requirement.mandatory, tuple(selected), tuple(choices),
            requirement.requested_authorizations, granted, tuple(authorization_choices),
        )

    def set_requirement_providers(self, consumer_instance_id: str, requirement_id: str, provider_instance_ids: tuple[str, ...]) -> None:
        editor = self.requirement_editor(consumer_instance_id, requirement_id)
        if editor.cardinality == "SINGLE" and len(provider_instance_ids) > 1:
            raise ValueError("SINGLE requirement accepts at most one provider instance")
        if editor.mandatory and not provider_instance_ids:
            raise ValueError("mandatory requirement must select a provider instance")
        self.core.set_binding_preference(AIcBindingPreference(consumer_instance_id, requirement_id, provider_instance_ids))

    def set_requirement_authorizations(
        self, consumer_instance_id: str, requirement_id: str, permission_ids: tuple[str, ...]
    ) -> None:
        self.core.set_component_authorization_grant(
            consumer_instance_id, requirement_id, permission_ids, approved_by="AAC_UI"
        )


    def entitlement_status(self, component_id: str) -> AIcUiEntitlementStatus:
        descriptor = self.core.installed(component_id).descriptor
        context = self.core.entitlement.evaluate_component(
            descriptor, licensing_scopes=self.core.active_licensing_scopes, context=self.core.application_context
        )
        rows = []
        declarations = {
            (item.capability_id, item.capability_version): item for item in descriptor.provided_capability_entitlements
        }
        for capability in context.capabilities:
            declaration = declarations.get((capability.capability_id, capability.capability_version))
            for permission_id, effective in capability.permissions.items():
                meta = None if declaration is None else declaration.permission(permission_id)
                provenance = effective.provenance[0] if effective.provenance else None
                rows.append(AIcUiEntitlementPermission(
                    component_id=component_id, capability_id=capability.capability_id,
                    capability_version=capability.capability_version, permission_id=permission_id,
                    effective_from=effective.effective_from, effective_until=effective.effective_until,
                    licensing_scope=(provenance.licensing_scope.key if provenance is not None else None),
                    entitlement_id=(provenance.entitlement_id if provenance is not None else None),
                    issuer_id=(provenance.issuer_id if provenance is not None else None),
                    name=(_display_text(meta.name) if meta is not None else permission_id),
                    description=(_display_text(meta.description) if meta is not None else None),
                    implicit=effective.implicit,
                ))
        return AIcUiEntitlementStatus(component_id, tuple(rows), context.next_transition_at, context.diagnostics)

    def observation_bindings(self) -> tuple[AIcUiObservationBinding, ...]:
        return tuple(AIcUiObservationBinding(
            binding.observer_instance_id,
            tuple(AIcUiObservationSelector(
                selector.capability, selector.versions, selector.operations,
                tuple(phase.value for phase in selector.phases),
            ) for selector in binding.selectors),
        ) for binding in self.core.observation_topology.all())

    def put_observation_binding(self, binding: AIcUiObservationBinding) -> None:
        self.core.configure_observer(AIcObservationBinding(
            binding.observer_instance_id,
            tuple(AIcObservationSelector(
                selector.capability, selector.versions, selector.operations,
                tuple(AInObservationPhase(value) for value in selector.phases),
            ) for selector in binding.selectors),
        ))

    def delete_observation_binding(self, observer_instance_id: str) -> None:
        self.core.observation_topology.delete(observer_instance_id)

    def catalog_defaults(self) -> tuple[str | None, str | None]:
        return self.core.catalog_product_id, self.core.catalog_technology_id

    def catalog_packages(
        self, product_id: str, technology_id: str, text: str | None = None
    ) -> tuple[AIcUiCatalogPackageArtifact, ...]:
        entries = self.core.query_catalog(AIcCatalogQuery(product_id, technology_id, text=text or None))
        result = []
        manager = self.core.package_manager
        for entry in entries:
            component = entry.component
            release = entry.release
            licensing_scope_names = {
                item.type: (_display_text_value(item.name) or item.type)
                for item in release.entitlement_licensing_scopes
            }
            provides = tuple(
                f"{item.capability_id} [{', '.join(str(v) for v in item.versions)}]" for item in release.provides
            )
            requires = tuple(
                f"{item.capability_id} [{', '.join(str(v) for v in item.versions)}]" + ("" if item.mandatory else " (optional)")
                for item in release.requires
            )
            entitlement_summary = []
            for declaration in release.provided_capability_entitlements:
                for permission in declaration.permissions:
                    if permission.possible_licensing_scope_types:
                        entitlement_summary.append(
                            f"{declaration.capability_id}/{declaration.capability_version}:{permission.id} "
                            f"[{', '.join(licensing_scope_names.get(scope, scope) for scope in permission.possible_licensing_scope_types)}]"
                        )
                    else:
                        entitlement_summary.append(
                            f"{declaration.capability_id}/{declaration.capability_version}:{permission.id} [included]"
                        )
            for artifact in release.artifacts:
                downloaded = installed = False
                if manager is not None:
                    downloaded = manager.package_store.find(
                        entry.component_id, entry.component_version, artifact.sha256, AInStoredPackageState.DOWNLOADED
                    ) is not None
                    installed = manager.package_store.find(
                        entry.component_id, entry.component_version, artifact.sha256, AInStoredPackageState.INSTALLED
                    ) is not None
                result.append(AIcUiCatalogPackageArtifact(
                    source_id=entry.source_id, product_id=entry.product_id, technology_id=entry.technology_id,
                    component_id=entry.component_id, component_version=entry.component_version, artifact_id=artifact.id,
                    name=_display_text(component.name), description=_display_text(component.description),
                    publisher=(
                        _display_text_value(component.publisher.name) if component.publisher and component.publisher.name
                        else (component.publisher.id if component.publisher else None)
                    ),
                    package_format=artifact.package_format, artifact_uri=artifact.locator.uri, sha256=artifact.sha256,
                    provides=provides, requires=requires, entitlement_summary=tuple(entitlement_summary),
                    entitlement_info_url=component.entitlement_info_url, homepage_url=component.homepage_url,
                    documentation_url=component.documentation_url, icon_url=(component.icon.url if component.icon else None),
                    downloaded=downloaded, installed=installed,
                ))
        return tuple(result)

    @staticmethod
    def _ui_package(package, manager) -> AIcUiPackageArtifact:
        scopes = tuple(sorted(item.application_scope_id for item in manager.selections.references(package)))
        return AIcUiPackageArtifact(
            package.component_id, package.component_version, package.sha256, package.state.value, scopes,
            package.provenance.source_id, package.provenance.signer_identity, package.artifact_path,
        )


    def solve_catalog_target(
        self, application_scope_id: str, identity: tuple[str, str, str, str, int, str]
    ) -> AIcTargetStateSolverResult:
        _, product_id, technology_id, component_id, component_version, _ = identity
        if self.core.catalog_product_id != product_id or self.core.catalog_technology_id != technology_id:
            raise ValueError("selected catalog row does not match active Core catalog scope")
        return self.core.solve_compatible_target_state(
            application_scope_id, (AIcTargetStateRequest.exact(component_id, component_version),)
        )

    def apply_target_state_solution(
        self, application_scope_id: str, solution: AIcTargetStateSolution
    ) -> AIcTargetStateSolution:
        self.core.apply_target_state_solution(application_scope_id, solution)
        return solution

    def download_catalog_package(
        self, identity: tuple[str, str, str, str, int, str]
    ) -> AIcUiPackageArtifact:
        package = self.core.download_catalog_package(*identity)
        return self._ui_package(package, self.core.package_manager)

    def install_catalog_package(
        self, identity: tuple[str, str, str, str, int, str]
    ) -> AIcUiPackageArtifact:
        package = self.core.install_catalog_package(*identity)
        return self._ui_package(package, self.core.package_manager)

    def restore_obsolete_package(self, identity: tuple[str, int, str]) -> AIcUiPackageArtifact:
        if self.core.package_manager is None:
            raise RuntimeError("package management is not configured")
        component_id, version, sha256 = identity
        package = self.core.package_manager.package_store.find(
            component_id, int(version), str(sha256), AInStoredPackageState.OBSOLETE
        )
        if package is None:
            raise KeyError(f"obsolete package artifact not found: {component_id}/{version}/{sha256}")
        restored = self.core.restore_obsolete_package(package)
        return self._ui_package(restored, self.core.package_manager)

    def package_artifacts(self) -> tuple[AIcUiPackageArtifact, ...]:
        if self.core.package_manager is None:
            return ()
        manager = self.core.package_manager
        return tuple(self._ui_package(package, manager) for package in manager.package_store.records())

    def _stored_packages(self, package_identities: tuple[tuple[str, int, str], ...]):
        if self.core.package_manager is None:
            raise RuntimeError("package management is not configured")
        if not package_identities:
            raise ValueError("select at least one target package")
        if len(package_identities) != len(set(package_identities)):
            raise ValueError("target package identities must be unique")
        result = []
        for component_id, version, sha256 in package_identities:
            package = self.core.package_manager.package_store.find(
                component_id, int(version), str(sha256), AInStoredPackageState.INSTALLED
            )
            if package is None:
                raise KeyError(f"installed package artifact not found: {component_id}/{version}/{sha256}")
            result.append(package)
        return tuple(result)

    @staticmethod
    def _upgrade_plan(plan) -> AIcUiUpgradePlan:
        return AIcUiUpgradePlan(
            plan.application_scope_id,
            tuple(AIcUiUpgradeReplacement(
                item.component_id, item.previous_version, item.target_version
            ) for item in plan.replacements),
            plan.compatible,
            tuple(AIcUiUpgradeDiagnostic(
                item.component_id, AIcDisplayText(text=item.message), item.consumer_instance_id, item.requirement_id,
                item.capability_id, item.consumer_versions, item.provider_versions,
                item.available_provider_component_ids, item.blocking, item.code,
            ) for item in plan.diagnostics),
        )

    def plan_package_upgrades(
        self, application_scope_id: str, package_identities: tuple[tuple[str, int, str], ...]
    ) -> AIcUiUpgradePlan:
        packages = self._stored_packages(package_identities)
        return self._upgrade_plan(self.core.plan_stored_package_upgrades(application_scope_id, packages))

    def apply_package_upgrades(
        self, application_scope_id: str, package_identities: tuple[tuple[str, int, str], ...]
    ) -> AIcUiUpgradePlan:
        packages = self._stored_packages(package_identities)
        plan = self.core.plan_stored_package_upgrades(application_scope_id, packages)
        if not plan.compatible:
            return self._upgrade_plan(plan)
        self.core.upgrade_stored_packages(application_scope_id, packages)
        return self._upgrade_plan(plan)

    def _instance(self, value) -> AIcUiProviderInstance:
        scope_ids = self.core.active_application_scope_ids()
        scope_id = scope_ids[0] if scope_ids else None
        readiness = None
        if scope_id is not None:
            try:
                readiness = self.core.refresh_provider_readiness(scope_id, value.id)
            except (KeyError, RuntimeError):
                readiness = self.core.provider_readiness(scope_id, value.id)
        return AIcUiProviderInstance(
            value.id, value.component_id, value.provider_definition_id, value.name,
            tuple((item.id, item.versions) for item in value.capabilities), value.access_mode.value,
            value.state.value, value.configuration_schema,
            readiness_state=(readiness.state.value if readiness is not None else None),
            readiness_reasons=tuple(reason.message for reason in readiness.reasons) if readiness is not None else (),
        )

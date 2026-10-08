from __future__ import annotations

from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_1 import AIigComponentDescriptor_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_1 import AIigComponentDescriptorComponent_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_capabilities_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsCapabilitiesItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_implementation_classes_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsImplementationClassesItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_initial_instances_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsInitialInstancesItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_operations_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_operations_items_interaction_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_operations_items_parameters_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_operations_items_parameters_items_enum_values_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItemsEnumValuesItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_readiness_requirements_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_requirements_items_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_capability_providers_items_runtime_1 import AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_entitlement_licensing_scopes_items_1 import AIigComponentDescriptorComponentEntitlementLicensingScopesItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_provided_capability_entitlements_items_1 import AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_provided_capability_entitlements_items_capability_1 import AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsCapability_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_component_provided_capability_entitlements_items_permissions_items_1 import AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_definition_data_entity_requirement_1 import AIigComponentDescriptorDefinitionDataEntityRequirement_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_definition_data_entity_support_1 import AIigComponentDescriptorDefinitionDataEntitySupport_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_definition_persisted_schema_1 import AIigComponentDescriptorDefinitionPersistedSchema_1
from eu.algites.frmw.aac.core.descriptor.aiig_component_descriptor_definition_schema_migration_step_1 import AIigComponentDescriptorDefinitionSchemaMigrationStep_1
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from zipfile import ZipFile, BadZipFile, is_zipfile
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcPermissionDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcCapabilityEntitlementDescriptor,
    AIcDataEntityRequirementDescriptor,
    AIcDataEntitySupportDescriptor,
    AIcPersistedSchemaDescriptor,
    AIcSchemaMigrationStepDescriptor,
    AInDataEntityAccess,
    AIcInitialProviderInstanceDescriptor,
    AIcLifecycleHooksDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderImplementationClassDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
    AIcCapabilityProviderOperationDescriptor,
    AIcCapabilityProviderOperationInteractionDescriptor,
    AIcOperationParameterDefinitionDescriptor,
    AIcOperationParameterEnumValueDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.instances.api import AInProviderAccessMode
from eu.algites.frmw.aac.core.interaction_types import AInStateResultDeliveryMode
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.readiness.api import AInReadinessRequirementSource, AInReadinessState, AIcReadinessRequirementDescriptor

from .aic_discovered_component import AIcDiscoveredComponent

def _validate_raw_descriptor(raw: Mapping[str, Any], source: str) -> None:
    try:
        schema_text = read_core_schema("component-descriptor_1.jsondef.schema.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
    except Exception as exc:
        raise AIxDescriptorError(f"cannot validate descriptor schema for {source}: {exc}") from exc
    if not errors:
        return
    rendered = []
    for error in errors:
        path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
        rendered.append(f"{path}: {error.message}")
    raise AIxDescriptorError(
        f"{source}: descriptor schema validation failed: " + "; ".join(rendered)
    )

def _parse_persisted_schema(raw_schema: Any) -> AIcPersistedSchemaDescriptor | None:
    if raw_schema is None:
        return None
    if not isinstance(raw_schema, Mapping):
        raise ValueError("persisted schema declaration must be a mapping")
    migrations = tuple(
        AIcSchemaMigrationStepDescriptor(
            from_version=int(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__FROM]),
            to_version=int(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__TO]),
            migrator_id=str(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__MIGRATOR]),
        )
        for item in raw_schema.get(AIigComponentDescriptorDefinitionPersistedSchema_1.SCHEMA_FIELD_NAME__MIGRATIONS, ())
    )
    return AIcPersistedSchemaDescriptor(
        schema_id=str(raw_schema[AIigComponentDescriptorDefinitionPersistedSchema_1.SCHEMA_FIELD_NAME__ID]),
        write_version=int(raw_schema[AIigComponentDescriptorDefinitionPersistedSchema_1.SCHEMA_FIELD_NAME__WRITE_VERSION]),
        readable_versions=tuple(int(v) for v in raw_schema[AIigComponentDescriptorDefinitionPersistedSchema_1.SCHEMA_FIELD_NAME__READABLE_VERSIONS]),
        migrations=migrations,
        resource_name=str(raw_schema[AIigComponentDescriptorDefinitionPersistedSchema_1.SCHEMA_FIELD_NAME__RESOURCE]),
    )

def _parse_requirement(raw_requirement: Mapping[str, Any]) -> AIcConsumerRequirementDescriptor:
    return AIcConsumerRequirementDescriptor(
        id=raw_requirement[AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__ID],
        capability_id=raw_requirement[AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__CAPABILITY],
        versions=tuple(int(v) for v in raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__VERSIONS, ())),
        cardinality=AInConsumerCardinality(raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__CARDINALITY, "single")),
        mandatory=bool(raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__MANDATORY, True)),
        requested_authorizations=tuple(str(v) for v in raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__REQUESTED_AUTHORIZATIONS, ())),
        name=normalize_display_text(raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__NAME)),
        description=normalize_display_text(raw_requirement.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRequirementsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
    )

def _parse_component(component: Mapping[str, Any]) -> AIcComponentDescriptor:
    capability_providers = []
    for raw_provider in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__CAPABILITY_PROVIDERS, ()):
        capabilities = tuple(
            AIcProvidedCapability(
                id=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsCapabilitiesItems_1.SCHEMA_FIELD_NAME__ID]),
                versions=tuple(sorted({int(version) for version in item[AIigComponentDescriptorComponentCapabilityProvidersItemsCapabilitiesItems_1.SCHEMA_FIELD_NAME__VERSIONS]})),
                binding_qualifier_profiles=tuple(dict(value) for value in item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsCapabilitiesItems_1.SCHEMA_FIELD_NAME__BINDING_QUALIFIER_PROFILES, ())),
            )
            for item in raw_provider[AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__CAPABILITIES]
        )
        initial_instances = tuple(
            AIcInitialProviderInstanceDescriptor(
                name=item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsInitialInstancesItems_1.SCHEMA_FIELD_NAME__NAME, "default"),
                configuration=item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsInitialInstancesItems_1.SCHEMA_FIELD_NAME__CONFIGURATION, {}),
                access_mode=AInProviderAccessMode(str(item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsInitialInstancesItems_1.SCHEMA_FIELD_NAME__ACCESS_MODE, "read_write"))),
            )
            for item in raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__INITIAL_INSTANCES, ())
        )
        requirements = tuple(_parse_requirement(item) for item in raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__REQUIREMENTS, ()))
        provider_operations = tuple(
            AIcCapabilityProviderOperationDescriptor(
                capability_id=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__CAPABILITY]),
                capability_version=int(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__CAPABILITY_VERSION]),
                operation_id=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__OPERATION]),
                interaction=AIcCapabilityProviderOperationInteractionDescriptor(
                    supported_state_result_delivery_modes=tuple(
                        AInStateResultDeliveryMode(str(value))
                        for value in item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTION][AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1.SCHEMA_FIELD_NAME__SUPPORTED_STATE_RESULT_DELIVERY_MODES]
                    ),
                    progress_reporting=bool(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTION].get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1.SCHEMA_FIELD_NAME__PROGRESS_REPORTING, False)),
                    cancellation=bool(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTION].get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1.SCHEMA_FIELD_NAME__CANCELLATION, False)),
                    detail_level=bool(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTION].get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1.SCHEMA_FIELD_NAME__DETAIL_LEVEL, False)),
                    reporting_interval=bool(item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTION].get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsInteraction_1.SCHEMA_FIELD_NAME__REPORTING_INTERVAL, False)),
                ),
                parameters=tuple(
                    AIcOperationParameterDefinitionDescriptor(
                        id=str(parameter[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__ID]),
                        name=normalize_display_text(parameter[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__NAME]),
                        description=normalize_display_text(parameter[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__DESCRIPTION]),
                        value_schema=dict(parameter[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__VALUE_SCHEMA]),
                        enum_values=tuple(
                            AIcOperationParameterEnumValueDescriptor(
                                value=enum_item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItemsEnumValuesItems_1.SCHEMA_FIELD_NAME__VALUE),
                                name=normalize_display_text(enum_item[AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItemsEnumValuesItems_1.SCHEMA_FIELD_NAME__NAME]),
                                description=normalize_display_text(enum_item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItemsEnumValuesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                            )
                            for enum_item in parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__ENUM_VALUES, ())
                        ),
                        required=bool(parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__REQUIRED, False)),
                        default=parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__DEFAULT),
                        has_default="Default" in parameter,
                        component_configurable=bool(parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__COMPONENT_CONFIGURABLE, False)),
                        instance_configurable=bool(parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__INSTANCE_CONFIGURABLE, False)),
                        invocation_overridable=bool(parameter.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItemsParametersItems_1.SCHEMA_FIELD_NAME__INVOCATION_OVERRIDABLE, False)),
                    )
                    for parameter in item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsOperationsItems_1.SCHEMA_FIELD_NAME__PARAMETERS, ())
                ),
            )
            for item in raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__OPERATIONS, ())
        )
        raw_runtime = raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__RUNTIME, {}) or {}
        runtime = AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile(raw_runtime.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__PROFILE, "in_process")),
            command=tuple(str(v) for v in raw_runtime.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__COMMAND, ())),
            cwd=str(raw_runtime[AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__CWD]) if raw_runtime.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__CWD) is not None else None,
            environment={str(k): str(v) for k, v in raw_runtime.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__ENVIRONMENT, {}).items()},
            timeout_seconds=float(raw_runtime.get(AIigComponentDescriptorComponentCapabilityProvidersItemsRuntime_1.SCHEMA_FIELD_NAME__TIMEOUT_SECONDS, 30.0)),
        )
        readiness_requirements = tuple(
            AIcReadinessRequirementDescriptor(
                id=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__ID]),
                source=AInReadinessRequirementSource(str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__SOURCE])),
                key=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__KEY]),
                missing_state=AInReadinessState(str(item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__MISSING_STATE, "not_ready"))),
                message=(str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__MESSAGE]) if item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsReadinessRequirementsItems_1.SCHEMA_FIELD_NAME__MESSAGE) is not None else None),
            )
            for item in raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__READINESS_REQUIREMENTS, ())
        )
        capability_providers.append(AIcProviderDefinitionDescriptor(
            id=raw_provider[AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__ID],
            capabilities=capabilities,
            implementation_classes=tuple(
                AIcProviderImplementationClassDescriptor(
                    technology_kind=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsImplementationClassesItems_1.SCHEMA_FIELD_NAME__TECHNOLOGY_KIND]),
                    provider_class_name=str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsImplementationClassesItems_1.SCHEMA_FIELD_NAME__PROVIDER_CLASS_NAME]),
                    capability_profile_matcher_class_name=(
                        str(item[AIigComponentDescriptorComponentCapabilityProvidersItemsImplementationClassesItems_1.SCHEMA_FIELD_NAME__CAPABILITY_PROFILE_MATCHER_CLASS_NAME])
                        if item.get(AIigComponentDescriptorComponentCapabilityProvidersItemsImplementationClassesItems_1.SCHEMA_FIELD_NAME__CAPABILITY_PROFILE_MATCHER_CLASS_NAME) is not None else None
                    ),
                )
                for item in raw_provider[AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__IMPLEMENTATION_CLASSES]
            ),
            name=normalize_display_text(raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__NAME)),
            description=normalize_display_text(raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
            configuration_schema=_parse_persisted_schema(raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCHEMA)),
            initial_instances=initial_instances,
            requirements=requirements,
            operations=provider_operations,
            readiness_requirements=readiness_requirements,
            runtime_factory_class=raw_provider.get(AIigComponentDescriptorComponentCapabilityProvidersItems_1.SCHEMA_FIELD_NAME__RUNTIME_FACTORY_CLASS),
            runtime=runtime,
        ))

    entitlement_licensing_scopes = tuple(
        AIcEntitlementLicensingScopeDescriptor(
            type=str(item[AIigComponentDescriptorComponentEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__TYPE]),
            name=normalize_display_text(item.get(AIigComponentDescriptorComponentEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__NAME)),
            description=normalize_display_text(item.get(AIigComponentDescriptorComponentEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
            metadata=dict(item.get(AIigComponentDescriptorComponentEntitlementLicensingScopesItems_1.SCHEMA_FIELD_NAME__METADATA, {})),
        )
        for item in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__ENTITLEMENT_LICENSING_SCOPES, ())
    )

    provided_capability_entitlements = []
    for raw_capability in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__PROVIDED_CAPABILITY_ENTITLEMENTS, ()):
        permissions = tuple(
            AIcPermissionDescriptor(
                id=item[AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__ID],
                name=normalize_display_text(item.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__NAME)),
                description=normalize_display_text(item.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                possible_licensing_scope_types=tuple(
                    str(v) for v in item.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__POSSIBLE_LICENSING_SCOPES, ())
                ),
                metadata=item.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__METADATA, {}),
            )
            for item in raw_capability.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1.SCHEMA_FIELD_NAME__PERMISSIONS, ())
        )
        provided_capability_entitlements.append(AIcCapabilityEntitlementDescriptor(
            capability_id=raw_capability[AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1.SCHEMA_FIELD_NAME__CAPABILITY][AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsCapability_1.SCHEMA_FIELD_NAME__ID],
            capability_version=int(raw_capability[AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1.SCHEMA_FIELD_NAME__CAPABILITY][AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItemsCapability_1.SCHEMA_FIELD_NAME__VERSION]),
            permissions=permissions,
            name=normalize_display_text(raw_capability.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1.SCHEMA_FIELD_NAME__NAME)),
            description=normalize_display_text(raw_capability.get(AIigComponentDescriptorComponentProvidedCapabilityEntitlementsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
        ))


    data_entity_support = []
    for raw_support in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__DATA_ENTITY_SUPPORT, ()):
        migrations = tuple(
            AIcSchemaMigrationStepDescriptor(
                from_version=int(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__FROM]),
                to_version=int(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__TO]),
                migrator_id=str(item[AIigComponentDescriptorDefinitionSchemaMigrationStep_1.SCHEMA_FIELD_NAME__MIGRATOR]),
            )
            for item in raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__MIGRATIONS, ())
        )
        requirements = tuple(
            AIcDataEntityRequirementDescriptor(
                schema_id=str(item[AIigComponentDescriptorDefinitionDataEntityRequirement_1.SCHEMA_FIELD_NAME__SCHEMA_ID]),
                access=tuple(AInDataEntityAccess(str(value)) for value in item.get(AIigComponentDescriptorDefinitionDataEntityRequirement_1.SCHEMA_FIELD_NAME__ACCESS, ())),
                readable_versions=tuple(int(value) for value in item.get(AIigComponentDescriptorDefinitionDataEntityRequirement_1.SCHEMA_FIELD_NAME__READABLE_VERSIONS, ())),
                writable_versions=tuple(int(value) for value in item.get(AIigComponentDescriptorDefinitionDataEntityRequirement_1.SCHEMA_FIELD_NAME__WRITABLE_VERSIONS, ())),
                required=bool(item.get(AIigComponentDescriptorDefinitionDataEntityRequirement_1.SCHEMA_FIELD_NAME__REQUIRED, True)),
            )
            for item in raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__DATA_ENTITY_REQUIREMENTS, ())
        )
        data_entity_support.append(AIcDataEntitySupportDescriptor(
            schema_id=str(raw_support[AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__SCHEMA_ID]),
            readable_versions=tuple(int(value) for value in raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__READABLE_VERSIONS, ())),
            writable_versions=tuple(int(value) for value in raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__WRITABLE_VERSIONS, ())),
            preferred_write_version=(
                int(raw_support[AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__PREFERRED_WRITE_VERSION])
                if raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__PREFERRED_WRITE_VERSION) is not None else None
            ),
            migrations=migrations,
            data_entity_requirements=requirements,
            name=normalize_display_text(raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__NAME)),
            description=normalize_display_text(raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
            metadata=dict(raw_support.get(AIigComponentDescriptorDefinitionDataEntitySupport_1.SCHEMA_FIELD_NAME__METADATA, {})),
        ))

    raw_lifecycle = component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__LIFECYCLE, {}) or {}
    lifecycle = AIcLifecycleHooksDescriptor(**{
        name: raw_lifecycle.get(name)
        for name in ("provision", "validate", "unprovision")
    })
    return AIcComponentDescriptor(
        id=component[AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__ID],
        version=int(component[AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__VERSION]),
        name=normalize_display_text(component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__NAME)),
        description=normalize_display_text(component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
        capability_providers=tuple(capability_providers),
        capability_group_resources=tuple(str(v) for v in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__CAPABILITY_GROUPS, ())),
        contract_resources=tuple(str(v) for v in component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__CAPABILITY, ())),
        component_configuration_schema=_parse_persisted_schema(component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__COMPONENT_CONFIGURATION_SCHEMA)),
        entitlement_licensing_scopes=entitlement_licensing_scopes,
        provided_capability_entitlements=tuple(provided_capability_entitlements),
        data_entity_support=tuple(data_entity_support),
        lifecycle=lifecycle,
        metadata=component.get(AIigComponentDescriptorComponent_1.SCHEMA_FIELD_NAME__METADATA, {}),
    )

class AIcDescriptorLoader:
    @staticmethod
    def load_file(path: str | Path) -> AIcComponentDescriptor:
        path = Path(path)
        return AIcDescriptorLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_package(package: str, resource_name: str = "component.yml") -> AIcComponentDescriptor:
        return AIcDescriptorLoader.discover_package(package, resource_name).descriptor

    @staticmethod
    def discover_package(package: str, resource_name: str = "component.yml", *, artifact_path: str | None = None) -> AIcDiscoveredComponent:
        # When an explicit wheel is supplied, descriptor discovery must not resolve through an
        # already-imported package of another version.  Read the candidate artifact directly.
        if artifact_path is not None:
            artifact = Path(artifact_path)
            if artifact.is_file() and is_zipfile(artifact):
                return AIcDescriptorLoader.discover_wheel(artifact, package, resource_name)
        try:
            text = resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise AIxDescriptorError(f"cannot read {resource_name!r} from package {package!r}") from exc
        source = f"{package}:{resource_name}"
        return AIcDiscoveredComponent(AIcDescriptorLoader.load_text(text, source=source), package, source, artifact_path)

    @staticmethod
    def discover_wheel(wheel_path: str | Path, package: str, resource_name: str = "component.yml") -> AIcDiscoveredComponent:
        wheel = Path(wheel_path)
        member = package.replace(".", "/") + "/" + resource_name
        try:
            with ZipFile(wheel) as archive:
                text = archive.read(member).decode("utf-8")
        except (OSError, BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise AIxDescriptorError(f"cannot read {member!r} from wheel {wheel}: {exc}") from exc
        source = f"{wheel}!/{member}"
        return AIcDiscoveredComponent(AIcDescriptorLoader.load_text(text, source=source), package, source, str(wheel))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcComponentDescriptor:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: descriptor root must be a mapping")
        _validate_raw_descriptor(raw, source)
        try:
            return _parse_component(raw[AIigComponentDescriptor_1.SCHEMA_FIELD_NAME__COMPONENT])
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid component descriptor: {exc}") from exc

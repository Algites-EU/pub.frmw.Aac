from __future__ import annotations

import pytest

from algites.lib.aac.coreimpl.operation_parameters import (
    AIcOperationParameterConfigurationStore,
    AIcOperationParameterResolver,
)
from algites.lib.aac.coreimpl.persistence import AIcInMemoryStateStore
from algites.lib.aac.coreintf.contracts import AIcProvidedCapability
from algites.lib.aac.coreintf.descriptor import (
    AIcCapabilityProviderOperationDescriptor,
    AIcCapabilityProviderOperationInteractionDescriptor,
    AIcOperationParameterDefinitionDescriptor,
    AIcOperationParameterEnumValueDescriptor,
    AIcProviderDefinitionDescriptor,
)
from algites.lib.aac.coreintf.presentation import AIcDisplayText


def _parameter(**changes):
    values = dict(
        id="integration_strategy",
        name=AIcDisplayText(text="Integration strategy", resource_key="vcs.pull.integrationStrategy.name"),
        description=AIcDisplayText(text="How retrieved changes are integrated.", resource_key="vcs.pull.integrationStrategy.description"),
        value_schema={"type": "string", "enum": ["MERGE", "REBASE", "FAST_FORWARD_ONLY"]},
        enum_values=(
            AIcOperationParameterEnumValueDescriptor(
                "MERGE", AIcDisplayText(text="Merge"), AIcDisplayText(text="Merge histories.")),
            AIcOperationParameterEnumValueDescriptor(
                "REBASE", AIcDisplayText(text="Rebase"), AIcDisplayText(text="Reapply local revisions.")),
        ),
        default="MERGE",
        has_default=True,
        component_configurable=True,
        instance_configurable=True,
        invocation_overridable=True,
    )
    values.update(changes)
    return AIcOperationParameterDefinitionDescriptor(**values)


def _provider(parameter=None):
    return AIcProviderDefinitionDescriptor(
        id="git",
        capabilities=(AIcProvidedCapability("_AAC.vcs.distributed-repository-synchronization", (1,)),),
        implementation_class="example:Provider",
        operations=(AIcCapabilityProviderOperationDescriptor(
            "_AAC.vcs.distributed-repository-synchronization", 1, "pull",
            AIcCapabilityProviderOperationInteractionDescriptor(),
            (parameter or _parameter(),),
        ),),
    )


def test_operation_parameter_precedence_and_validation():
    store = AIcOperationParameterConfigurationStore(AIcInMemoryStateStore())
    resolver = AIcOperationParameterResolver(store)
    provider = _provider()
    resolver.validate_provider_definition(provider)

    assert resolver.resolve(
        provider, component_id="c", component_version=1, provider_instance_id="i",
        capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
        operation_id="pull",
    ) == {"integration_strategy": "MERGE"}

    store.set_component_value(
        "c", "git", "_AAC.vcs.distributed-repository-synchronization", 1, "pull",
        "integration_strategy", "REBASE", component_version=2,
    )
    assert resolver.resolve(
        provider, component_id="c", component_version=2, provider_instance_id="i",
        capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
        operation_id="pull",
    )["integration_strategy"] == "REBASE"

    store.set_instance_value(
        "c", "git", "i", "_AAC.vcs.distributed-repository-synchronization", 1, "pull",
        "integration_strategy", "FAST_FORWARD_ONLY", component_version=2,
    )
    assert resolver.resolve(
        provider, component_id="c", component_version=2, provider_instance_id="i",
        capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
        operation_id="pull",
    )["integration_strategy"] == "FAST_FORWARD_ONLY"

    assert resolver.resolve(
        provider, component_id="c", component_version=2, provider_instance_id="i",
        capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
        operation_id="pull", invocation_overrides={"integration_strategy": "MERGE"},
    )["integration_strategy"] == "MERGE"

    with pytest.raises(Exception):
        resolver.resolve(
            provider, component_id="c", component_version=2, provider_instance_id="i",
            capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
            operation_id="pull", invocation_overrides={"integration_strategy": "INVALID"},
        )


def test_scope_permissions_and_required_parameter():
    store = AIcOperationParameterConfigurationStore(AIcInMemoryStateStore())
    resolver = AIcOperationParameterResolver(store)
    parameter = _parameter(
        default=None, has_default=False, required=True,
        component_configurable=False, instance_configurable=True, invocation_overridable=False,
    )
    provider = _provider(parameter)

    with pytest.raises(ValueError, match="required operation parameter"):
        resolver.resolve(
            provider, component_id="c", component_version=1, provider_instance_id="i",
            capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
            operation_id="pull",
        )
    with pytest.raises(ValueError, match="not component-configurable"):
        resolver.validate_configured_value(parameter, "MERGE", scope="COMPONENT")
    with pytest.raises(ValueError, match="not invocation-overridable"):
        resolver.resolve(
            provider, component_id="c", component_version=1, provider_instance_id="i",
            capability_id="_AAC.vcs.distributed-repository-synchronization", capability_version=1,
            operation_id="pull", invocation_overrides={"integration_strategy": "MERGE"},
        )


def test_operation_parameter_enum_display_values_are_constrained_by_value_schema():
    resolver = AIcOperationParameterResolver(AIcOperationParameterConfigurationStore(AIcInMemoryStateStore()))
    invalid = _parameter(enum_values=(
        AIcOperationParameterEnumValueDescriptor("UNKNOWN", AIcDisplayText(text="Unknown")),
    ))
    with pytest.raises(ValueError, match="absent from value_schema"):
        resolver.validate_definition(invalid)

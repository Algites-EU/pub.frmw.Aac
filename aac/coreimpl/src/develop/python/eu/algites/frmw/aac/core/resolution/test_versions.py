import pytest

from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef, AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderInstanceState
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingResolutionError
from eu.algites.frmw.aac.core.resolution.bindings import AIcBindingResolver


def candidate(instance_id, versions=(1, 2)):
    return AIcProviderInstance(instance_id, "c", "p", instance_id, (AIcProvidedCapability("x.cap", versions),), "m:C", state=AInProviderInstanceState.CONFIGURED)


def catalog():
    result = AIcActiveContractCatalog()
    result.admit_builtin_contracts()
    for version in (1, 2):
        result.admit(AIcCapabilityContract(AIcCapabilityRef("x.cap", version), "_AAC.runtime", (AIcCapabilityOperation("run"),)))
    return result


def test_binding_stores_negotiated_version_not_provider_max_by_assumption():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1,))
    binding = AIcBindingResolver(catalog()).resolve_single("consumer", requirement, [candidate("p1")])
    assert binding.capability_version == 1


def test_single_is_ambiguous_when_multiple_provider_instances_are_valid():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1, 2))
    with pytest.raises(AIxBindingResolutionError, match="ambiguous"):
        AIcBindingResolver(catalog()).resolve_single("consumer", requirement, [candidate("p1"), candidate("p2")])


def test_multiple_returns_all_compatible_instances():
    requirement = AIcConsumerRequirementDescriptor("r", "x.cap", (1, 2), cardinality=AInConsumerCardinality.MULTIPLE)
    bindings = AIcBindingResolver(catalog()).resolve_multiple("consumer", requirement, [candidate("p2"), candidate("p1")])
    assert [binding.provider_instance_id for binding in bindings] == ["p1", "p2"]


def qualified_catalog():
    result = AIcActiveContractCatalog()
    result.admit_builtin_contracts()
    result.schema_registry.register("test-binding-qualifiers_1.json", {
        "x-aac-schema-id": "test.binding-qualifiers",
        "x-aac-schema-version": 1,
        "type": "object",
        "required": ["TechnologyKind", "BuildOutputType"],
        "additionalProperties": False,
        "properties": {
            "TechnologyKind": {"type": "string"},
            "BuildOutputType": {"type": "string"},
        },
    })
    from eu.algites.frmw.aac.core.capability.api import AIcSchemaRef
    result.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.qualified", 1),
        "_AAC.runtime",
        (AIcCapabilityOperation("run"),),
        binding_qualifiers_schema=AIcSchemaRef("test.binding-qualifiers", 1),
    ))
    return result


def qualified_candidate(instance_id, profiles):
    return AIcProviderInstance(
        instance_id,
        "c",
        "p",
        instance_id,
        (AIcProvidedCapability("x.qualified", (1,), tuple(profiles)),),
        "m:C",
        state=AInProviderInstanceState.CONFIGURED,
    )


def test_capability_profile_matcher_selects_multiple_provider_profiles_and_stores_them_on_binding():
    requirement = AIcConsumerRequirementDescriptor("r", "x.qualified", (1,))
    binding = AIcBindingResolver(qualified_catalog()).resolve_single(
        "consumer",
        requirement,
        [qualified_candidate("java", (
            {"TechnologyKind": "java", "BuildOutputType": "java-bin-jar"},
            {"TechnologyKind": "java", "BuildOutputType": "java-source-jar"},
            {"TechnologyKind": "java", "BuildOutputType": "java-doc-jar"},
        ))],
        capability_profile_matcher_class_name="eu.algites.frmw.aac.core.resolution.test_profile_matcher_fixture:AIcTestCapabilityProfileMatcher",
        consumer_configuration={"WantedOutputs": ["java-bin-jar", "java-source-jar"]},
    )
    assert binding.binding_qualifier_profiles == (
        {"TechnologyKind": "java", "BuildOutputType": "java-bin-jar"},
        {"TechnologyKind": "java", "BuildOutputType": "java-source-jar"},
    )


def test_qualified_capability_requires_matcher_class():
    resolver = AIcBindingResolver(qualified_catalog())
    with pytest.raises(AIxBindingResolutionError, match="CapabilityProfileMatcherClassName"):
        resolver.resolve_single(
            "consumer",
            AIcConsumerRequirementDescriptor("r", "x.qualified", (1,)),
            [qualified_candidate("java", ({"TechnologyKind": "java", "BuildOutputType": "java-bin-jar"},))],
        )


def test_required_binding_qualifier_fields_are_validated_on_provider_profiles():
    resolver = AIcBindingResolver(qualified_catalog())
    with pytest.raises(AIxBindingResolutionError, match="provider instance.*binding qualifier profile is invalid"):
        resolver.resolve_single(
            "consumer",
            AIcConsumerRequirementDescriptor("r", "x.qualified", (1,)),
            [qualified_candidate("java", ({"TechnologyKind": "java"},))],
            capability_profile_matcher_class_name="eu.algites.frmw.aac.core.resolution.test_profile_matcher_fixture:AIcTestCapabilityProfileMatcher",
            consumer_configuration={"WantedOutputs": ["java-bin-jar"]},
        )


def test_unqualified_capability_rejects_provider_profile_declarations():
    provider = AIcProviderInstance(
        "p1", "c", "p", "p1",
        (AIcProvidedCapability("x.cap", (1,), ({"TechnologyKind": "java"},)),),
        "m:C", state=AInProviderInstanceState.CONFIGURED,
    )
    with pytest.raises(AIxBindingResolutionError, match="has no BindingQualifiersSchema"):
        AIcBindingResolver(catalog()).resolve_single(
            "consumer", AIcConsumerRequirementDescriptor("r", "x.cap", (1,)), [provider]
        )


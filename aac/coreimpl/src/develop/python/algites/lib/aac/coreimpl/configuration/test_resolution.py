import pytest

from algites.lib.aac.coreintf.configuration import (
    AInConfigurationPolicyMode,
    AInConfigurationTargetKind,
    AInConfigurationValueSourceKind,
    AIcConfigurationContribution,
    AIcConfigurationPolicy,
    AIcConfigurationProviderBinding,
    AIcConfigurationTarget,
    AIcResolvedConfigurationScope,
)
from algites.lib.aac.coreintf.context import AIcConfigurationScope
from algites.lib.aac.coreimpl.configuration import (
    AIcConfigurationProviderRegistry,
    AIcConfigurationResolver,
    AIcStaticConfigurationProvider,
)
from algites.lib.aac.coreimpl.errors import AIxConfigurationPolicyError


def _scope(definition_id, type_, id_, provider):
    return AIcResolvedConfigurationScope(
        definition_id, AIcConfigurationScope(type_, id_), (AIcConfigurationProviderBinding(provider, 100),), True
    )


def _target():
    return AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, "vendor.foo")


def test_policy_intersection_and_specific_value_resolution():
    providers = AIcConfigurationProviderRegistry()
    providers.register("org", AIcStaticConfigurationProvider({
        "ORGANIZATION(algites)": (
            AIcConfigurationContribution("size", policy_modes=(
                AIcConfigurationPolicy(AInConfigurationPolicyMode.MIN, 20),
                AIcConfigurationPolicy(AInConfigurationPolicyMode.MAX, 50),
            )),
        ),
    }))
    providers.register("workspace", AIcStaticConfigurationProvider({
        "WORKSPACE(project-x)": (
            AIcConfigurationContribution("size", policy_modes=(
                AIcConfigurationPolicy(AInConfigurationPolicyMode.IN_SET, [10, 30, 40, 80]),
            )),
        ),
    }))
    providers.register("user", AIcStaticConfigurationProvider({
        "USER(artur)": (AIcConfigurationContribution("size", value=40, has_value=True),),
    }))
    scopes = (
        _scope("user", "USER", "artur", "user"),
        _scope("workspace", "WORKSPACE", "project-x", "workspace"),
        _scope("org", "ORGANIZATION", "algites", "org"),
    )
    result = AIcConfigurationResolver(providers).resolve(
        configuration_target=_target(), configuration_scopes=scopes, property_ids=("size",),
    )
    value = result.values["size"]
    assert result.configuration_target == _target()
    assert value.value == 40
    assert value.source_kind is AInConfigurationValueSourceKind.EXPLICIT
    assert value.effective_policy.minimum == 20
    assert value.effective_policy.maximum == 50
    assert value.effective_policy.in_set == (10, 30, 40, 80)


def test_policy_tightening_can_reduce_effective_set_to_two_values():
    providers = AIcConfigurationProviderRegistry()
    providers.register("org", AIcStaticConfigurationProvider({
        "ORGANIZATION(algites)": (AIcConfigurationContribution("size", policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.MIN, 20),
            AIcConfigurationPolicy(AInConfigurationPolicyMode.MAX, 50),
        )),),
    }))
    providers.register("workspace", AIcStaticConfigurationProvider({
        "WORKSPACE(project-x)": (AIcConfigurationContribution("size", policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.IN_SET, [10, 30, 40, 80]),
        )),),
    }))
    scopes = (
        _scope("workspace", "WORKSPACE", "project-x", "workspace"),
        _scope("org", "ORGANIZATION", "algites", "org"),
    )
    result = AIcConfigurationResolver(providers).resolve(
        configuration_target=_target(), configuration_scopes=scopes, property_ids=("size",), schema_defaults={"size": 30},
    )
    policy = result.values["size"].effective_policy
    assert [v for v in policy.in_set if 20 <= v <= 50] == [30, 40]


def test_more_specific_minimum_cannot_relax_less_specific_minimum():
    providers = AIcConfigurationProviderRegistry()
    providers.register("org", AIcStaticConfigurationProvider({
        "ORGANIZATION(algites)": (AIcConfigurationContribution("size", policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.MIN, 20),
        )),),
    }))
    providers.register("workspace", AIcStaticConfigurationProvider({
        "WORKSPACE(project-x)": (AIcConfigurationContribution("size", policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.MIN, 10),
        )),),
    }))
    scopes = (
        _scope("workspace", "WORKSPACE", "project-x", "workspace"),
        _scope("org", "ORGANIZATION", "algites", "org"),
    )
    result = AIcConfigurationResolver(providers).resolve(
        configuration_target=_target(), configuration_scopes=scopes, property_ids=("size",), schema_defaults={"size": 20},
    )
    assert result.values["size"].effective_policy.minimum == 20


def test_policy_default_is_distinct_from_explicit_value():
    providers = AIcConfigurationProviderRegistry()
    providers.register("system", AIcStaticConfigurationProvider({
        "SYSTEM": (AIcConfigurationContribution("timeout", policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.DEFAULT, 30),
        )),),
    }))
    scopes = (_scope("system", "SYSTEM", None, "system"),)
    result = AIcConfigurationResolver(providers).resolve(
        configuration_target=_target(), configuration_scopes=scopes, property_ids=("timeout",),
    )
    assert result.values["timeout"].value == 30
    assert result.values["timeout"].source_kind is AInConfigurationValueSourceKind.POLICY_DEFAULT


def test_explicit_value_violating_policy_is_error_not_fallback():
    providers = AIcConfigurationProviderRegistry()
    providers.register("system", AIcStaticConfigurationProvider({
        "SYSTEM": (AIcConfigurationContribution("timeout", value=30, has_value=True, policy_modes=(
            AIcConfigurationPolicy(AInConfigurationPolicyMode.MAX, 50),
        )),),
    }))
    providers.register("user", AIcStaticConfigurationProvider({
        "USER(artur)": (AIcConfigurationContribution("timeout", value=80, has_value=True),),
    }))
    scopes = (
        _scope("user", "USER", "artur", "user"),
        _scope("system", "SYSTEM", None, "system"),
    )
    with pytest.raises(AIxConfigurationPolicyError):
        AIcConfigurationResolver(providers).resolve(
            configuration_target=_target(), configuration_scopes=scopes, property_ids=("timeout",),
        )


def test_unsupported_versioned_provider_contribution_is_unavailable_and_falls_back_to_default():
    from algites.lib.aac.coreintf.configuration import (
        AIcConfigurationPersistedPayload,
        AIcConfigurationProviderRequest,
        AIcConfigurationProviderSnapshot,
        AIiConfigurationProvider,
    )
    from algites.lib.aac.coreintf.descriptor import AIcPersistedSchemaDescriptor
    from algites.lib.aac.coreimpl.configuration import AIcConfigurationReadService
    from algites.lib.aac.coreimpl.migration import AIcConfigurationMigrationService
    from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry

    class VersionedProvider(AIiConfigurationProvider):
        def snapshot(self, request):
            payload = AIcConfigurationPersistedPayload(
                request.configuration_target, "foo-config", 3, 3,
                values={"timeout": 99},
                policies={"timeout": (AIcConfigurationPolicy(AInConfigurationPolicyMode.LOCK, 99),)},
            )
            return AIcConfigurationProviderSnapshot(request.configuration_scope, request.configuration_target, 1, payload)

        def contributions(self, request):
            raise AssertionError("versioned provider must be consumed through snapshot")

    providers = AIcConfigurationProviderRegistry()
    providers.register("future", VersionedProvider())
    declaration = AIcPersistedSchemaDescriptor("foo-config", 2, (2,), resource_name="foo-config_2.json")
    schemas = AIcSchemaRegistry()
    schemas.register("foo-config_2.json", {
        "type": "object",
        "properties": {"timeout": {"type": "integer", "default": 30}},
        "required": ["timeout"],
    })
    read_service = AIcConfigurationReadService(
        providers, AIcConfigurationMigrationService(), lambda target: (declaration, 2), schemas
    )
    resolver = AIcConfigurationResolver(providers, read_service)
    result = resolver.resolve(
        configuration_target=_target(),
        configuration_scopes=(_scope("org", "ORGANIZATION", "algites", "future"),),
        property_ids=("timeout",),
        schema_defaults={"timeout": 30},
    )
    assert result.values["timeout"].value == 30
    assert result.values["timeout"].source_kind is AInConfigurationValueSourceKind.SCHEMA_DEFAULT
    assert result.values["timeout"].effective_policy.has_lock is False
    assert any("unsupported representation" in item for item in result.diagnostics)


def test_unsupported_contribution_without_fallback_resolves_to_undefined():
    from algites.lib.aac.coreintf.configuration import (
        AIcConfigurationPersistedPayload,
        AIcConfigurationProviderSnapshot,
        AIiConfigurationProvider,
    )
    from algites.lib.aac.coreintf.descriptor import AIcPersistedSchemaDescriptor
    from algites.lib.aac.coreimpl.configuration import AIcConfigurationReadService
    from algites.lib.aac.coreimpl.migration import AIcConfigurationMigrationService
    from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry

    class VersionedProvider(AIiConfigurationProvider):
        def snapshot(self, request):
            payload = AIcConfigurationPersistedPayload(
                request.configuration_target, "foo-config", 8, 8, values={"endpoint": "future"}
            )
            return AIcConfigurationProviderSnapshot(request.configuration_scope, request.configuration_target, 1, payload)

        def contributions(self, request):
            return ()

    providers = AIcConfigurationProviderRegistry(); providers.register("future", VersionedProvider())
    declaration = AIcPersistedSchemaDescriptor("foo-config", 2, (2,), resource_name="foo-config_2.json")
    schemas = AIcSchemaRegistry(); schemas.register("foo-config_2.json", {
        "type": "object", "properties": {"endpoint": {"type": "string"}}, "required": ["endpoint"]
    })
    read_service = AIcConfigurationReadService(
        providers, AIcConfigurationMigrationService(), lambda target: (declaration, 2), schemas
    )
    result = AIcConfigurationResolver(providers, read_service).resolve(
        configuration_target=_target(),
        configuration_scopes=(_scope("org", "ORGANIZATION", "algites", "future"),),
        property_ids=("endpoint",),
    )
    assert result.values["endpoint"].source_kind is AInConfigurationValueSourceKind.UNDEFINED
    assert result.plain_values() == {}

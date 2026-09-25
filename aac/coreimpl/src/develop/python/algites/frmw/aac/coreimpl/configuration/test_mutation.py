import pytest

from algites.frmw.aac.coreintf.configuration import (
    AInConfigurationMutationOperation,
    AInConfigurationProviderCapability,
    AInConfigurationTargetKind,
    AIcConfigurationChange,
    AIcConfigurationChangeSet,
    AIcConfigurationContribution,
    AIcConfigurationMutationResult,
    AIcConfigurationProviderRequest,
    AIcConfigurationTarget,
)
from algites.frmw.aac.coreintf.context import AIcConfigurationScope
from algites.frmw.aac.coreintf.configuration import AIiConfigurationProvider
from algites.frmw.aac.coreimpl.configuration import (
    AIcAllowOwnNamespaceConfigurationMutationAuthorizer,
    AIcConfigurationMutationService,
    AIcConfigurationProviderRegistry,
)
from algites.frmw.aac.coreimpl.errors import AIxConfigurationPolicyError


class AIcTestWritableProvider(AIiConfigurationProvider):
    def __init__(self):
        self.applied = []

    def contributions(self, request: AIcConfigurationProviderRequest):
        return ()

    def capabilities(self, request: AIcConfigurationProviderRequest):
        return (
            AInConfigurationProviderCapability.READ,
            AInConfigurationProviderCapability.WRITE_VALUE,
            AInConfigurationProviderCapability.DELETE_VALUE,
            AInConfigurationProviderCapability.WRITE_POLICY,
            AInConfigurationProviderCapability.DELETE_POLICY,
            AInConfigurationProviderCapability.ATOMIC_CHANGE_SET,
        )

    def apply_changes(self, change_set):
        self.applied.append(change_set)
        return AIcConfigurationMutationResult("rev-2", tuple(change.property_id for change in change_set.changes))


def _change_set(actor="vendor.foo"):
    return AIcConfigurationChangeSet(
        AIcConfigurationScope("WORKSPACE", "project-x"),
        "rw",
        AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, "vendor.foo", "instance-1"),
        (
            AIcConfigurationChange("url", AInConfigurationMutationOperation.SET_VALUE, "https://example", True),
            AIcConfigurationChange("timeout", AInConfigurationMutationOperation.DELETE_VALUE),
        ),
        expected_record_revision="rev-1",
        actor_context={"component_id": actor},
    )


def test_atomic_change_set_is_forwarded_to_rw_provider_after_core_authorization():
    provider = AIcTestWritableProvider()
    registry = AIcConfigurationProviderRegistry()
    registry.register("rw", provider)
    service = AIcConfigurationMutationService(registry, AIcAllowOwnNamespaceConfigurationMutationAuthorizer())
    result = service.apply(_change_set())
    assert result.record_revision == "rev-2"
    assert result.changed_property_ids == ("url", "timeout")
    assert provider.applied[0].expected_record_revision == "rev-1"


def test_component_cannot_mutate_another_component_namespace():
    provider = AIcTestWritableProvider()
    registry = AIcConfigurationProviderRegistry()
    registry.register("rw", provider)
    service = AIcConfigurationMutationService(registry, AIcAllowOwnNamespaceConfigurationMutationAuthorizer())
    with pytest.raises(AIxConfigurationPolicyError):
        service.apply(_change_set(actor="vendor.other"))


def test_access_descriptor_intersects_provider_rw_with_core_authorization():
    provider = AIcTestWritableProvider()
    registry = AIcConfigurationProviderRegistry(); registry.register("rw", provider)
    service = AIcConfigurationMutationService(registry, AIcAllowOwnNamespaceConfigurationMutationAuthorizer())
    request = AIcConfigurationProviderRequest(
        AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, "vendor.foo", "instance-1"),
        AIcConfigurationScope("WORKSPACE", "project-x"),
    )
    own = service.access_for("rw", request, {"component_id": "vendor.foo"})
    other = service.access_for("rw", request, {"component_id": "vendor.other"})
    assert "WRITE_VALUE" in {item.value for item in own.authorized_capabilities}
    assert {item.value for item in other.authorized_capabilities} == {"READ"}

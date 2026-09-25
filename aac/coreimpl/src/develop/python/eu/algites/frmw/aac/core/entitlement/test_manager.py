from eu.algites.frmw.aac.core.descriptor.api import AIcProviderImplementationClassDescriptor
from datetime import datetime, timezone

from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor, AIcComponentDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor, AIcProviderDefinitionDescriptor,
)
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementCapabilityGrant, AIcEntitlementComponentGrant, AIcEntitlementDocument, AIcEntitlementIssuer,
    AIcEntitlementPermissionGrant, AIcEntitlementProviderBinding, AIcEntitlementSubject, AIcResolvedEntitlementLicensingScope,
)
from eu.algites.frmw.aac.core.entitlement.runtime import AIcEntitlementManager, AIcEntitlementProviderRegistry, AIcStaticEntitlementProvider


def _descriptor():
    return AIcComponentDescriptor(
        "vendor.foo", 1,
        capability_providers=(AIcProviderDefinitionDescriptor("main", (AIcProvidedCapability("vendor.foo.document", (1,)),), (AIcProviderImplementationClassDescriptor("python", "x:Provider"),)),),
        entitlement_licensing_scopes=(
            AIcEntitlementLicensingScopeDescriptor("USER"),
            AIcEntitlementLicensingScopeDescriptor("WORKSPACE"),
            AIcEntitlementLicensingScopeDescriptor("ORGANIZATION"),
        ),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "vendor.foo.document", 1,
            (
                AIcPermissionDescriptor("BASIC"),
                AIcPermissionDescriptor("WRITE", possible_licensing_scope_types=("USER", "WORKSPACE", "ORGANIZATION")),
                AIcPermissionDescriptor("EXPORT", possible_licensing_scope_types=("WORKSPACE",)),
            ),
        ),),
    )


def _doc(eid, scope_type, subject_id, permissions, *, component_id="vendor.foo", valid_until=None):
    return AIcEntitlementDocument(
        1, eid, AIcEntitlementIssuer("vendor.example"), AIcEntitlementLicensingScope(scope_type, subject_id),
        AIcEntitlementSubject(subject_id),
        (AIcEntitlementComponentGrant(component_id, (
            AIcEntitlementCapabilityGrant("vendor.foo.document", 1, tuple(
                AIcEntitlementPermissionGrant(pid, valid_until=valid_until) for pid in permissions
            )),
        )),),
    )


def test_implicit_permission_exists_without_any_grant():
    result = AIcEntitlementManager().evaluate_component(_descriptor())
    assert result.has_permission("vendor.foo.document", 1, "BASIC")
    assert not result.has_permission("vendor.foo.document", 1, "WRITE")


def test_permissions_accumulate_across_licensing_scopes_and_providers():
    registry = AIcEntitlementProviderRegistry()
    registry.register("user-license", AIcStaticEntitlementProvider({
        "USER(artur)": (_doc("g-user", "USER", "artur", ("WRITE",)),),
    }))
    registry.register("workspace-license", AIcStaticEntitlementProvider({
        "WORKSPACE(project-x)": (_doc("g-workspace", "WORKSPACE", "project-x", ("EXPORT",)),),
    }))
    scopes = (
        AIcResolvedEntitlementLicensingScope("user", AIcEntitlementLicensingScope("USER", "artur"), (AIcEntitlementProviderBinding("user-license"),)),
        AIcResolvedEntitlementLicensingScope("workspace", AIcEntitlementLicensingScope("WORKSPACE", "project-x"), (AIcEntitlementProviderBinding("workspace-license"),)),
    )
    result = AIcEntitlementManager(registry).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert result.has_permission("vendor.foo.document", 1, "BASIC")
    assert result.has_permission("vendor.foo.document", 1, "WRITE")
    assert result.has_permission("vendor.foo.document", 1, "EXPORT")
    write = result.capability("vendor.foo.document", 1).permissions["WRITE"]
    assert write.provenance[0].entitlement_provider_id == "user-license"


def test_permission_from_non_possible_licensing_scope_is_ignored_with_diagnostic():
    registry = AIcEntitlementProviderRegistry()
    registry.register("org-license", AIcStaticEntitlementProvider({
        "ORGANIZATION(acme)": (_doc("g-org", "ORGANIZATION", "acme", ("EXPORT",)),),
    }))
    scopes = (AIcResolvedEntitlementLicensingScope(
        "org", AIcEntitlementLicensingScope("ORGANIZATION", "acme"), (AIcEntitlementProviderBinding("org-license"),)
    ),)
    result = AIcEntitlementManager(registry).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert not result.has_permission("vendor.foo.document", 1, "EXPORT")
    assert any("unsupported entitlement licensing-scope type" in item for item in result.diagnostics)


def test_multi_component_bundle_keeps_unrelated_component_dormant():
    bundle = AIcEntitlementDocument(
        1, "bundle", AIcEntitlementIssuer("vendor.example"), AIcEntitlementLicensingScope("USER", "artur"), AIcEntitlementSubject("artur"),
        (
            _doc("unused", "USER", "artur", ("WRITE",)).components[0],
            AIcEntitlementComponentGrant("vendor.other", (AIcEntitlementCapabilityGrant("vendor.other.x", 1, (AIcEntitlementPermissionGrant("ANY"),)),)),
        ),
    )
    registry = AIcEntitlementProviderRegistry()
    registry.register("bundle", AIcStaticEntitlementProvider({"USER(artur)": (bundle,)}))
    scopes = (AIcResolvedEntitlementLicensingScope("user", AIcEntitlementLicensingScope("USER", "artur"), (AIcEntitlementProviderBinding("bundle"),)),)
    result = AIcEntitlementManager(registry).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert result.has_permission("vendor.foo.document", 1, "WRITE")
    assert not any("vendor.other" in item for item in result.diagnostics)


def test_effective_expiry_uses_union_of_overlapping_grants():
    registry = AIcEntitlementProviderRegistry()
    registry.register("org", AIcStaticEntitlementProvider({
        "ORGANIZATION(acme)": (_doc("org", "ORGANIZATION", "acme", ("WRITE",), valid_until="2027-03-31T00:00:00Z"),),
    }))
    registry.register("user", AIcStaticEntitlementProvider({
        "USER(artur)": (_doc("user", "USER", "artur", ("WRITE",), valid_until="2027-06-30T00:00:00Z"),),
    }))
    scopes = (
        AIcResolvedEntitlementLicensingScope("org", AIcEntitlementLicensingScope("ORGANIZATION", "acme"), (AIcEntitlementProviderBinding("org"),)),
        AIcResolvedEntitlementLicensingScope("user", AIcEntitlementLicensingScope("USER", "artur"), (AIcEntitlementProviderBinding("user"),)),
    )
    result = AIcEntitlementManager(registry).evaluate_component(
        _descriptor(), licensing_scopes=scopes, now=datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    permission = result.capability("vendor.foo.document", 1).permissions["WRITE"]
    assert permission.effective_until == "2027-06-30T00:00:00Z"



def test_unbounded_active_grant_keeps_effective_from_unbounded():
    scope = AIcEntitlementLicensingScope("USER", "artur")
    unbounded = AIcEntitlementDocument(
        1, "unbounded", AIcEntitlementIssuer("vendor.example"), scope, AIcEntitlementSubject("artur"),
        (AIcEntitlementComponentGrant("vendor.foo", (
            AIcEntitlementCapabilityGrant("vendor.foo.document", 1, (
                AIcEntitlementPermissionGrant("WRITE", valid_until="2027-03-31T00:00:00Z"),
            )),
        )),),
    )
    finite = AIcEntitlementDocument(
        1, "finite", AIcEntitlementIssuer("vendor.example"), scope, AIcEntitlementSubject("artur"),
        (AIcEntitlementComponentGrant("vendor.foo", (
            AIcEntitlementCapabilityGrant("vendor.foo.document", 1, (
                AIcEntitlementPermissionGrant("WRITE", valid_from="2026-01-01T00:00:00Z", valid_until="2027-06-30T00:00:00Z"),
            )),
        )),),
    )
    registry = AIcEntitlementProviderRegistry()
    registry.register("user", AIcStaticEntitlementProvider({"USER(artur)": (unbounded, finite)}))
    scopes = (AIcResolvedEntitlementLicensingScope(
        "user", scope, (AIcEntitlementProviderBinding("user"),)
    ),)
    result = AIcEntitlementManager(registry).evaluate_component(
        _descriptor(), licensing_scopes=scopes, now=datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    permission = result.capability("vendor.foo.document", 1).permissions["WRITE"]
    assert permission.effective_from is None
    assert permission.effective_until == "2027-06-30T00:00:00Z"

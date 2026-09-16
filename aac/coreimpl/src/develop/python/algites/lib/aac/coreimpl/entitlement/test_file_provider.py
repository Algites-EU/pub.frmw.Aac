from pathlib import Path

from algites.lib.aac.coreintf.entitlement import AIcEntitlementLicensingScope
from algites.lib.aac.coreintf.descriptor import (
    AIcCapabilityEntitlementDescriptor, AIcComponentDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor, AIcProviderDefinitionDescriptor,
)
from algites.lib.aac.coreintf.entitlement import (
    AIcEntitlementEvidenceVerification, AIcEntitlementProviderBinding, AIcResolvedEntitlementLicensingScope,
    AIcTrustedEntitlementIssuerRule, AIiEntitlementEvidenceVerifier,
)
from algites.lib.aac.coreimpl.entitlement import AIcEntitlementManager, AIcEntitlementProviderRegistry, AIcEntitlementEvidenceVerifierRegistry
from algites.lib.aac.coreimpl.entitlement_providers import AIcFileEntitlementProvider
from algites.lib.aac.coreimpl.entitlement_trust import AIcTrustedEntitlementIssuerRegistry


class _Verifier(AIiEntitlementEvidenceVerifier):
    def verify(self, evidence):
        return AIcEntitlementEvidenceVerification(True, "test", signer_identity="release@example.test")


def _descriptor():
    return AIcComponentDescriptor(
        "vendor.foo", 1,
        providers=(AIcProviderDefinitionDescriptor("main", "vendor.foo.document", (1,), "x:Provider"),),
        entitlement_licensing_scopes=(AIcEntitlementLicensingScopeDescriptor("WORKSPACE"),),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "vendor.foo.document", 1,
            (AIcPermissionDescriptor("WRITE", possible_licensing_scope_types=("WORKSPACE",)),),
        ),),
    )


def test_file_entitlement_provider_requires_trusted_issuer(tmp_path: Path):
    path = tmp_path / "bundle.entitlement.yml"
    path.write_text('''
entitlement:
  format_version: 2
  entitlement_id: bundle-1
  issuer: {id: vendor.example}
  licensing_scope: {type: WORKSPACE}
  subject: {id: ws-1, display_name: Project One}
  components:
    - id: vendor.foo
      grants:
        - capability: {id: vendor.foo.document, version: 1}
          permissions: [{id: WRITE}]
''', encoding="utf-8")
    Path(str(path) + ".sigstore.json").write_text("{}", encoding="utf-8")

    providers = AIcEntitlementProviderRegistry()
    providers.register("files", AIcFileEntitlementProvider(tmp_path, evidence_type="SIGSTORE"))
    verifiers = AIcEntitlementEvidenceVerifierRegistry(); verifiers.register("SIGSTORE", _Verifier())
    trust = AIcTrustedEntitlementIssuerRegistry()
    scopes = (AIcResolvedEntitlementLicensingScope(
        "workspace", AIcEntitlementLicensingScope("WORKSPACE", "ws-1"), (AIcEntitlementProviderBinding("files"),)
    ),)

    denied = AIcEntitlementManager(providers, verifiers, trust).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert not denied.has_permission("vendor.foo.document", 1, "WRITE")
    assert any("not trusted" in item for item in denied.diagnostics)

    trust.register(AIcTrustedEntitlementIssuerRule(
        "vendor.example", component_ids=("vendor.foo",), evidence_types=("SIGSTORE",), signer_identities=("release@example.test",)
    ))
    allowed = AIcEntitlementManager(providers, verifiers, trust).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert allowed.has_permission("vendor.foo.document", 1, "WRITE")

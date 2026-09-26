from eu.algites.frmw.aac.core.descriptor.api import AIcProviderImplementationClassDescriptor
from pathlib import Path

from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor, AIcComponentDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor, AIcProviderDefinitionDescriptor,
)
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementEvidenceVerification, AIcEntitlementProviderBinding, AIcResolvedEntitlementLicensingScope,
    AIcTrustedEntitlementIssuerRule, AIiEntitlementEvidenceVerifier,
)
from eu.algites.frmw.aac.core.entitlement.runtime import AIcEntitlementManager, AIcEntitlementProviderRegistry, AIcEntitlementEvidenceVerifierRegistry
from eu.algites.frmw.aac.core.entitlement.providers import AIcFileEntitlementProvider
from eu.algites.frmw.aac.core.entitlement.trust import AIcTrustedEntitlementIssuerRegistry


class _Verifier(AIiEntitlementEvidenceVerifier):
    def verify(self, evidence):
        return AIcEntitlementEvidenceVerification(True, "test", signer_identity="release@example.test")


def _descriptor():
    return AIcComponentDescriptor(
        "vendor.foo", 1,
        capability_providers=(AIcProviderDefinitionDescriptor("main", (AIcProvidedCapability("vendor.foo.document", (1,)),), (AIcProviderImplementationClassDescriptor("python", "x:Provider"),)),),
        entitlement_licensing_scopes=(AIcEntitlementLicensingScopeDescriptor("WORKSPACE"),),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "vendor.foo.document", 1,
            (AIcPermissionDescriptor("write", possible_licensing_scope_types=("WORKSPACE",)),),
        ),),
    )


def test_file_entitlement_provider_requires_trusted_issuer(tmp_path: Path):
    path = tmp_path / "bundle.entitlement.yml"
    path.write_text('''
Entitlement:
  FormatVersion: 1
  EntitlementId: bundle-1
  Issuer: {Id: vendor.example}
  LicensingScope: {Type: WORKSPACE}
  Subject: {Id: ws-1, DisplayName: Project One}
  Components:
    - Id: vendor.foo
      Grants:
        - Capability: {Id: vendor.foo.document, Version: 1}
          Permissions: [{Id: write}]
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
    assert not denied.has_permission("vendor.foo.document", 1, "write")
    assert any("not trusted" in item for item in denied.diagnostics)

    trust.register(AIcTrustedEntitlementIssuerRule(
        "vendor.example", component_ids=("vendor.foo",), evidence_types=("SIGSTORE",), signer_identities=("release@example.test",)
    ))
    allowed = AIcEntitlementManager(providers, verifiers, trust).evaluate_component(_descriptor(), licensing_scopes=scopes)
    assert allowed.has_permission("vendor.foo.document", 1, "write")

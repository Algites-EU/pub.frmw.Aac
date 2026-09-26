from eu.algites.frmw.aac.core.entitlement.documents import AIcEntitlementDocumentLoader, AIcEntitlementIssuingRequestLoader


def test_multi_component_entitlement_document_loader():
    document = AIcEntitlementDocumentLoader.load_text('''
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
          Permissions:
            - {Id: view, ValidUntil: 2027-06-30T00:00:00Z}
    - Id: vendor.bar
      Grants:
        - Capability: {Id: vendor.bar.export, Version: 2}
          Permissions:
            - {Id: export-pdf}
  IssuedAt: 2026-09-14T00:00:00Z
''')
    assert document.licensing_scope.key == "WORKSPACE(ws-1)"
    assert [item.component_id for item in document.components] == ["vendor.foo", "vendor.bar"]
    assert document.components[1].grants[0].capability_version == 2


def test_multi_component_issuing_request_loader():
    request = AIcEntitlementIssuingRequestLoader.load_text('''
EntitlementRequest:
  FormatVersion: 1
  RequestId: request-1
  RequestedLicensingScope: {Type: USER}
  Subject: {Id: user-1}
  Components:
    - Id: vendor.foo
      RequestedGrants:
        - Capability: {Id: vendor.foo.document, Version: 1}
          Permissions: [view, edit]
''')
    assert request.requested_licensing_scope.key == "USER(user-1)"
    assert request.components[0].requested_grants[0].permissions == ("view", "edit")

from algites.frmw.aac.coreimpl.entitlement_documents import AIcEntitlementDocumentLoader, AIcEntitlementIssuingRequestLoader


def test_multi_component_entitlement_document_loader():
    document = AIcEntitlementDocumentLoader.load_text('''
entitlement:
  format_version: 1
  entitlement_id: bundle-1
  issuer: {id: vendor.example}
  licensing_scope: {type: WORKSPACE}
  subject: {id: ws-1, display_name: Project One}
  components:
    - id: vendor.foo
      grants:
        - capability: {id: vendor.foo.document, version: 1}
          permissions:
            - {id: view, valid_until: 2027-06-30T00:00:00Z}
    - id: vendor.bar
      grants:
        - capability: {id: vendor.bar.export, version: 2}
          permissions:
            - {id: export-pdf}
  issued_at: 2026-09-14T00:00:00Z
''')
    assert document.licensing_scope.key == "WORKSPACE(ws-1)"
    assert [item.component_id for item in document.components] == ["vendor.foo", "vendor.bar"]
    assert document.components[1].grants[0].capability_version == 2


def test_multi_component_issuing_request_loader():
    request = AIcEntitlementIssuingRequestLoader.load_text('''
entitlement_request:
  format_version: 1
  request_id: request-1
  requested_licensing_scope: {type: USER}
  subject: {id: user-1}
  components:
    - id: vendor.foo
      requested_grants:
        - capability: {id: vendor.foo.document, version: 1}
          permissions: [view, edit]
''')
    assert request.requested_licensing_scope.key == "USER(user-1)"
    assert request.components[0].requested_grants[0].permissions == ("view", "edit")

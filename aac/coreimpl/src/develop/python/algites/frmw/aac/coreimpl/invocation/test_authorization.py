from algites.frmw.aac.coreintf.authorization import AIcComponentAuthorizationGrant
from algites.frmw.aac.coreintf.invocation import AIcInvocationInput
from algites.frmw.aac.coreimpl.authorization import AIcComponentAuthorizationGrantStore
from algites.frmw.aac.coreimpl.capability import AIcActiveContractCatalog
from algites.frmw.aac.coreimpl.invocation import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint


class Provider:
    calls = 0
    def edit_1(self):
        self.calls += 1
        return None


def _catalog():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit_text('''
capability: {id: x.secured, version: 1, group_id: _AAC.runtime}
authorization_permissions:
  - {id: EDIT, name: Edit}
  - {id: ADMIN, name: Admin}
operations:
  - id: edit
    authorization:
      all_of: [EDIT]
      any_of: [ADMIN, EDIT]
''')
    return catalog


def test_core_bridge_rejects_before_provider_without_component_grant_and_accepts_with_grant():
    store = AIcComponentAuthorizationGrantStore()
    dispatcher = AIcInvocationDispatcher(_catalog(), component_authorizations=store)
    provider = Provider()
    endpoint = AIcObjectCapabilityEndpoint(provider)
    invocation = AIcInvocationInput(
        "i", None, "x.secured", 1, "edit", "provider", {}, consumer_instance_id="consumer", requirement_id="req"
    )
    denied = dispatcher.invoke(endpoint, invocation)
    assert not denied.success and denied.error["type"] == "AUTHORIZATION_DENIED"
    assert provider.calls == 0
    store.put(AIcComponentAuthorizationGrant("consumer", "req", ("EDIT",)))
    allowed = dispatcher.invoke(endpoint, invocation)
    assert allowed.success and provider.calls == 1

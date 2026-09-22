from algites.lib.aac.coreimpl.codegen import AIcPythonCapabilityBindingGenerator
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.invocation import AIcObjectCapabilityEndpoint
from algites.lib.aac.coreintf.invocation import AIcInvocationInput


def test_generated_python_binding_contains_dtos_authorization_and_is_invokable():
    catalog = AIcActiveContractCatalog()
    catalog.schema_registry.register("site-edit-input_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.site-edit-input", "x-aac-schema-version": 1, "type": "object",
        "properties": {"site_id": {"type": "string"}, "display_name": {"type": "string"}},
        "required": ["site_id", "display_name"],
    })
    catalog.schema_registry.register("site-edit-output_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.site-edit-output", "x-aac-schema-version": 1, "type": "object",
        "properties": {"changed": {"type": "boolean"}}, "required": ["changed"],
    })
    admitted = catalog.admit_text('''
capability:
  id: _AO.core.siteManagement
  version: 1
  name: Site management
authorization_permissions:
  - id: EDIT_SITE
    name: Edit sites
  - id: STANDARD_EDITOR
    name: Standard editor
  - id: ADVANCED_EDITOR
    name: Advanced editor
operations:
  - id: edit_site
    authorization: {all_of: [EDIT_SITE], any_of: [STANDARD_EDITOR, ADVANCED_EDITOR]}
    input_schema: site-edit-input_1.json
    output_schema: site-edit-output_1.json
''')
    source = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract)
    namespace = {}
    exec(source, namespace)
    interface = namespace["AIigSiteManagement_1"]
    input_dto = namespace["AIcgdSiteEditInput_1"]
    assert interface.__aac_source_id__ == "_AO.core.siteManagement"
    assert interface.__aac_source_version__ == 1
    assert input_dto.__aac_source_id__ == "_AO.schema.site-edit-input"
    assert input_dto.__aac_source_version__ == 1
    assert input_dto.__aac_source_resource__ == "site-edit-input_1.json"
    assert getattr(interface.edit_site, "__aac_authorization_all_of__") == ("EDIT_SITE",)
    assert getattr(interface.edit_site, "__aac_authorization_any_of__") == ("STANDARD_EDITOR", "ADVANCED_EDITOR")

    output_dto = namespace["AIcgdSiteEditOutput_1"]
    class Impl(interface):
        def edit_site(self, request):
            assert isinstance(request, input_dto)
            return output_dto(changed=True)

    result = AIcObjectCapabilityEndpoint(Impl()).invoke(AIcInvocationInput(
        "i", None, "_AO.core.siteManagement", 1, "edit_site", "provider", {"site_id": "s1", "display_name": "New"}
    ))
    assert result.success and result.result == {"changed": True}


def test_generated_python_binding_reuses_one_dto_type_for_one_canonical_schema():
    catalog = AIcActiveContractCatalog()
    catalog.schema_registry.register("repository-identity_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AAC.schema.repository-identity", "x-aac-schema-version": 1,
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    })
    admitted = catalog.admit_text('''
capability:
  id: _AAC.sourceRepositoryIdentification
  version: 1
operations:
  - id: identify
    input_schema: repository-identity_1.json
    output_schema: repository-identity_1.json
  - id: normalize
    input_schema: repository-identity_1.json
    output_schema: repository-identity_1.json
''')
    source = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(
        admitted.contract, canonical_resource="source-repository-identification_1.yml"
    )
    assert source.count("class AIcgdRepositoryIdentity_1") == 1
    namespace = {}
    exec(source, namespace)
    interface = namespace["AIigSourceRepositoryIdentification_1"]
    dto = namespace["AIcgdRepositoryIdentity_1"]
    assert interface.__aac_source_resource__ == "source-repository-identification_1.yml"
    assert dto.__aac_source_id__ == "_AAC.schema.repository-identity"
    assert dto.__aac_source_version__ == 1
    assert dto.__aac_source_resource__ == "repository-identity_1.json"

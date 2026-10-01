from eu.algites.frmw.aac.codegen import AIcPythonCapabilityBindingGenerator
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcObjectCapabilityEndpoint
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput


def test_generated_python_binding_contains_dtos_authorization_and_is_invokable():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("site-edit-input_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.site-edit-input", "x-aac-schema-version": 1, "type": "object",
        "description": "Request data used to edit one site.",
        "properties": {
            "site_id": {"type": "string", "description": "Stable site identifier."},
            "DisplayName": {"type": "string", "description": "New human-readable site name."},
        },
        "required": ["site_id", "display_name"],
    })
    catalog.schema_registry.register("site-edit-output_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.site-edit-output", "x-aac-schema-version": 1, "type": "object",
        "properties": {"Changed": {"type": "boolean"}}, "required": ["Changed"],
    })
    admitted = catalog.admit_text('''
Capability:
  Id: _AO.core.siteManagement
  Version: 1
  GroupId: _AAC.runtime
  Name: Site management
AuthorizationPermissions:
  - Id: EDIT_SITE
    Name: Edit sites
  - Id: STANDARD_EDITOR
    Name: Standard editor
  - Id: ADVANCED_EDITOR
    Name: Advanced editor
Operations:
  - Id: edit_site
    Authorization: {AllOf: [EDIT_SITE], AnyOf: [STANDARD_EDITOR, ADVANCED_EDITOR]}
    Interactions:
      - Kind: input
        Schema: {Id: _AO.schema.site-edit-input, Version: 1}
      - Kind: final_success_state_result
        Schema: {Id: _AO.schema.site-edit-output, Version: 1}
''')
    source = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract)
    namespace = {}
    exec(source, namespace)
    interface = namespace["AIigSiteManagement_1"]
    input_dto = namespace["AIcgdSiteEditInput_1"]
    assert interface.__aac_source_id__ == "_AO.core.siteManagement"
    assert interface.__aac_source_version__ == 1
    assert input_dto.__canonical_source_id__ == "_AO.schema.site-edit-input"
    assert input_dto.__canonical_source_version__ == 1
    assert input_dto.__canonical_source_resource__ == "site-edit-input_1.json"
    assert "Request data used to edit one site." in input_dto.__doc__
    assert "site_id: Stable site identifier." in input_dto.__doc__
    assert getattr(interface.edit_site_1, "__aac_authorization_all_of__") == ("EDIT_SITE",)
    assert getattr(interface.edit_site_1, "__aac_authorization_any_of__") == ("STANDARD_EDITOR", "ADVANCED_EDITOR")

    output_dto = namespace["AIcgdSiteEditOutput_1"]
    class Impl(interface):
        def edit_site_1(self, request, interaction):
            assert isinstance(request, input_dto)
            return output_dto(changed=True)

    result = AIcObjectCapabilityEndpoint(Impl()).invoke(AIcInvocationInput(
        "i", None, "_AO.core.siteManagement", 1, "edit_site", "provider", {"site_id": "s1", "DisplayName": "New"}
    ))
    assert result.success and result.result == {"Changed": True}


def test_generated_python_binding_reuses_one_dto_type_for_one_canonical_schema():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("repository-identity_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AAC.schema.repository-identity", "x-aac-schema-version": 1,
        "type": "object",
        "properties": {"Id": {"type": "string"}},
        "required": ["Id"],
    })
    admitted = catalog.admit_text('''
Capability:
  Id: _AAC.sourceRepositoryIdentification
  Version: 1
  GroupId: _AAC.runtime
Operations:
  - Id: identify
    Interactions:
      - Kind: input
        Schema: {Id: _AAC.schema.repository-identity, Version: 1}
      - Kind: final_success_state_result
        Schema: {Id: _AAC.schema.repository-identity, Version: 1}
  - Id: normalize
    Interactions:
      - Kind: input
        Schema: {Id: _AAC.schema.repository-identity, Version: 1}
      - Kind: final_success_state_result
        Schema: {Id: _AAC.schema.repository-identity, Version: 1}
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
    assert dto.__canonical_source_id__ == "_AAC.schema.repository-identity"
    assert dto.__canonical_source_version__ == 1
    assert dto.__canonical_source_resource__ == "repository-identity_1.json"


def test_data_entity_binding_generator_uses_versioned_view_methods_and_codec():
    from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

    schemas = AIcSchemaRegistry()
    schemas.register("site_2.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.entity.site",
        "x-aac-schema-version": 2,
        "type": "object",
        "description": "Canonical site data stored by the Data Entity provider.",
        "required": ["Name"],
        "properties": {"Name": {"type": "string", "description": "Human-readable site name."}},
        "additionalProperties": False,
    })
    from eu.algites.frmw.aac.codegen import AIcPythonDataEntityBindingGenerator

    source = AIcPythonDataEntityBindingGenerator(schemas).generate("_AO.entity.site", 2)
    assert "class AIigSite_2" in source
    assert "def get_name_2" in source
    assert "def set_name_2" in source
    assert "class AIcgSiteCodec_2" in source
    assert "__aac_source_id__ = '_AO.entity.site'" in source
    assert "Canonical site data stored by the Data Entity provider." in source
    assert "Human-readable site name." in source


def test_generated_caller_materializes_operation_specific_failure_exception_and_allows_typed_override():
    import pytest

    from eu.algites.frmw.aac.core.instances.api import AIcBinding
    from eu.algites.frmw.aac.core.invocation.api import (
        AIcCallableOperationFailureExceptionFactory,
        AIcOperationFailure,
        AIxCapabilityOperationFailed,
    )
    from eu.algites.frmw.aac.core.invocation.dispatcher import AIcCoreCapabilityHandle, AIcEndpointRegistry, AIcInvocationDispatcher

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("failure-data_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.failure-data", "x-aac-schema-version": 1,
        "type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"],
    })
    admitted = catalog.admit_text('''
Capability:
  Id: _AO.core.failureTest
  Version: 1
  GroupId: _AAC.runtime
Operations:
  - Id: run
    Interactions:
      - Kind: final_failed_state_result_extension
        Schema: {Id: _AO.schema.failure-data, Version: 1}
''')
    source = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract)
    namespace = {}
    exec(source, namespace)
    interface = namespace["AIigFailureTest_1"]
    caller_type = namespace["AIcgFailureTestCaller_1"]
    generated_exception = namespace["AIxgFailureTestFailed_1"]
    failure_dto = namespace["AIcgdFailureData_1"]

    class Impl(interface):
        def run_1(self, interaction):
            raise AIxCapabilityOperationFailed(AIcOperationFailure(
                system_message="failed",
                exception_type="example.ProviderFailure",
                extension={"reason": "BROKEN"},
            ))

    endpoints = AIcEndpointRegistry()
    endpoints.register_object("provider", Impl())
    handle = AIcCoreCapabilityHandle(
        AIcBinding("consumer", "failure", "provider", "_AO.core.failureTest", 1),
        endpoints,
        AIcInvocationDispatcher(catalog),
    )
    caller = caller_type(handle)

    with pytest.raises(generated_exception) as captured:
        caller.run_1()
    assert isinstance(captured.value.additional_data, failure_dto)
    assert captured.value.additional_data.reason == "BROKEN"

    class CustomFailure(generated_exception):
        pass

    interaction = handle.new_operation_interaction(
        exception_factory=AIcCallableOperationFailureExceptionFactory(lambda failure: CustomFailure(failure))
    )
    with pytest.raises(CustomFailure):
        caller.run_1(interaction=interaction)

    invalid_interaction = handle.new_operation_interaction(
        exception_factory=AIcCallableOperationFailureExceptionFactory(lambda failure: AIxCapabilityOperationFailed(failure))
    )
    with pytest.raises(TypeError, match="AIxgFailureTestFailed_1 or its subclass"):
        caller.run_1(interaction=invalid_interaction)


def test_generated_binding_rejects_ambiguous_schema_name_projection():
    import pytest

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    for schema_id in ("alpha.same-name", "beta.same-name"):
        catalog.schema_registry.register(schema_id.replace(".", "-") + "_1.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "x-aac-schema-id": schema_id,
            "x-aac-schema-version": 1,
            "x-jsondefs-name": "same-name",
            "type": "object",
        })
    admitted = catalog.admit_text('''
Capability:
  Id: _AO.core.namingCollision
  Version: 1
  GroupId: _AAC.runtime
Operations:
  - Id: run
    Interactions:
      - Kind: input
        Schema: {Id: alpha.same-name, Version: 1}
      - Kind: final_success_state_result
        Schema: {Id: beta.same-name, Version: 1}
''')
    with pytest.raises(ValueError, match="generated DTO name collision"):
        AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract)

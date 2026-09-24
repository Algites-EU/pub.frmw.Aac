from algites.lib.aac.coreimpl.codegen import AIcPythonCapabilityBindingGenerator
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.invocation import AIcObjectCapabilityEndpoint
from algites.lib.aac.coreintf.invocation import AIcInvocationInput


def test_generated_python_binding_contains_dtos_authorization_and_is_invokable():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
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
  group_id: _AAC.runtime
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
    interactions:
      - kind: INPUT
        schema: {id: _AO.schema.site-edit-input, version: 1}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: _AO.schema.site-edit-output, version: 1}
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
    assert getattr(interface.edit_site_1, "__aac_authorization_all_of__") == ("EDIT_SITE",)
    assert getattr(interface.edit_site_1, "__aac_authorization_any_of__") == ("STANDARD_EDITOR", "ADVANCED_EDITOR")

    output_dto = namespace["AIcgdSiteEditOutput_1"]
    class Impl(interface):
        def edit_site_1(self, request, interaction):
            assert isinstance(request, input_dto)
            return output_dto(changed=True)

    result = AIcObjectCapabilityEndpoint(Impl()).invoke(AIcInvocationInput(
        "i", None, "_AO.core.siteManagement", 1, "edit_site", "provider", {"site_id": "s1", "display_name": "New"}
    ))
    assert result.success and result.result == {"changed": True}


def test_generated_python_binding_reuses_one_dto_type_for_one_canonical_schema():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
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
  group_id: _AAC.runtime
operations:
  - id: identify
    interactions:
      - kind: INPUT
        schema: {id: _AAC.schema.repository-identity, version: 1}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: _AAC.schema.repository-identity, version: 1}
  - id: normalize
    interactions:
      - kind: INPUT
        schema: {id: _AAC.schema.repository-identity, version: 1}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: _AAC.schema.repository-identity, version: 1}
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


def test_data_entity_binding_generator_uses_versioned_view_methods_and_codec():
    from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry

    schemas = AIcSchemaRegistry()
    schemas.register("site_2.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.entity.site",
        "x-aac-schema-version": 2,
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    })
    from algites.lib.aac.coreimpl.codegen import AIcPythonDataEntityBindingGenerator

    source = AIcPythonDataEntityBindingGenerator(schemas).generate("_AO.entity.site", 2)
    assert "class AIigSite_2" in source
    assert "def get_name_2" in source
    assert "def set_name_2" in source
    assert "class AIcgSiteCodec_2" in source
    assert "__aac_source_id__ = '_AO.entity.site'" in source


def test_generated_caller_materializes_operation_specific_failure_exception_and_allows_typed_override():
    import pytest

    from algites.lib.aac.coreintf.instances import AIcBinding
    from algites.lib.aac.coreintf.invocation import (
        AIcCallableOperationFailureExceptionFactory,
        AIcOperationFailure,
        AIxCapabilityOperationFailed,
    )
    from algites.lib.aac.coreimpl.invocation import AIcCoreCapabilityHandle, AIcEndpointRegistry, AIcInvocationDispatcher

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("failure-data_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "_AO.schema.failure-data", "x-aac-schema-version": 1,
        "type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"],
    })
    admitted = catalog.admit_text('''
capability:
  id: _AO.core.failureTest
  version: 1
  group_id: _AAC.runtime
operations:
  - id: run
    interactions:
      - kind: FINAL_FAILED_STATE_RESULT_EXTENSION
        schema: {id: _AO.schema.failure-data, version: 1}
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
            "type": "object",
        })
    admitted = catalog.admit_text('''
capability:
  id: _AO.core.namingCollision
  version: 1
  group_id: _AAC.runtime
operations:
  - id: run
    interactions:
      - kind: INPUT
        schema: {id: alpha.same-name, version: 1}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: beta.same-name, version: 1}
''')
    with pytest.raises(ValueError, match="generated DTO name collision"):
        AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract)

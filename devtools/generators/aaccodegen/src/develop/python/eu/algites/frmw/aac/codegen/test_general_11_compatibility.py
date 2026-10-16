"""Regression coverage for pub.tool.General and pub.lib.General 1.1 naming APIs."""

from types import SimpleNamespace

from eu.algites.frmw.aac.codegen.aic_general_defs_inline_dto_adapter import (
    AIcGeneralDefsInlineDtoAdapter,
)


def test_general_11_generates_versioned_interface_and_dto_names():
    adapter = AIcGeneralDefsInlineDtoAdapter()
    schema = SimpleNamespace(
        resource_name="site_2.json",
        schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "x-aac-schema-id": "_AO.entity.site",
            "x-aac-schema-version": 2,
            "type": "object",
            "properties": {"Name": {"type": "string"}},
            "required": ["Name"],
        },
    )

    normalized = adapter.normalize(schema)
    assert adapter.interface_type_name(normalized) == "AIigSite_2"
    assert adapter.property_name("Name") == "name"
    assert adapter.schema_field_name_constant("Name") == "SCHEMA_FIELD_NAME__NAME"

    dto_name, dto_declaration = adapter.generate(schema)
    assert dto_name == "AIcgdSite_2"
    assert "class AIcgdSite_2" in dto_declaration

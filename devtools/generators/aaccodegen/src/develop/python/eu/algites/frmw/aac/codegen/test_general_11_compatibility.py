"""AAC schema registration must use current General 1.1 Defs -> SDO APIs."""
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry
from eu.algites.frmw.aac.codegen.aic_aac_schema_type_generator import AIcAacSchemaTypeGenerator


def test_general_11_generates_versioned_aiig_aiigd_and_aicgd():
    registry = AIcSchemaRegistry()
    registered = registry.register('site_2.json', {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'x-aac-schema-id': '_AO.entity.site',
        'x-aac-schema-version': 2,
        'type': 'object',
        'properties': {'Name': {'type': 'string'}},
        'required': ['Name'],
    })
    result = AIcAacSchemaTypeGenerator().generate(registered)
    assert result.contract.type_name == 'AIigSite_2'
    assert result.mutable_interface.type_name == 'AIigdSite_2'
    assert result.implementation.type_name == 'AIcgdSite_2'
    assert result.contract.primary_type.fully_qualified_type_name.endswith('.aiig_site_2.AIigSite_2')
    assert result.implementation.primary_type.fully_qualified_type_name.endswith('.aicgd_site_2.AIcgdSite_2')
    assert result.implementation.primary_type.source_definition_id == '_AO.entity.site'
    assert result.implementation.primary_type.source_definition_version == 2

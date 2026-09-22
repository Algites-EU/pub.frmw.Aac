import pytest

from algites.lib.aac.coreimpl.errors import AIxSchemaValidationError
from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry


def test_simpleaudit_defaults_are_applied():
    registry = AIcSchemaRegistry()
    registry.register_package_resource("algites.lib.aac.simpleaudit", "schemas/simpleaudit-config_1.json")
    assert registry.normalize("simpleaudit-config_1.json", {}) == {
        "output": {"type": "STDOUT"},
        "format": "JSON",
    }


def test_file_output_requires_path():
    registry = AIcSchemaRegistry()
    registry.register_package_resource("algites.lib.aac.simpleaudit", "schemas/simpleaudit-config_1.json")
    with pytest.raises(AIxSchemaValidationError):
        registry.normalize("simpleaudit-config_1.json", {"output": {"type": "FILE"}})


def test_schema_identity_is_explicit_and_independent_from_filename():
    registry = AIcSchemaRegistry()
    registered = registry.register(
        "arbitrary-file-name.json",
        {
            "x-aac-schema-id": "vendor.foo.data",
            "x-aac-schema-version": 7,
            "type": "object",
        },
    )
    assert registered.id == "vendor.foo.data"
    assert registered.version == 7
    assert registry.get_identity("vendor.foo.data", 7) is registered
    assert registry.contains_identity("vendor.foo.data", 7)


def test_schema_without_explicit_identity_is_rejected():
    registry = AIcSchemaRegistry()
    with pytest.raises(ValueError, match="x-aac-schema-id"):
        registry.register("thing_12.json", {"type": "object"})
    with pytest.raises(ValueError, match="x-aac-schema-version"):
        registry.register("thing_12.json", {"x-aac-schema-id": "vendor.foo.thing", "type": "object"})


def test_data_entity_reference_annotation_is_discovered_from_schema_field():
    registry = AIcSchemaRegistry()
    registry.register(
        "monitoring-data.json",
        {
            "x-aac-schema-id": "vendor.monitoring.site-data",
            "x-aac-schema-version": 3,
            "type": "object",
            "properties": {
                "site_uid": {
                    "type": "string",
                    "x-aac-data-entity-reference": {"schema_id": "_AO.entity.site"},
                }
            },
        },
    )
    references = registry.data_entity_references("vendor.monitoring.site-data", 3)
    assert len(references) == 1
    assert references[0].target_schema_id == "_AO.entity.site"
    assert references[0].schema_path[-2:] == ("properties", "site_uid")


def test_invalid_data_entity_reference_annotation_is_rejected():
    registry = AIcSchemaRegistry()
    with pytest.raises(ValueError, match="requires non-empty schema_id"):
        registry.register_text(
            "bad.json",
            '''{
              "x-aac-schema-id": "vendor.foo.bad",
              "x-aac-schema-version": 1,
              "type": "object",
              "properties": {
                "site_uid": {
                  "type": "string",
                  "x-aac-data-entity-reference": {}
                }
              }
            }''',
        )


def test_resolved_configuration_allows_missing_top_level_required_but_validates_present_nested_structure():
    registry = AIcSchemaRegistry()
    registry.register("runtime-config.json", {
        "x-aac-schema-id": "vendor.foo.runtime-config",
        "x-aac-schema-version": 1,
        "type": "object",
        "properties": {
            "database": {
                "type": "object",
                "properties": {"host": {"type": "string"}},
                "required": ["host"],
            }
        },
        "required": ["database"],
    })
    assert registry.validate_resolved_configuration("runtime-config.json", {}) == ()
    errors = registry.validate_resolved_configuration("runtime-config.json", {"database": {}})
    assert errors and "host" in errors[0]

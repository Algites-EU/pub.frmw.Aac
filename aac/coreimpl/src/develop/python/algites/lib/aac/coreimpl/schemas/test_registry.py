import pytest

from algites.lib.aac.coreimpl.errors import AIxSchemaValidationError
from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry, split_versioned_schema_name


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


def test_schema_filename_version_convention_is_enforced():
    assert split_versioned_schema_name("thing_12.json") == ("thing", 12)
    with pytest.raises(ValueError):
        split_versioned_schema_name("thing-v1.json")


def test_resolved_configuration_allows_missing_top_level_required_but_validates_present_nested_structure():
    registry = AIcSchemaRegistry()
    registry.register("runtime-config_1.json", {
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
    assert registry.validate_resolved_configuration("runtime-config_1.json", {}) == ()
    errors = registry.validate_resolved_configuration("runtime-config_1.json", {"database": {}})
    assert errors and "host" in errors[0]

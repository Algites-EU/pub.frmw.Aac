from importlib import resources


def test_descriptor_and_versioned_schema_are_packaged_sources():
    package = resources.files("algites.lib.aac.simpleaudit")
    assert package.joinpath("component.yml").is_file()
    assert package.joinpath("schemas/simpleaudit-config_1.json").is_file()

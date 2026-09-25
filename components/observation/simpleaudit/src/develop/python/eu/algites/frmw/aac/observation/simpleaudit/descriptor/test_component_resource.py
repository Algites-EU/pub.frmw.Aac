from pathlib import Path


def _artifact_root() -> Path:
    return next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())


def test_descriptor_and_versioned_schema_are_technology_neutral_sources():
    artifact = _artifact_root()
    assert (
        artifact
        / "src/product/config/eu/algites/frmw/aac/observation/simpleaudit/component.yml"
    ).is_file()
    assert (
        artifact
        / "src/product/jsondefs/eu/algites/frmw/aac/observation/simpleaudit/schemas/simpleaudit-config_1.json"
    ).is_file()

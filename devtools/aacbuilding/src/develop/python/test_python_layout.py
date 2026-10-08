from python_layout import stage_python_product_tree, validate_repository_source_layout


def test_config_document_with_sidecar_is_rejected_in_canonical_yamldefs(tmp_path):
    root = tmp_path / "artifact/src/product/yamldefs/eu/example"
    root.mkdir(parents=True)
    (root / "capability_1.yml").write_text("Capability: {Id: example, Version: 1}\n")
    (root / "capability_1.yml.meta.yml").write_text("GlobalPublicationPathId: example\n")
    errors = validate_repository_source_layout(tmp_path)
    assert len(errors) == 1
    assert "capability_1.yml: unsupported file in canonical yamldefs root" in errors[0]


def test_canonical_schema_and_sidecar_are_allowed(tmp_path):
    root = tmp_path / "artifact/src/product/yamldefs/eu/example"
    root.mkdir(parents=True)
    (root / "document_1.yamldef.schema.json").write_text('{"type": "object"}')
    (root / "document_1.yamldef.schema.json.meta.yml").write_text("GlobalPublicationPathId: example\n")
    assert validate_repository_source_layout(tmp_path) == []


def test_config_move_keeps_the_packaged_resource_path(tmp_path):
    artifact = tmp_path / "repo/artifact"
    root = artifact / "src/product/config/eu/example/definitions"
    root.mkdir(parents=True)
    content = "Capability: {Id: example, Version: 1}\n"
    (root / "capability_1.yml").write_text(content)
    assert validate_repository_source_layout(tmp_path / "repo") == []
    staged = stage_python_product_tree(artifact, tmp_path / "staged")
    assert (staged / "eu/example/definitions/capability_1.yml").read_text() == content

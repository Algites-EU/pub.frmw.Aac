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


def test_public_python_types_have_one_type_per_deterministically_named_module():
    import ast
    import re
    from pathlib import Path

    repository = Path(__file__).resolve().parents[5]
    violations = []
    checked = 0
    for source_file in sorted(repository.glob("**/src/product/python/**/*.py")):
        if "build" in source_file.relative_to(repository).parts:
            continue
        source = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        public_classes = [
            statement.name for statement in source.body
            if isinstance(statement, ast.ClassDef)
            and statement.name.startswith(("AIc", "AId", "AIi", "AIn", "AIx", "AIg"))
        ]
        if not public_classes:
            continue
        checked += len(public_classes)
        if len(public_classes) > 1:
            violations.append(f"{source_file}: more than one public Algites class: {public_classes}")
        for name in public_classes:
            suffix = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name[3:])
            suffix = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", suffix).lower()
            expected = name[:3].lower() + "_" + suffix
            if source_file.stem != expected:
                violations.append(f"{source_file}: {name} requires {expected}.py")
    assert checked > 0, "Expected to inspect public Algites classes"
    assert violations == [], "\n".join(violations)

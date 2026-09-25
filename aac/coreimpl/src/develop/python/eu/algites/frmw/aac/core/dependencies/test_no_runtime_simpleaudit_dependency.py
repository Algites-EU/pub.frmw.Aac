from pathlib import Path


def test_coreimpl_product_source_does_not_reference_simpleaudit():
    test_file = Path(__file__).resolve()
    artifact = next(
        parent
        for parent in test_file.parents
        if parent.name == "coreimpl" and (parent / "src/product/python").is_dir()
    )
    package = artifact / "src/product/python/eu/algites/frmw/aac/core"
    for source in package.rglob("*.py"):
        assert "eu.algites.frmw.aac.observation.simpleaudit" not in source.read_text(encoding="utf-8")

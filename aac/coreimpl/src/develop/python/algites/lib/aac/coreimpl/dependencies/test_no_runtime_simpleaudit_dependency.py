from pathlib import Path


def test_coreimpl_product_source_does_not_reference_simpleaudit():
    product = Path(__file__).resolve().parents[7] / "product" / "python" / "algites" / "lib" / "aac" / "coreimpl"
    # Path calculation can vary under importlib pytest mode; inspect installed module tree instead.
    import algites.lib.aac.coreimpl as coreimpl
    package = Path(coreimpl.__file__).parent
    for source in package.rglob("*.py"):
        assert "algites.lib.aac.simpleaudit" not in source.read_text(encoding="utf-8")

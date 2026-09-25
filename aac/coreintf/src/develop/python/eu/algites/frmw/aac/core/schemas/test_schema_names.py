from pathlib import Path
import re


def test_versioned_schema_names_use_underscore_suffix():
    schema_root = Path(__file__).resolve().parents[9] / "src/product/jsondefs/eu/algites/frmw/aac/core"
    names = sorted(item.name for item in schema_root.rglob("*.json"))
    assert names
    assert all(re.search(r"_[0-9]+\.json$", name) for name in names)
    assert not any("-v1" in name for name in names)

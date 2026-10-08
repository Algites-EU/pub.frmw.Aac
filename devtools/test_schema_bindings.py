#!/usr/bin/env python3
"""Verify fresh generator outputs without depending on a preinstalled artifact distribution."""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "devtools/schema-field-bindings.json").read_text())
ARTIFACTS = [MANIFEST["artifact"], MANIFEST["implementation_artifact"]]
for artifact in ARTIFACTS:
    sys.path.insert(0, str(ROOT / artifact / "src/product/python.gen"))


class AItcSchemaBindings(unittest.TestCase):
    """Exercise the generated package layout and real contract implementation."""

    def test_every_generated_python_type_has_the_schema_package_and_correct_artifact(self):
        ownership = ROOT / "build/run/schema-bindings/generated-files.json"
        self.assertTrue(ownership.is_file(), "Run generateModustroSchemaBindings before tests")
        paths = [ROOT / value for value in json.loads(ownership.read_text()) if value.endswith(".py")]
        self.assertGreater(len(paths), 0)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file())
                relative = path.relative_to(ROOT)
                offset = next(i for i, part in enumerate(relative.parts) if part == "python.gen")
                module_path = Path(*relative.parts[offset + 1:])
                module = importlib.import_module(".".join(module_path.with_suffix("").parts))
                types = [value for value in vars(module).values() if inspect.isclass(value)
                         and value.__module__ == module.__name__ and hasattr(value, "__canonical_source_resource__")]
                self.assertEqual(len(types), 1, "Each module owns one schema type")
                value = types[0]
                schema = Path(value.__canonical_source_resource__.split("#", 1)[0])
                source_offset = next(i for i, part in enumerate(schema.parts) if part in {"jsondefs", "yamldefs"})
                self.assertEqual(module_path.parent, Path(*schema.parts[source_offset + 1:]).parent)
                if value.__name__.startswith("AIig"):
                    self.assertIn(MANIFEST["artifact"], path.as_posix())
                    self.assertTrue(inspect.isabstract(value))
                    self.assertFalse(dataclasses.is_dataclass(value))
                    with self.assertRaises(TypeError):
                        value()
                    for name in vars(value):
                        if name.startswith("SCHEMA_FIELD_NAME__"):
                            self.assertIn(name, value.__annotations__)
                elif value.__name__.startswith("AIcgd"):
                    self.assertIn(MANIFEST["implementation_artifact"], path.as_posix())
                    self.assertFalse(inspect.isabstract(value))
                    self.assertTrue(dataclasses.is_dataclass(value))
                    contract = value.__bases__[0]
                    self.assertTrue(contract.__name__.startswith("AIig"))
                    self.assertTrue(inspect.isabstract(contract))
                    fields = {field.name for field in dataclasses.fields(value)}
                    self.assertFalse(any(name.startswith("SCHEMA_FIELD_NAME__") for name in fields))
                    self.assertTrue(fields <= set(contract.__annotations__))
                else:
                    self.assertTrue(value.__name__.startswith("AIng"))
                    self.assertIn(MANIFEST["artifact"], path.as_posix())

    def test_wire_round_trip_preserves_absence_and_constant_names(self):
        from eu.algites.frmw.aac.core.packages.aiig_active_package_set_1 import AIigActivePackageSet_1
        from eu.algites.frmw.aac.core.packages.aicgd_active_package_set_1 import AIcgdActivePackageSet_1
        original = {"FormatVersion": 1, "RecordRevision": 0, "Selections": []}
        value = AIcgdActivePackageSet_1.from_mapping(original)
        self.assertIsInstance(value, AIigActivePackageSet_1)
        self.assertEqual(value.to_mapping(), original)
        self.assertEqual(AIigActivePackageSet_1.SCHEMA_FIELD_NAME__SELECTIONS, "Selections")
        self.assertNotIn("$schema", value.to_mapping())
        self.assertFalse(hasattr(value, "__dict__"))


if __name__ == "__main__":
    unittest.main()

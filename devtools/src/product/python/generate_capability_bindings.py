#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from algites.lib.aac.coreimpl.codegen import AIcPythonCapabilityBindingGenerator
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Python AAC interface/DTO bindings from a canonical capability contract")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--schema-dir", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    catalog = AIcActiveContractCatalog()
    for directory in args.schema_dir:
        for schema in sorted(directory.glob("*.json")):
            catalog.schema_registry.register_file(schema)
    admitted = catalog.admit_file(args.contract)
    source = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate(admitted.contract, canonical_resource=args.contract.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

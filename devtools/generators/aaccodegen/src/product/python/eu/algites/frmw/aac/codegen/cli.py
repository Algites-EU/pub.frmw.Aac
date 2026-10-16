from __future__ import annotations

import argparse
from pathlib import Path

from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

from .generators import AIcPythonCapabilityBindingGenerator, AIcPythonDataEntityBindingGenerator


def _register_schemas(registry: AIcSchemaRegistry, directories: list[Path]) -> None:
    for directory in directories:
        for schema in sorted(directory.glob("*.json")):
            registry.register_file(schema)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate canonical AAC technology bindings")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capability = subparsers.add_parser("capability", help="Generate Python capability bindings")
    capability.add_argument("contract", type=Path)
    capability.add_argument("--schema-dir", type=Path, action="append", default=[])
    capability.add_argument("--output", type=Path, required=True)
    capability.add_argument("--generated-root", type=Path, default=None,
                            help="Source root for standalone General-generated AIig/AIcgd modules (default: output parent)")

    dataentity = subparsers.add_parser("dataentity", help="Generate a Python Data Entity view and codec")
    dataentity.add_argument("schema", type=Path)
    dataentity.add_argument("--schema-dir", type=Path, action="append", default=[])
    dataentity.add_argument("--schema-id", required=True)
    dataentity.add_argument("--schema-version", type=int, required=True)
    dataentity.add_argument("--output", type=Path, required=True)
    dataentity.add_argument("--generated-root", type=Path, default=None)

    args = parser.parse_args()
    if args.command == "capability":
        from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
        catalog = AIcActiveContractCatalog()
        _register_schemas(catalog.schema_registry, args.schema_dir)
        admitted = catalog.admit_file(args.contract)
        result = AIcPythonCapabilityBindingGenerator(catalog.schema_registry).generate_sources(
            admitted.contract, canonical_resource=args.contract.name
        )
    else:
        registry = AIcSchemaRegistry()
        _register_schemas(registry, args.schema_dir)
        registry.register_file(args.schema)
        result = AIcPythonDataEntityBindingGenerator(registry).generate_sources(args.schema_id, args.schema_version)
    root = args.generated_root or args.output.parent
    destinations = [(root / unit.relative_path, unit) for unit in result.schema_sources]
    for dest, unit in destinations:
        if dest.exists() and dest.read_text(encoding='utf-8') != unit.source:
            raise ValueError(f'Conflicting canonical type generation at {dest}')
    for dest, unit in destinations:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_text(unit.source, encoding='utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.binding_source, encoding='utf-8')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

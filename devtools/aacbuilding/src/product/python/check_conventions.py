#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

from python_layout import validate_python_distribution_paths, validate_repository_source_layout

ROOT = Path(__file__).resolve().parents[5]
ALLOWED = ("AIi", "AIc", "AIn", "AIx", "AIig", "AIcg", "AIigd", "AIcgd", "AIr")
PUBLIC_TYPE_PATTERN = re.compile(r"^AI[a-z]+[A-Z]")


def type_module_name(type_name: str) -> str:
    match = re.match(r"^(AI[a-z]+)(.*)$", type_name)
    if match is None:
        raise ValueError(f"unsupported Algites type name {type_name!r}")
    prefix = match.group(1).lower()
    remainder = match.group(2)
    remainder = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", remainder)
    remainder = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", remainder).lower()
    return prefix if not remainder else f"{prefix}_{remainder}"


def validate_public_type_modules(paths: list[Path]) -> list[str]:
    problems: list[str] = []
    for path in sorted(paths):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        public_types = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef) and PUBLIC_TYPE_PATTERN.match(node.name)
        ]
        if len(public_types) > 1:
            problems.append(
                f"{path.relative_to(ROOT)}: defines multiple main public Algites types: {', '.join(public_types)}"
            )
        elif public_types:
            expected_name = f"{type_module_name(public_types[0])}.py"
            if path.name != expected_name:
                problems.append(
                    f"{path.relative_to(ROOT)}: public type {public_types[0]} must be in deterministic module {expected_name!r}"
                )
    return problems


def main() -> int:
    errors: list[str] = []
    paths = [
        *(ROOT / "aac").rglob("src/product/python/**/*.py"),
        *(ROOT / "components").rglob("src/product/python/**/*.py"),
        *(ROOT / "devtools").rglob("src/product/python/**/*.py"),
    ]
    for path in sorted(paths):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith(ALLOWED):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: class {node.name} violates Algites prefix convention"
                )

    errors.extend(validate_public_type_modules(paths))
    errors.extend(validate_repository_source_layout(ROOT))
    errors.extend(validate_python_distribution_paths(ROOT))

    if errors:
        raise SystemExit("\n".join(errors))
    print("Algites Python naming, one-public-type-per-module, source-layout, and distribution-path conventions OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

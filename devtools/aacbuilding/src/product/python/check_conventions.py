#!/usr/bin/env python3
from __future__ import annotations
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
ALLOWED=("AIi","AIc","AIn","AIx","AIig","AIcg","AIigd","AIcgd","AIr")
errors=[]
paths=[*(ROOT/'aac').rglob('src/product/python/**/*.py'), *(ROOT/'components').rglob('src/product/python/**/*.py'), *(ROOT/'devtools').rglob('src/product/python/**/*.py')]
for path in sorted(paths):
    tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith(ALLOWED):
            errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: class {node.name} violates Algites prefix convention")
if errors:
    raise SystemExit("\n".join(errors))
print("Algites Python type-prefix conventions OK")

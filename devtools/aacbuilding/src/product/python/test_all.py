#!/usr/bin/env python3
"""Run AAC tests in bounded functional blocks using repository-central derived state."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from python_layout import stage_python_product_tree

ROOT = Path(__file__).resolve().parents[5]


def run_directory(artifact: Path) -> Path:
    return ROOT / "build/run" / artifact.relative_to(ROOT) / "run"


def staged_product_path(artifact: Path) -> Path:
    return stage_python_product_tree(artifact, run_directory(artifact) / "develop/product-tree")


def run_pytest(cwd: Path, product_paths: list[Path], targets: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in product_paths)
    run_dir = run_directory(cwd)
    env["PYTHONPYCACHEPREFIX"] = str(run_dir / "develop/pycache")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            f"cache_dir={run_dir / 'develop/pytest/cache'}",
            *targets,
        ],
        cwd=cwd,
        env=env,
        check=True,
    )


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/sync_versions.py"), "--check"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/check_conventions.py")],
        cwd=ROOT,
        check=True,
    )

    coreintf = staged_product_path(ROOT / "aac/coreintf")
    simpleaudit = staged_product_path(ROOT / "components/observation/simpleaudit")
    sigstore = staged_product_path(ROOT / "aac/verify/sigstore")
    coreimpl = staged_product_path(ROOT / "aac/coreimpl")
    uiintf = staged_product_path(ROOT / "aac/uiintf")
    uiqt = staged_product_path(ROOT / "aac/uiqt")
    yamlfsdes = staged_product_path(ROOT / "components/dataentity/yamlfsdes")
    codegen = staged_product_path(ROOT / "devtools/generators/aaccodegen")

    run_pytest(ROOT / "aac/coreintf", [coreintf], ["src/develop/python"])
    run_pytest(ROOT / "components/observation/simpleaudit", [coreintf, simpleaudit], ["src/develop/python"])
    run_pytest(ROOT / "aac/verify/sigstore", [coreintf, sigstore], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiintf", [coreintf, uiintf], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiqt", [coreintf, simpleaudit, coreimpl, uiintf, uiqt], ["src/develop/python"])
    run_pytest(ROOT / "components/dataentity/yamlfsdes", [coreintf, coreimpl, yamlfsdes], ["src/develop/python"])
    run_pytest(ROOT / "devtools/generators/aaccodegen", [coreintf, coreimpl, codegen], ["src/develop/python"])

    base = ROOT / "aac/coreimpl"
    paths = [coreintf, simpleaudit, coreimpl, codegen]
    groups = [
        [
            "src/develop/python/eu/algites/frmw/aac/core/capability",
            "src/develop/python/eu/algites/frmw/aac/core/dataentity",
            "src/develop/python/eu/algites/frmw/aac/core/schemas",
            "src/develop/python/eu/algites/frmw/aac/core/persistence",
        ],
        [
            "src/develop/python/eu/algites/frmw/aac/core/entitlement",
            "src/develop/python/eu/algites/frmw/aac/core/configuration",
            "src/develop/python/eu/algites/frmw/aac/core/authentication",
            "src/develop/python/eu/algites/frmw/aac/core/bootstrap",
            "src/develop/python/eu/algites/frmw/aac/core/packages",
            "src/develop/python/eu/algites/frmw/aac/core/catalog",
            "src/develop/python/eu/algites/frmw/aac/core/resolution",
        ],
        [
            "src/develop/python/eu/algites/frmw/aac/core/lifecycle",
            "src/develop/python/eu/algites/frmw/aac/core/invocation",
            "src/develop/python/eu/algites/frmw/aac/core/interaction",
            "src/develop/python/eu/algites/frmw/aac/core/operation_parameters",
            "src/develop/python/eu/algites/frmw/aac/core/process",
            "src/develop/python/eu/algites/frmw/aac/core/readiness",
            "src/develop/python/eu/algites/frmw/aac/core/subinterpreter",
        ],
        [
            "src/develop/python/eu/algites/frmw/aac/core/bindings",
            "src/develop/python/eu/algites/frmw/aac/core/descriptor",
            "src/develop/python/eu/algites/frmw/aac/core/migration",
        ],
        [
            "src/develop/python/eu/algites/frmw/aac/core/dependencies",
            "src/develop/python/eu/algites/frmw/aac/core/observation",
            "src/develop/python/eu/algites/frmw/aac/core/provisioning",
        ],
        [
            "src/develop/python/eu/algites/frmw/aac/core/graph",
            "src/develop/python/eu/algites/frmw/aac/core/runtime",
            "src/develop/python/eu/algites/frmw/aac/core/namespace",
            "src/develop/python/eu/algites/frmw/aac/core/upgrade",
            "src/develop/python/eu/algites/frmw/aac/core/solver",
        ],
    ]
    for group in groups:
        run_pytest(base, paths, group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

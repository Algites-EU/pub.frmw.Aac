#!/usr/bin/env python3
"""Run AAC tests in bounded functional blocks using repository-central derived state."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def run_directory(artifact: Path) -> Path:
    return ROOT / "build/run" / artifact.relative_to(ROOT) / "run"


def run_pytest(cwd: Path, product_paths: list[Path], targets: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in product_paths)
    run_dir = run_directory(cwd)
    env["PYTHONPYCACHEPREFIX"] = str(run_dir / "develop/pycache")
    subprocess.run([
        sys.executable, "-m", "pytest", "-q",
        "-o", f"cache_dir={run_dir / 'develop/pytest/cache'}",
        *targets,
    ], cwd=cwd, env=env, check=True)


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/sync_versions.py"), "--check"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/check_conventions.py")], cwd=ROOT, check=True)
    coreintf = ROOT / "aac/coreintf/src/product/python"
    simpleaudit = ROOT / "aac/simpleaudit/src/product/python"
    sigstore = ROOT / "aac/verify/sigstore/src/product/python"
    coreimpl = ROOT / "aac/coreimpl/src/product/python"
    uiintf = ROOT / "aac/uiintf/src/product/python"
    uiqt = ROOT / "aac/uiqt/src/product/python"
    yamlfsdes = ROOT / "components/dataentity/yamlfsdes/src/product/python"
    codegen = ROOT / "devtools/generators/aaccodegen/src/product/python"

    run_pytest(ROOT / "aac/coreintf", [coreintf], ["src/develop/python"])
    run_pytest(ROOT / "aac/simpleaudit", [coreintf, simpleaudit], ["src/develop/python"])
    run_pytest(ROOT / "aac/verify/sigstore", [coreintf, sigstore], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiintf", [coreintf, uiintf], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiqt", [coreintf, simpleaudit, coreimpl, uiintf, uiqt], ["src/develop/python"])
    run_pytest(ROOT / "components/dataentity/yamlfsdes", [coreintf, coreimpl, yamlfsdes], ["src/develop/python"])
    run_pytest(ROOT / "devtools/generators/aaccodegen", [coreintf, coreimpl, codegen], ["src/develop/python"])

    base = ROOT / "aac/coreimpl"
    paths = [coreintf, simpleaudit, coreimpl, codegen]
    groups = [
        ["src/develop/python/algites/frmw/aac/coreimpl/capability", "src/develop/python/algites/frmw/aac/coreimpl/dataentity", "src/develop/python/algites/frmw/aac/coreimpl/schemas", "src/develop/python/algites/frmw/aac/coreimpl/persistence"],
        ["src/develop/python/algites/frmw/aac/coreimpl/entitlement", "src/develop/python/algites/frmw/aac/coreimpl/configuration", "src/develop/python/algites/frmw/aac/coreimpl/authentication", "src/develop/python/algites/frmw/aac/coreimpl/bootstrap", "src/develop/python/algites/frmw/aac/coreimpl/packages", "src/develop/python/algites/frmw/aac/coreimpl/catalog", "src/develop/python/algites/frmw/aac/coreimpl/resolution"],
        ["src/develop/python/algites/frmw/aac/coreimpl/lifecycle", "src/develop/python/algites/frmw/aac/coreimpl/invocation", "src/develop/python/algites/frmw/aac/coreimpl/interaction", "src/develop/python/algites/frmw/aac/coreimpl/operation_parameters", "src/develop/python/algites/frmw/aac/coreimpl/process", "src/develop/python/algites/frmw/aac/coreimpl/readiness", "src/develop/python/algites/frmw/aac/coreimpl/subinterpreter"],
        ["src/develop/python/algites/frmw/aac/coreimpl/bindings", "src/develop/python/algites/frmw/aac/coreimpl/descriptor", "src/develop/python/algites/frmw/aac/coreimpl/migration"],
        ["src/develop/python/algites/frmw/aac/coreimpl/dependencies", "src/develop/python/algites/frmw/aac/coreimpl/observation", "src/develop/python/algites/frmw/aac/coreimpl/provisioning"],
        ["src/develop/python/algites/frmw/aac/coreimpl/graph", "src/develop/python/algites/frmw/aac/coreimpl/runtime", "src/develop/python/algites/frmw/aac/coreimpl/namespace", "src/develop/python/algites/frmw/aac/coreimpl/upgrade", "src/develop/python/algites/frmw/aac/coreimpl/solver"],
    ]
    for group in groups:
        run_pytest(base, paths, group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run AAC tests in small functional blocks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def run_pytest(cwd: Path, product_paths: list[Path], targets: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in product_paths)
    env["PYTHONPYCACHEPREFIX"] = str(cwd / "run/develop/pycache")
    subprocess.run([sys.executable, "-m", "pytest", "-q", *targets], cwd=cwd, env=env, check=True)


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "devtools/src/product/python/sync_versions.py"), "--check"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "devtools/src/product/python/check_conventions.py")], cwd=ROOT, check=True)
    coreintf = ROOT / "aac/coreintf/src/product/python"
    simpleaudit = ROOT / "aac/simpleaudit/src/product/python"
    sigstore = ROOT / "aac/verify/sigstore/src/product/python"
    coreimpl = ROOT / "aac/coreimpl/src/product/python"
    uiintf = ROOT / "aac/uiintf/src/product/python"
    uiqt = ROOT / "aac/uiqt/src/product/python"

    run_pytest(ROOT / "aac/coreintf", [coreintf], ["src/develop/python"])
    run_pytest(ROOT / "aac/simpleaudit", [coreintf, simpleaudit], ["src/develop/python"])
    run_pytest(ROOT / "aac/verify/sigstore", [coreintf, sigstore], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiintf", [coreintf, uiintf], ["src/develop/python"])
    run_pytest(ROOT / "aac/uiqt", [coreintf, simpleaudit, coreimpl, uiintf, uiqt], ["src/develop/python"])

    base = ROOT / "aac/coreimpl"
    paths = [coreintf, simpleaudit, coreimpl]
    groups = [
        ["src/develop/python/algites/lib/aac/coreimpl/contracts", "src/develop/python/algites/lib/aac/coreimpl/schemas", "src/develop/python/algites/lib/aac/coreimpl/persistence"],
        ["src/develop/python/algites/lib/aac/coreimpl/entitlement", "src/develop/python/algites/lib/aac/coreimpl/configuration", "src/develop/python/algites/lib/aac/coreimpl/authentication", "src/develop/python/algites/lib/aac/coreimpl/bootstrap", "src/develop/python/algites/lib/aac/coreimpl/packages", "src/develop/python/algites/lib/aac/coreimpl/catalog", "src/develop/python/algites/lib/aac/coreimpl/resolution"],
        ["src/develop/python/algites/lib/aac/coreimpl/lifecycle", "src/develop/python/algites/lib/aac/coreimpl/invocation", "src/develop/python/algites/lib/aac/coreimpl/interaction", "src/develop/python/algites/lib/aac/coreimpl/process", "src/develop/python/algites/lib/aac/coreimpl/subinterpreter"],
        ["src/develop/python/algites/lib/aac/coreimpl/bindings", "src/develop/python/algites/lib/aac/coreimpl/codegen", "src/develop/python/algites/lib/aac/coreimpl/descriptor", "src/develop/python/algites/lib/aac/coreimpl/migration"],
        ["src/develop/python/algites/lib/aac/coreimpl/dependencies", "src/develop/python/algites/lib/aac/coreimpl/observation", "src/develop/python/algites/lib/aac/coreimpl/provisioning"],
        ["src/develop/python/algites/lib/aac/coreimpl/graph", "src/develop/python/algites/lib/aac/coreimpl/runtime", "src/develop/python/algites/lib/aac/coreimpl/namespace", "src/develop/python/algites/lib/aac/coreimpl/upgrade", "src/develop/python/algites/lib/aac/coreimpl/solver"],
    ]
    for group in groups:
        run_pytest(base, paths, group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

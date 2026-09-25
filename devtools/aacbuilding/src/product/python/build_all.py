#!/usr/bin/env python3
"""Build all AAC Python artifacts into repository-central build/run state."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
ARTIFACTS = (
    ROOT / "aac/coreintf",
    ROOT / "aac/simpleaudit",
    ROOT / "aac/coreimpl",
    ROOT / "aac/verify/sigstore",
    ROOT / "aac/uiintf",
    ROOT / "aac/uiqt",
    ROOT / "components/dataentity/yamlfsdes",
    ROOT / "devtools/aacbuilding",
    ROOT / "devtools/generators/aaccodegen",
)


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def artifact_run_directory(artifact: Path) -> Path:
    return ROOT / "build/run" / artifact.relative_to(ROOT) / "run"


def clean_spillover(artifact: Path) -> None:
    shutil.rmtree(artifact / "build", ignore_errors=True)
    for egg_info in (artifact / "src/product/python").glob("*.egg-info"):
        shutil.rmtree(egg_info, ignore_errors=True)


def main() -> int:
    run([sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/sync_versions.py")], ROOT)
    for artifact in ARTIFACTS:
        artifact = artifact.resolve()
        bld = artifact_run_directory(artifact) / "bld"
        shutil.rmtree(bld, ignore_errors=True)
        bld.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps", "--wheel-dir", str(bld), "."], artifact)
        run([sys.executable, "-c", f"import setuptools.build_meta as b; print(b.build_sdist({str(bld)!r}))"], artifact)
        clean_spillover(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

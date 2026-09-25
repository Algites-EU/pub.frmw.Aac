#!/usr/bin/env python3
"""Build all AAC Python artifacts into repository-central build/run state."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from python_layout import merge_neutral_product_roots_into_python_tree

ROOT = Path(__file__).resolve().parents[5]
ARTIFACTS = (
    ROOT / "aac/coreintf",
    ROOT / "components/observation/simpleaudit",
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


def copy_source_project(artifact: Path, target: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(
        artifact,
        target,
        ignore=shutil.ignore_patterns(
            "build",
            "run",
            ".gradle",
            ".pytest_cache",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.egg-info",
        ),
    )
    merge_neutral_product_roots_into_python_tree(artifact, target / "src/product/python")


def main() -> int:
    run([sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/sync_versions.py")], ROOT)
    run([sys.executable, str(ROOT / "devtools/aacbuilding/src/product/python/check_conventions.py")], ROOT)
    for artifact in ARTIFACTS:
        artifact = artifact.resolve()
        bld = artifact_run_directory(artifact) / "bld"
        project = bld / "project"
        dist = bld / "dist"
        shutil.rmtree(bld, ignore_errors=True)
        dist.mkdir(parents=True, exist_ok=True)
        copy_source_project(artifact, project)
        run(
            [sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps", "--wheel-dir", str(dist), "."],
            project,
        )
        run(
            [sys.executable, "-c", f"import setuptools.build_meta as b; print(b.build_sdist({str(dist)!r}))"],
            project,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

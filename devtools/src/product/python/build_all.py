#!/usr/bin/env python3
"""Build all AAC Python artifacts into each artifact's run/bld directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS = (
    ROOT / "aac/coreintf",
    ROOT / "aac/simpleaudit",
    ROOT / "aac/coreimpl",
    ROOT / "aac/verify/sigstore",
    ROOT / "aac/uiintf",
    ROOT / "aac/uiqt",
    ROOT / "devtools",
)


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def clean_spillover(artifact: Path) -> None:
    shutil.rmtree(artifact / "build", ignore_errors=True)
    for egg_info in (artifact / "src/product/python").glob("*.egg-info"):
        shutil.rmtree(egg_info, ignore_errors=True)


def main() -> int:
    run([sys.executable, str(ROOT / "devtools/src/product/python/sync_versions.py")], ROOT)
    for artifact in ARTIFACTS:
        artifact = artifact.resolve()
        bld = artifact / "run/bld"
        bld.mkdir(parents=True, exist_ok=True)
        for child in bld.iterdir():
            if child.name != ".gitkeep":
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps", "--wheel-dir", str(bld), "."], artifact)
        run([sys.executable, "-c", "import setuptools.build_meta as b; print(b.build_sdist('run/bld'))"], artifact)
        clean_spillover(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

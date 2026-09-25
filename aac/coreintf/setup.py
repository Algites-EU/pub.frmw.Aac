from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    """Merge technology-neutral schema sources into the Python wheel resource tree."""

    def run(self):
        super().run()
        artifact = Path(__file__).resolve().parent
        source = artifact / "src/product/schema/algites/frmw/aac/coreintf"
        target = Path(self.build_lib) / "algites/frmw/aac/coreintf"
        if source.is_dir():
            for path in source.rglob("*.json"):
                relative = path.relative_to(source)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)


setup(cmdclass={"build_py": build_py})

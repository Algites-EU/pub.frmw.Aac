from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    """Merge technology-neutral AAC source roots into the Python wheel resource tree."""

    def run(self):
        super().run()
        artifact = Path(__file__).resolve().parent
        source = artifact / 'src/product/config/eu/algites/frmw/aac/dataentity/yamlfsdes'
        target = Path(self.build_lib) / 'eu/algites/frmw/aac/dataentity/yamlfsdes'
        if source.is_dir():
            for path in source.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(source)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        source = artifact / 'src/product/jsondefs/eu/algites/frmw/aac/dataentity/yamlfsdes'
        target = Path(self.build_lib) / 'eu/algites/frmw/aac/dataentity/yamlfsdes'
        if source.is_dir():
            for path in source.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(source)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)


setup(cmdclass={"build_py": build_py})

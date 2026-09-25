from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PYTHON_SOURCE_KIND = "python"
NEUTRAL_RESOURCE_SOURCE_KINDS = ("jsondefs", "yamldefs", "xmldefs", "config")
PYTHON_PACKAGE_SOURCE_KINDS = (PYTHON_SOURCE_KIND, *NEUTRAL_RESOURCE_SOURCE_KINDS)
GENERATION_SUFFIXES = ("", ".gen", ".extgen")
FORBIDDEN_PYTHON_RESOURCE_SUFFIXES = {
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".xsd",
    ".wsdl",
    ".properties",
    ".ini",
    ".cfg",
    ".conf",
}


def source_kind_base(directory_name: str) -> str:
    return directory_name.split(".", 1)[0]


def is_repository_build_path(path: Path, repository: Path) -> bool:
    try:
        relative = path.relative_to(repository)
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] == "build"


def iter_source_roots(
    artifact: Path,
    scope: str,
    source_kinds: Iterable[str] = PYTHON_PACKAGE_SOURCE_KINDS,
) -> tuple[Path, ...]:
    source_directory = artifact / "src" / scope
    if not source_directory.is_dir():
        return ()
    allowed = set(source_kinds)
    roots = [
        path
        for path in source_directory.iterdir()
        if path.is_dir()
        and source_kind_base(path.name) in allowed
        and any(path.name == source_kind_base(path.name) + suffix for suffix in GENERATION_SUFFIXES)
    ]
    return tuple(sorted(roots, key=lambda path: path.name))


def iter_python_artifacts(repository: Path) -> tuple[Path, ...]:
    artifacts: list[Path] = []
    for descriptor in sorted(repository.rglob("algites-artifact.yml")):
        if is_repository_build_path(descriptor, repository):
            continue
        artifact = descriptor.parent
        text = descriptor.read_text(encoding="utf-8")
        if re.search(r"(?is)\btechnologyKinds\b\s*:\s*(?:\[[^\]]*\bpython\b[^\]]*\]|(?:\n\s+-\s*python\b))", text):
            artifacts.append(artifact)
    return tuple(artifacts)


def _iter_files(source_root: Path):
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        yield path


def merge_source_root(source_root: Path, target_root: Path) -> None:
    for source_file in _iter_files(source_root):
        relative = source_file.relative_to(source_root)
        target_file = target_root / relative
        if target_file.exists():
            raise RuntimeError(
                f"Python package staging collision for {relative.as_posix()!r}: "
                f"{source_file} would overwrite {target_file}"
            )
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)


def stage_python_product_tree(artifact: Path, target_root: Path) -> Path:
    shutil.rmtree(target_root, ignore_errors=True)
    target_root.mkdir(parents=True, exist_ok=True)
    for source_root in iter_source_roots(artifact, "product"):
        merge_source_root(source_root, target_root)
    return target_root


def merge_neutral_product_roots_into_python_tree(artifact: Path, python_tree: Path) -> None:
    for source_root in iter_source_roots(artifact, "product", NEUTRAL_RESOURCE_SOURCE_KINDS):
        merge_source_root(source_root, python_tree)


def validate_repository_source_layout(repository: Path) -> list[str]:
    problems: list[str] = []

    for scope in ("product", "develop"):
        for schema_root in sorted(repository.rglob(f"src/{scope}/schema")):
            if is_repository_build_path(schema_root, repository):
                continue
            if schema_root.is_dir():
                problems.append(
                    f"{schema_root.relative_to(repository).as_posix()}: source kind 'schema' is not allowed; "
                    "use jsondefs, yamldefs, xmldefs, or config according to semantic role"
                )

        for python_root in sorted(repository.rglob(f"src/{scope}/python*")):
            if is_repository_build_path(python_root, repository):
                continue
            if not python_root.is_dir() or source_kind_base(python_root.name) != "python":
                continue
            for path in _iter_files(python_root):
                if path.suffix.lower() in FORBIDDEN_PYTHON_RESOURCE_SUFFIXES:
                    problems.append(
                        f"{path.relative_to(repository).as_posix()}: non-Python definition/configuration resource "
                        "must be moved to jsondefs, yamldefs, xmldefs, or config"
                    )

    return problems


def validate_python_distribution_paths(repository: Path) -> list[str]:
    problems: list[str] = []
    path_owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
    artifact_files: dict[str, set[str]] = defaultdict(set)

    for artifact in iter_python_artifacts(repository):
        artifact_name = artifact.relative_to(repository).as_posix()
        local_owners: dict[str, list[str]] = defaultdict(list)
        for source_root in iter_source_roots(artifact, "product"):
            for path in _iter_files(source_root):
                relative = path.relative_to(source_root).as_posix()
                local_owners[relative].append(source_root.name)
                path_owners[relative].append((artifact_name, source_root.name))
                artifact_files[artifact_name].add(relative)
        for relative, roots in sorted(local_owners.items()):
            if len(roots) > 1:
                problems.append(
                    f"{artifact_name}: target Python module/resource path {relative!r} is provided by multiple "
                    f"product source roots: {', '.join(sorted(roots))}"
                )

    for relative, owners in sorted(path_owners.items()):
        artifacts = sorted({artifact for artifact, _ in owners})
        if len(artifacts) > 1:
            rendered = ", ".join(
                f"{artifact} ({source_root})" for artifact, source_root in sorted(owners)
            )
            problems.append(
                f"Python distribution path collision for {relative!r}: {rendered}"
            )

    for artifact, files in sorted(artifact_files.items()):
        for relative in sorted(path for path in files if path.endswith("/__init__.py")):
            package_directory = relative[: -len("/__init__.py")]
            prefix = package_directory + "/"
            other_artifacts = sorted(
                other_artifact
                for other_artifact, other_files in artifact_files.items()
                if other_artifact != artifact and any(path.startswith(prefix) for path in other_files)
            )
            if other_artifacts:
                problems.append(
                    f"{artifact}: {relative!r} turns shared package {package_directory.replace('/', '.')!r} "
                    f"into a regular package although it is also populated by {', '.join(other_artifacts)}; "
                    "shared cross-distribution package prefixes must remain PEP 420 namespace packages"
                )

    return problems

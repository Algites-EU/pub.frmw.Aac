from __future__ import annotations
from pathlib import Path
import yaml

from aic_version_context import AIcVersionContext


def _context_from_mapping(raw: object) -> AIcVersionContext | None:
    if not isinstance(raw, dict):
        return None
    version = raw.get("Version")
    if not isinstance(version, dict):
        return None
    return AIcVersionContext(
        str(version.get("ReleaseLine", "")),
        int(version.get("Revision", 0)),
        str(version.get("QualifierKind", "release")),
        "",
    )


def _load_context(path: Path) -> AIcVersionContext | None:
    if not path.is_file():
        return None
    return _context_from_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))


def repository_context(root: Path) -> AIcVersionContext:
    ctx = _load_context(root / "algites-source-repository.yml")
    if ctx is None:
        raise ValueError("root algites-source-repository.yml has no Version")
    return ctx


def artifact_context(root: Path, artifact: Path) -> AIcVersionContext:
    return _load_context(artifact / "algites-artifact.yml") or repository_context(root)

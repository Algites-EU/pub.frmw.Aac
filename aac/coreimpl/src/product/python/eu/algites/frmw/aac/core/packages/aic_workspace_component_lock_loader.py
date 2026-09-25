from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.packages.api import (
    AInPackageUpdatePolicy,
    AIcPackageAutomationPolicy,
    AIcPackageBootstrap,
    AIcPackageSidecar,
    AIcPackageSourceRegistration,
    AIcPackageStoreLayout,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentLockEntry,
    AIcWorkspaceComponentRequirement,
    AIcWorkspaceComponentRequirements,
)
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text

def _load_yaml(text: str, schema_name: str, source: str) -> Mapping[str, Any]:
    raw = yaml.safe_load(text)
    if not isinstance(raw, Mapping):
        raise ValueError(f"{source}: document root must be a mapping")
    schema = json.loads(read_core_schema(schema_name))
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = []
        for error in errors:
            path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
            rendered.append(f"{path}: {error.message}")
        raise ValueError(f"{source}: schema validation failed: " + "; ".join(rendered))
    return raw

class AIcWorkspaceComponentLockLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcWorkspaceComponentLock:
        raw = _load_yaml(text, "workspace-component-lock_1.json", source)["workspace_component_lock"]
        return AIcWorkspaceComponentLock(
            workspace_id=str(raw["workspace_id"]),
            entries=tuple(
                AIcWorkspaceComponentLockEntry(
                    component_id=str(item["component_id"]), component_version=int(item["component_version"]),
                    sha256=str(item["sha256"]), source_id=str(item["source_id"]), artifact_uri=str(item["artifact_uri"]),
                    artifact_filename=str(item["artifact_filename"]), package_format=str(item["package_format"]),
                    descriptor_path=str(item["descriptor_path"]), runtime_package=str(item["runtime_package"]) if item.get("runtime_package") is not None else None,
                    verifier_id=str(item["verifier_id"]) if item.get("verifier_id") is not None else None,
                    sidecars=tuple(AIcPackageSidecar(str(sc["uri"]), str(sc["suffix"])) for sc in item.get("sidecars", ())),
                )
                for item in raw.get("entries", ())
            ),
        )

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

class AIcWorkspaceComponentRequirementsLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcWorkspaceComponentRequirements:
        raw = _load_yaml(text, "workspace-component-requirements_1.json", source)["workspace_component_requirements"]
        return AIcWorkspaceComponentRequirements(
            workspace_id=str(raw["workspace_id"]),
            update_policy=AInPackageUpdatePolicy(str(raw.get("update_policy", "MANUAL"))),
            requirements=tuple(
                AIcWorkspaceComponentRequirement(
                    component_id=str(item["component_id"]), versions=tuple(int(v) for v in item.get("versions", ())),
                    required=bool(item.get("required", True)), source_ids=tuple(str(v) for v in item.get("source_ids", ())),
                    name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                )
                for item in raw.get("requirements", ())
            ),
        )

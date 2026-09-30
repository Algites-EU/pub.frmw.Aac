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
        raw = _load_yaml(text, "workspace-component-lock_1.jsondef.schema.json", source)["WorkspaceComponentLock"]
        return AIcWorkspaceComponentLock(
            workspace_id=str(raw["WorkspaceId"]),
            entries=tuple(
                AIcWorkspaceComponentLockEntry(
                    component_id=str(item["ComponentId"]), component_version=int(item["ComponentVersion"]),
                    sha256=str(item["Sha256"]), source_id=str(item["SourceId"]), artifact_uri=str(item["ArtifactUri"]),
                    artifact_filename=str(item["ArtifactFilename"]), package_format=str(item["PackageFormat"]),
                    descriptor_path=str(item["DescriptorPath"]), runtime_package=str(item["RuntimePackage"]) if item.get("RuntimePackage") is not None else None,
                    verifier_id=str(item["VerifierId"]) if item.get("VerifierId") is not None else None,
                    sidecars=tuple(AIcPackageSidecar(str(sc["Uri"]), str(sc["Suffix"])) for sc in item.get("Sidecars", ())),
                )
                for item in raw.get("Entries", ())
            ),
        )

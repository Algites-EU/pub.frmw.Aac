from __future__ import annotations

from eu.algites.frmw.aac.core.packages.aiig_workspace_component_lock_1 import AIigWorkspaceComponentLock_1
from eu.algites.frmw.aac.core.packages.aiig_workspace_component_lock_workspace_component_lock_1 import AIigWorkspaceComponentLockWorkspaceComponentLock_1
from eu.algites.frmw.aac.core.packages.aiig_workspace_component_lock_workspace_component_lock_entries_items_1 import AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1
from eu.algites.frmw.aac.core.packages.aiig_workspace_component_lock_workspace_component_lock_entries_items_sidecars_items_1 import AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItemsSidecarsItems_1
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
        raw = _load_yaml(text, "workspace-component-lock_1.jsondef.schema.json", source)[AIigWorkspaceComponentLock_1.SCHEMA_FIELD_NAME__WORKSPACE_COMPONENT_LOCK]
        return AIcWorkspaceComponentLock(
            workspace_id=str(raw[AIigWorkspaceComponentLockWorkspaceComponentLock_1.SCHEMA_FIELD_NAME__WORKSPACE_ID]),
            entries=tuple(
                AIcWorkspaceComponentLockEntry(
                    component_id=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__COMPONENT_ID]), component_version=int(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__COMPONENT_VERSION]),
                    sha256=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__SHA256]), source_id=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__SOURCE_ID]), artifact_uri=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__ARTIFACT_URI]),
                    artifact_filename=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__ARTIFACT_FILENAME]), package_format=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__PACKAGE_FORMAT]),
                    descriptor_path=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__DESCRIPTOR_PATH]), runtime_package=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__RUNTIME_PACKAGE]) if item.get(AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__RUNTIME_PACKAGE) is not None else None,
                    verifier_id=str(item[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__VERIFIER_ID]) if item.get(AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__VERIFIER_ID) is not None else None,
                    sidecars=tuple(AIcPackageSidecar(str(sc[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItemsSidecarsItems_1.SCHEMA_FIELD_NAME__URI]), str(sc[AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItemsSidecarsItems_1.SCHEMA_FIELD_NAME__SUFFIX])) for sc in item.get(AIigWorkspaceComponentLockWorkspaceComponentLockEntriesItems_1.SCHEMA_FIELD_NAME__SIDECARS, ())),
                )
                for item in raw.get(AIigWorkspaceComponentLockWorkspaceComponentLock_1.SCHEMA_FIELD_NAME__ENTRIES, ())
            ),
        )

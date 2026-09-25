from __future__ import annotations

from .schema_resources import read_core_schema

import json
from importlib import resources
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from algites.frmw.aac.coreintf.packages import (
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
from algites.frmw.aac.coreintf.presentation import normalize_display_text


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


class AIcPackageBootstrapLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcPackageBootstrap:
        initial = yaml.safe_load(text)
        if not isinstance(initial, Mapping) or not isinstance(initial.get("package_bootstrap"), Mapping):
            raise ValueError(f"{source}: package bootstrap document root is invalid")
        schema_version = int(initial["package_bootstrap"].get("schema_version", 0))
        if schema_version != 1:
            raise ValueError(f"{source}: unsupported package bootstrap schema_version {schema_version}; expected 1")
        raw = _load_yaml(text, "package-bootstrap_1.json", source)
        root = raw["package_bootstrap"]
        layout_raw = root["layout"]
        policy_raw = root.get("automation_policy", {})
        return AIcPackageBootstrap(
            schema_version=int(root["schema_version"]),
            layout=AIcPackageStoreLayout(
                product_root=str(layout_raw["product_root"]),
                package_store_subdirectory=str(layout_raw.get("package_store_subdirectory", "plugins")),
                downloaded_subdirectory=str(layout_raw.get("downloaded_subdirectory", "downloaded")),
                installed_subdirectory=str(layout_raw.get("installed_subdirectory", "installed")),
                obsolete_subdirectory=str(layout_raw.get("obsolete_subdirectory", "obsolete")),
                core_state_subdirectory=str(layout_raw.get("core_state_subdirectory", "aac-state")),
                transactions_subdirectory=str(layout_raw.get("transactions_subdirectory", "transactions")),
                core_lock_filename=str(layout_raw.get("core_lock_filename", "core.lock")),
            ),
            sources=tuple(
                AIcPackageSourceRegistration(
                    id=str(item["id"]), type=str(item.get("type", "MANIFEST")), uri=str(item["uri"]),
                    authentication_profile_id=str(item["authentication_profile_id"]) if item.get("authentication_profile_id") is not None else None,
                    verifier_id=str(item["verifier_id"]) if item.get("verifier_id") is not None else None,
                    priority=int(item.get("priority", 0)), settings=dict(item.get("settings", {})),
                    name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                )
                for item in root.get("sources", ())
            ),
            automation_policy=AIcPackageAutomationPolicy(
                verify_on_download=bool(policy_raw.get("verify_on_download", True)),
                require_entitlement_for_automatic_paid_component=bool(policy_raw.get("require_entitlement_for_automatic_paid_component", True)),
                allow_automatic_download=bool(policy_raw.get("allow_automatic_download", True)),
                allow_automatic_install=bool(policy_raw.get("allow_automatic_install", True)),
            ),
            metadata=dict(root.get("metadata", {})),
        )


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

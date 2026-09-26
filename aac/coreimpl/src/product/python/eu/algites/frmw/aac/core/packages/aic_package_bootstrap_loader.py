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

class AIcPackageBootstrapLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcPackageBootstrap:
        initial = yaml.safe_load(text)
        if not isinstance(initial, Mapping) or not isinstance(initial.get("PackageBootstrap"), Mapping):
            raise ValueError(f"{source}: package bootstrap document root is invalid")
        schema_version = int(initial["PackageBootstrap"].get("SchemaVersion", 0))
        if schema_version != 1:
            raise ValueError(f"{source}: unsupported package bootstrap schema_version {schema_version}; expected 1")
        raw = _load_yaml(text, "package-bootstrap_1.json", source)
        root = raw["PackageBootstrap"]
        layout_raw = root["Layout"]
        policy_raw = root.get("AutomationPolicy", {})
        return AIcPackageBootstrap(
            schema_version=int(root["SchemaVersion"]),
            layout=AIcPackageStoreLayout(
                product_root=str(layout_raw["ProductRoot"]),
                package_store_subdirectory=str(layout_raw.get("PackageStoreSubdirectory", "plugins")),
                downloaded_subdirectory=str(layout_raw.get("DownloadedSubdirectory", "downloaded")),
                installed_subdirectory=str(layout_raw.get("InstalledSubdirectory", "installed")),
                obsolete_subdirectory=str(layout_raw.get("ObsoleteSubdirectory", "obsolete")),
                core_state_subdirectory=str(layout_raw.get("CoreStateSubdirectory", "aac-state")),
                transactions_subdirectory=str(layout_raw.get("TransactionsSubdirectory", "transactions")),
                core_lock_filename=str(layout_raw.get("CoreLockFilename", "core.lock")),
            ),
            sources=tuple(
                AIcPackageSourceRegistration(
                    id=str(item["Id"]), type=str(item.get("Type", "MANIFEST")), uri=str(item["Uri"]),
                    authentication_profile_id=str(item["AuthenticationProfileId"]) if item.get("AuthenticationProfileId") is not None else None,
                    verifier_id=str(item["VerifierId"]) if item.get("VerifierId") is not None else None,
                    priority=int(item.get("Priority", 0)), settings=dict(item.get("Settings", {})),
                    name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")),
                )
                for item in root.get("Sources", ())
            ),
            automation_policy=AIcPackageAutomationPolicy(
                verify_on_download=bool(policy_raw.get("VerifyOnDownload", True)),
                require_entitlement_for_automatic_paid_component=bool(policy_raw.get("RequireEntitlementForAutomaticPaidComponent", True)),
                allow_automatic_download=bool(policy_raw.get("AllowAutomaticDownload", True)),
                allow_automatic_install=bool(policy_raw.get("AllowAutomaticInstall", True)),
            ),
            metadata=dict(root.get("Metadata", {})),
        )

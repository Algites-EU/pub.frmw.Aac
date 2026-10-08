from __future__ import annotations

from eu.algites.frmw.aac.core.packages.aiig_package_bootstrap_1 import AIigPackageBootstrap_1
from eu.algites.frmw.aac.core.packages.aiig_package_bootstrap_package_bootstrap_1 import AIigPackageBootstrapPackageBootstrap_1
from eu.algites.frmw.aac.core.packages.aiig_package_bootstrap_package_bootstrap_automation_policy_1 import AIigPackageBootstrapPackageBootstrapAutomationPolicy_1
from eu.algites.frmw.aac.core.packages.aiig_package_bootstrap_package_bootstrap_layout_1 import AIigPackageBootstrapPackageBootstrapLayout_1
from eu.algites.frmw.aac.core.packages.aiig_package_bootstrap_package_bootstrap_sources_items_1 import AIigPackageBootstrapPackageBootstrapSourcesItems_1
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
        if not isinstance(initial, Mapping) or not isinstance(initial.get(AIigPackageBootstrap_1.SCHEMA_FIELD_NAME__PACKAGE_BOOTSTRAP), Mapping):
            raise ValueError(f"{source}: package bootstrap document root is invalid")
        schema_version = int(initial[AIigPackageBootstrap_1.SCHEMA_FIELD_NAME__PACKAGE_BOOTSTRAP].get(AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION, 0))
        if schema_version != 1:
            raise ValueError(f"{source}: unsupported package bootstrap schema_version {schema_version}; expected 1")
        raw = _load_yaml(text, "package-bootstrap_1.jsondef.schema.json", source)
        root = raw[AIigPackageBootstrap_1.SCHEMA_FIELD_NAME__PACKAGE_BOOTSTRAP]
        layout_raw = root[AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__LAYOUT]
        policy_raw = root.get(AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__AUTOMATION_POLICY, {})
        return AIcPackageBootstrap(
            schema_version=int(root[AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]),
            layout=AIcPackageStoreLayout(
                product_root=str(layout_raw[AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__PRODUCT_ROOT]),
                package_store_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__PACKAGE_STORE_SUBDIRECTORY, "plugins")),
                downloaded_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__DOWNLOADED_SUBDIRECTORY, "downloaded")),
                installed_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__INSTALLED_SUBDIRECTORY, "installed")),
                obsolete_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__OBSOLETE_SUBDIRECTORY, "obsolete")),
                core_state_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__CORE_STATE_SUBDIRECTORY, "aac-state")),
                transactions_subdirectory=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__TRANSACTIONS_SUBDIRECTORY, "transactions")),
                core_lock_filename=str(layout_raw.get(AIigPackageBootstrapPackageBootstrapLayout_1.SCHEMA_FIELD_NAME__CORE_LOCK_FILENAME, "core.lock")),
            ),
            sources=tuple(
                AIcPackageSourceRegistration(
                    id=str(item[AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__ID]), type=str(item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__TYPE, "MANIFEST")), uri=str(item[AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__URI]),
                    authentication_profile_id=str(item[AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID]) if item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID) is not None else None,
                    verifier_id=str(item[AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__VERIFIER_ID]) if item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__VERIFIER_ID) is not None else None,
                    priority=int(item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__PRIORITY, 0)), settings=dict(item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})),
                    name=normalize_display_text(item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigPackageBootstrapPackageBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                )
                for item in root.get(AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__SOURCES, ())
            ),
            automation_policy=AIcPackageAutomationPolicy(
                verify_on_download=bool(policy_raw.get(AIigPackageBootstrapPackageBootstrapAutomationPolicy_1.SCHEMA_FIELD_NAME__VERIFY_ON_DOWNLOAD, True)),
                require_entitlement_for_automatic_paid_component=bool(policy_raw.get(AIigPackageBootstrapPackageBootstrapAutomationPolicy_1.SCHEMA_FIELD_NAME__REQUIRE_ENTITLEMENT_FOR_AUTOMATIC_PAID_COMPONENT, True)),
                allow_automatic_download=bool(policy_raw.get(AIigPackageBootstrapPackageBootstrapAutomationPolicy_1.SCHEMA_FIELD_NAME__ALLOW_AUTOMATIC_DOWNLOAD, True)),
                allow_automatic_install=bool(policy_raw.get(AIigPackageBootstrapPackageBootstrapAutomationPolicy_1.SCHEMA_FIELD_NAME__ALLOW_AUTOMATIC_INSTALL, True)),
            ),
            metadata=dict(root.get(AIigPackageBootstrapPackageBootstrap_1.SCHEMA_FIELD_NAME__METADATA, {})),
        )

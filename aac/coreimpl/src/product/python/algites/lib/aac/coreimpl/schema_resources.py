from __future__ import annotations

from importlib import resources
from pathlib import Path

_SCHEMA_AREAS = {
    "catalog_1.json": "catalog",
    "catalog-bootstrap_1.json": "catalog",
    "component-descriptor_1.json": "descriptor",
    "capability-contract_1.json": "contracts",
    "configuration-persisted-payload_1.json": "configuration",
    "configuration-profile_1.json": "configuration",
    "configuration-provider-document_1.json": "configuration",
    "configuration-bootstrap_1.json": "configuration",
    "entitlement-bootstrap_1.json": "entitlement",
    "entitlement-document_1.json": "entitlement",
    "entitlement-issuing-request_1.json": "entitlement",
    "package-bootstrap_1.json": "packages",
    "active-package-set_1.json": "packages",
    "package-source-manifest_1.json": "packages",
    "workspace-component-lock_1.json": "packages",
    "workspace-component-requirements_1.json": "packages",
    "observation-operation-input_1.json": "observation",
    "observation-output_1.json": "observation",
    "observation-input_1.json": "observation",
    "data-entity-envelope_1.json": "dataentity",
    "provider-instance_1.json": "instances",
    "security-bootstrap_1.json": "authentication",
    "core-state-store_1.json": "persistence",
    "transaction-plan_1.json": "persistence",
    "transaction-state_1.json": "persistence",
}


def schema_relative_path(resource_name: str) -> str:
    area = _SCHEMA_AREAS.get(Path(resource_name).name, "common")
    return f"{area}/{Path(resource_name).name}"


def read_core_schema(resource_name: str) -> str:
    relative = schema_relative_path(resource_name)
    try:
        return resources.files("algites.lib.aac.coreintf").joinpath(relative).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        here = Path(__file__).resolve()
        for parent in here.parents:
            source = parent / "aac/coreintf/src/product/schema/algites/lib/aac/coreintf" / relative
            if source.is_file():
                return source.read_text(encoding="utf-8")
        raise FileNotFoundError(f"cannot locate AAC Core schema {resource_name!r} ({relative})")

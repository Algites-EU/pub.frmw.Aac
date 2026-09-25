from __future__ import annotations

from importlib import resources
from pathlib import Path

_SCHEMA_AREAS = {
    "catalog_1.json": "catalog",
    "catalog-bootstrap_1.json": "catalog",
    "component-descriptor_1.json": "descriptor",
    "capability-contract_1.json": "capability",
    "capability-group_1.json": "capability",
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
    "observation-output_1.json": "observation",
    "observation-input_1.json": "observation",
    "data-entity-envelope_1.json": "dataentity",
    "data-entity-get-record-request_1.json": "dataentity",
    "data-entity-get-record-result_1.json": "dataentity",
    "data-entity-query-records-request_1.json": "dataentity",
    "data-entity-query-records-result_1.json": "dataentity",
    "data-entity-apply-direct-record-changes-request_1.json": "dataentity",
    "data-entity-apply-direct-record-changes-result_1.json": "dataentity",
    "data-entity-apply-direct-record-changes-running-delta-result_1.json": "dataentity",
    "data-entity-apply-direct-record-changes-running-complete-result_1.json": "dataentity",
    "data-entity-query-records-running-delta-result_1.json": "dataentity",
    "data-entity-query-records-running-complete-result_1.json": "dataentity",
    "data-entity-inspect-storage-support-request_1.json": "dataentity",
    "data-entity-inspect-storage-support-result_1.json": "dataentity",
    "data-entity-ensure-storage-support-request_1.json": "dataentity",
    "data-entity-ensure-storage-support-result_1.json": "dataentity",
    "data-entity-retire-storage-support-request_1.json": "dataentity",
    "data-entity-retire-storage-support-result_1.json": "dataentity",
    "data-entity-create-storage-backup-request_1.json": "dataentity",
    "data-entity-create-storage-backup-result_1.json": "dataentity",
    "data-entity-inspect-storage-backup-request_1.json": "dataentity",
    "data-entity-inspect-storage-backup-result_1.json": "dataentity",
    "data-entity-restore-storage-backup-request_1.json": "dataentity",
    "data-entity-restore-storage-backup-result_1.json": "dataentity",
    "provider-instance_1.json": "instances",
    "security-bootstrap_1.json": "authentication",
    "core-state-store_1.json": "persistence",
    "transaction-plan_1.json": "persistence",
    "transaction-state_1.json": "persistence",
    "operation-interaction-event_1.json": "invocation",
    "operation-interaction-provider-to-caller-message_1.json": "invocation",
    "operation-interaction-caller-to-provider-message_1.json": "invocation",
    "operation-failure_1.json": "invocation",
    "display-content_1.json": "presentation",
}


def schema_relative_path(resource_name: str) -> str:
    area = _SCHEMA_AREAS.get(Path(resource_name).name, "common")
    return f"{area}/{Path(resource_name).name}"


def read_core_schema(resource_name: str) -> str:
    relative = schema_relative_path(resource_name)
    try:
        return resources.files("eu.algites.frmw.aac.core").joinpath(relative).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        here = Path(__file__).resolve()
        for parent in here.parents:
            source = parent / "aac/coreintf/src/product/jsondefs/eu/algites/frmw/aac/core" / relative
            if source.is_file():
                return source.read_text(encoding="utf-8")
        raise FileNotFoundError(f"cannot locate AAC Core schema {resource_name!r} ({relative})")

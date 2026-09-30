from __future__ import annotations

from importlib import resources
from pathlib import Path

_SCHEMA_AREAS = {
    "catalog_1.jsondef.schema.json": "catalog",
    "catalog-bootstrap_1.jsondef.schema.json": "catalog",
    "component-descriptor_1.jsondef.schema.json": "descriptor",
    "capability-contract_1.jsondef.schema.json": "capability",
    "capability-group_1.jsondef.schema.json": "capability",
    "configuration-persisted-payload_1.jsondef.schema.json": "configuration",
    "configuration-profile_1.jsondef.schema.json": "configuration",
    "configuration-provider-document_1.jsondef.schema.json": "configuration",
    "configuration-bootstrap_1.jsondef.schema.json": "configuration",
    "entitlement-bootstrap_1.jsondef.schema.json": "entitlement",
    "entitlement-document_1.jsondef.schema.json": "entitlement",
    "entitlement-issuing-request_1.jsondef.schema.json": "entitlement",
    "package-bootstrap_1.jsondef.schema.json": "packages",
    "active-package-set_1.jsondef.schema.json": "packages",
    "package-source-manifest_1.jsondef.schema.json": "packages",
    "workspace-component-lock_1.jsondef.schema.json": "packages",
    "workspace-component-requirements_1.jsondef.schema.json": "packages",
    "observation-output_1.jsondef.schema.json": "observation",
    "observation-input_1.jsondef.schema.json": "observation",
    "data-entity-envelope_1.jsondef.schema.json": "dataentity",
    "data-entity-get-record-request_1.jsondef.schema.json": "dataentity",
    "data-entity-get-record-result_1.jsondef.schema.json": "dataentity",
    "data-entity-query-records-request_1.jsondef.schema.json": "dataentity",
    "data-entity-query-records-result_1.jsondef.schema.json": "dataentity",
    "data-entity-apply-direct-record-changes-request_1.jsondef.schema.json": "dataentity",
    "data-entity-apply-direct-record-changes-result_1.jsondef.schema.json": "dataentity",
    "data-entity-apply-direct-record-changes-running-delta-result_1.jsondef.schema.json": "dataentity",
    "data-entity-apply-direct-record-changes-running-complete-result_1.jsondef.schema.json": "dataentity",
    "data-entity-query-records-running-delta-result_1.jsondef.schema.json": "dataentity",
    "data-entity-query-records-running-complete-result_1.jsondef.schema.json": "dataentity",
    "data-entity-inspect-storage-support-request_1.jsondef.schema.json": "dataentity",
    "data-entity-inspect-storage-support-result_1.jsondef.schema.json": "dataentity",
    "data-entity-ensure-storage-support-request_1.jsondef.schema.json": "dataentity",
    "data-entity-ensure-storage-support-result_1.jsondef.schema.json": "dataentity",
    "data-entity-retire-storage-support-request_1.jsondef.schema.json": "dataentity",
    "data-entity-retire-storage-support-result_1.jsondef.schema.json": "dataentity",
    "data-entity-create-storage-backup-request_1.jsondef.schema.json": "dataentity",
    "data-entity-create-storage-backup-result_1.jsondef.schema.json": "dataentity",
    "data-entity-inspect-storage-backup-request_1.jsondef.schema.json": "dataentity",
    "data-entity-inspect-storage-backup-result_1.jsondef.schema.json": "dataentity",
    "data-entity-restore-storage-backup-request_1.jsondef.schema.json": "dataentity",
    "data-entity-restore-storage-backup-result_1.jsondef.schema.json": "dataentity",
    "provider-instance_1.jsondef.schema.json": "instances",
    "security-bootstrap_1.jsondef.schema.json": "authentication",
    "core-state-store_1.jsondef.schema.json": "persistence",
    "transaction-plan_1.jsondef.schema.json": "persistence",
    "transaction-state_1.jsondef.schema.json": "persistence",
    "operation-interaction-event_1.jsondef.schema.json": "invocation",
    "operation-interaction-provider-to-caller-message_1.jsondef.schema.json": "invocation",
    "operation-interaction-caller-to-provider-message_1.jsondef.schema.json": "invocation",
    "operation-failure_1.jsondef.schema.json": "invocation",
    "display-content_1.jsondef.schema.json": "presentation",
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

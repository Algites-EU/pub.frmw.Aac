from __future__ import annotations

from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_1 import AIigEntitlementDocument_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_1 import AIigEntitlementDocumentEntitlement_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_components_items_1 import AIigEntitlementDocumentEntitlementComponentsItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_components_items_grants_items_1 import AIigEntitlementDocumentEntitlementComponentsItemsGrantsItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_components_items_grants_items_capability_1 import AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsCapability_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_components_items_grants_items_permissions_items_1 import AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_issued_for_request_1 import AIigEntitlementDocumentEntitlementIssuedForRequest_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_issuer_1 import AIigEntitlementDocumentEntitlementIssuer_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_licensing_scope_1 import AIigEntitlementDocumentEntitlementLicensingScope_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_document_entitlement_subject_1 import AIigEntitlementDocumentEntitlementSubject_1
import json
import hashlib
from datetime import date, datetime
from importlib import resources
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementCapabilityGrant,
    AIcEntitlementLicensingScope,
    AIcEntitlementComponentGrant,
    AIcEntitlementDocument,
    AIcEntitlementIssuer,
    AIcEntitlementIssuingRequest,
    AIcEntitlementPermissionGrant,
    AIcEntitlementSubject,
    AIcEntitlementRequestReference,
    AIcRequestedCapabilityGrant,
    AIcRequestedComponentGrant,
)
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
from eu.algites.frmw.aac.core.implementation.errors import AIxEntitlementError

def _load_yaml(text: str, source: str) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AIxEntitlementError(f"invalid entitlement YAML in {source}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise AIxEntitlementError(f"{source}: entitlement root must be a mapping")
    return _normalize_yaml_scalars(raw)

def _normalize_yaml_scalars(value: Any) -> Any:
    # PyYAML resolves ISO-8601 timestamps to datetime/date objects. The canonical
    # entitlement schemas intentionally model temporal values as strings so the
    # signed representation and cross-language bindings remain technology neutral.
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_scalars(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_yaml_scalars(item) for item in value)
    return value

def _validate(raw: Mapping[str, Any], schema_name: str, source: str) -> None:
    schema = json.loads(read_core_schema(schema_name))
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = []
        for error in errors:
            path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
            rendered.append(f"{path}: {error.message}")
        raise AIxEntitlementError(f"{source}: entitlement schema validation failed: " + "; ".join(rendered))

def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AIxEntitlementError("expected mapping in entitlement document")
    return value

class AIcEntitlementDocumentLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcEntitlementDocument:
        raw = _load_yaml(text, source)
        data = _mapping(raw.get(AIigEntitlementDocument_1.SCHEMA_FIELD_NAME__ENTITLEMENT))
        format_version = int(data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__FORMAT_VERSION, 0))
        if format_version != 1:
            raise AIxEntitlementError(f"{source}: unsupported entitlement document format_version {format_version}; expected 1")
        _validate(raw, "entitlement-document_1.jsondef.schema.json", source)
        scope_data = _mapping(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__LICENSING_SCOPE])
        subject_data = _mapping(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__SUBJECT])
        subject = AIcEntitlementSubject(
            str(subject_data[AIigEntitlementDocumentEntitlementSubject_1.SCHEMA_FIELD_NAME__ID]),
            str(subject_data[AIigEntitlementDocumentEntitlementSubject_1.SCHEMA_FIELD_NAME__DISPLAY_NAME]) if subject_data.get(AIigEntitlementDocumentEntitlementSubject_1.SCHEMA_FIELD_NAME__DISPLAY_NAME) is not None else None,
            dict(_mapping(subject_data.get(AIigEntitlementDocumentEntitlementSubject_1.SCHEMA_FIELD_NAME__ATTRIBUTES, {}))),
        )
        scope = AIcEntitlementLicensingScope(str(scope_data[AIigEntitlementDocumentEntitlementLicensingScope_1.SCHEMA_FIELD_NAME__TYPE]), subject.id)
        issuer_data = _mapping(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ISSUER])
        issuer = AIcEntitlementIssuer(str(issuer_data[AIigEntitlementDocumentEntitlementIssuer_1.SCHEMA_FIELD_NAME__ID]), {str(k): v for k, v in issuer_data.items() if k != "id"})
        components = []
        for component_raw in data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__COMPONENTS, ()):
            component = _mapping(component_raw)
            grants = []
            for grant_raw in component.get(AIigEntitlementDocumentEntitlementComponentsItems_1.SCHEMA_FIELD_NAME__GRANTS, ()):
                grant = _mapping(grant_raw)
                capability = _mapping(grant[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItems_1.SCHEMA_FIELD_NAME__CAPABILITY])
                permissions = tuple(
                    AIcEntitlementPermissionGrant(
                        str(_mapping(item)[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__ID]),
                        str(_mapping(item)[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__VALID_FROM]) if _mapping(item).get(AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__VALID_FROM) is not None else None,
                        str(_mapping(item)[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__VALID_UNTIL]) if _mapping(item).get(AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__VALID_UNTIL) is not None else None,
                        dict(_mapping(_mapping(item).get(AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__CONSTRAINTS, {}))),
                        dict(_mapping(_mapping(item).get(AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsPermissionsItems_1.SCHEMA_FIELD_NAME__METADATA, {}))),
                    )
                    for item in grant.get(AIigEntitlementDocumentEntitlementComponentsItemsGrantsItems_1.SCHEMA_FIELD_NAME__PERMISSIONS, ())
                )
                grants.append(AIcEntitlementCapabilityGrant(str(capability[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsCapability_1.SCHEMA_FIELD_NAME__ID]), int(capability[AIigEntitlementDocumentEntitlementComponentsItemsGrantsItemsCapability_1.SCHEMA_FIELD_NAME__VERSION]), permissions))
            components.append(AIcEntitlementComponentGrant(str(component[AIigEntitlementDocumentEntitlementComponentsItems_1.SCHEMA_FIELD_NAME__ID]), tuple(grants)))
        issued_for_request = None
        if data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ISSUED_FOR_REQUEST) is not None:
            request_ref = _mapping(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ISSUED_FOR_REQUEST])
            issued_for_request = AIcEntitlementRequestReference(
                str(request_ref[AIigEntitlementDocumentEntitlementIssuedForRequest_1.SCHEMA_FIELD_NAME__REQUEST_ID]), str(request_ref[AIigEntitlementDocumentEntitlementIssuedForRequest_1.SCHEMA_FIELD_NAME__REQUEST_DIGEST])
            )
        return AIcEntitlementDocument(
            format_version=int(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__FORMAT_VERSION]), entitlement_id=str(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ENTITLEMENT_ID]),
            issuer=issuer, licensing_scope=scope, subject=subject, components=tuple(components),
            issued_for_request=issued_for_request,
            issued_at=str(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ISSUED_AT]) if data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__ISSUED_AT) is not None else None,
            valid_from=str(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__VALID_FROM]) if data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__VALID_FROM) is not None else None,
            valid_until=str(data[AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__VALID_UNTIL]) if data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__VALID_UNTIL) is not None else None,
            metadata=dict(_mapping(data.get(AIigEntitlementDocumentEntitlement_1.SCHEMA_FIELD_NAME__METADATA, {}))),
        )

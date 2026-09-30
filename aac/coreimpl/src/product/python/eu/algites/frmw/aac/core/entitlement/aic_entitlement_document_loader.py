from __future__ import annotations
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
        data = _mapping(raw.get("Entitlement"))
        format_version = int(data.get("FormatVersion", 0))
        if format_version != 1:
            raise AIxEntitlementError(f"{source}: unsupported entitlement document format_version {format_version}; expected 1")
        _validate(raw, "entitlement-document_1.jsondef.schema.json", source)
        scope_data = _mapping(data["LicensingScope"])
        subject_data = _mapping(data["Subject"])
        subject = AIcEntitlementSubject(
            str(subject_data["Id"]),
            str(subject_data["DisplayName"]) if subject_data.get("DisplayName") is not None else None,
            dict(_mapping(subject_data.get("Attributes", {}))),
        )
        scope = AIcEntitlementLicensingScope(str(scope_data["Type"]), subject.id)
        issuer_data = _mapping(data["Issuer"])
        issuer = AIcEntitlementIssuer(str(issuer_data["Id"]), {str(k): v for k, v in issuer_data.items() if k != "id"})
        components = []
        for component_raw in data.get("Components", ()):
            component = _mapping(component_raw)
            grants = []
            for grant_raw in component.get("Grants", ()):
                grant = _mapping(grant_raw)
                capability = _mapping(grant["Capability"])
                permissions = tuple(
                    AIcEntitlementPermissionGrant(
                        str(_mapping(item)["Id"]),
                        str(_mapping(item)["ValidFrom"]) if _mapping(item).get("ValidFrom") is not None else None,
                        str(_mapping(item)["ValidUntil"]) if _mapping(item).get("ValidUntil") is not None else None,
                        dict(_mapping(_mapping(item).get("Constraints", {}))),
                        dict(_mapping(_mapping(item).get("Metadata", {}))),
                    )
                    for item in grant.get("Permissions", ())
                )
                grants.append(AIcEntitlementCapabilityGrant(str(capability["Id"]), int(capability["Version"]), permissions))
            components.append(AIcEntitlementComponentGrant(str(component["Id"]), tuple(grants)))
        issued_for_request = None
        if data.get("IssuedForRequest") is not None:
            request_ref = _mapping(data["IssuedForRequest"])
            issued_for_request = AIcEntitlementRequestReference(
                str(request_ref["RequestId"]), str(request_ref["RequestDigest"])
            )
        return AIcEntitlementDocument(
            format_version=int(data["FormatVersion"]), entitlement_id=str(data["EntitlementId"]),
            issuer=issuer, licensing_scope=scope, subject=subject, components=tuple(components),
            issued_for_request=issued_for_request,
            issued_at=str(data["IssuedAt"]) if data.get("IssuedAt") is not None else None,
            valid_from=str(data["ValidFrom"]) if data.get("ValidFrom") is not None else None,
            valid_until=str(data["ValidUntil"]) if data.get("ValidUntil") is not None else None,
            metadata=dict(_mapping(data.get("Metadata", {}))),
        )

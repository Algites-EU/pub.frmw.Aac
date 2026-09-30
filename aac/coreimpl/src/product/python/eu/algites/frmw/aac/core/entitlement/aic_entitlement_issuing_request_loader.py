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

class AIcEntitlementIssuingRequestLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcEntitlementIssuingRequest:
        raw = _load_yaml(text, source)
        data = _mapping(raw.get("EntitlementRequest"))
        format_version = int(data.get("FormatVersion", 0))
        if format_version != 1:
            raise AIxEntitlementError(f"{source}: unsupported entitlement issuing request format_version {format_version}; expected 1")
        _validate(raw, "entitlement-issuing-request_1.jsondef.schema.json", source)
        scope_data = _mapping(data["RequestedLicensingScope"])
        subject_data = _mapping(data["Subject"])
        subject = AIcEntitlementSubject(
            str(subject_data["Id"]),
            str(subject_data["DisplayName"]) if subject_data.get("DisplayName") is not None else None,
            dict(_mapping(subject_data.get("Attributes", {}))),
        )
        scope = AIcEntitlementLicensingScope(str(scope_data["Type"]), subject.id)
        components = []
        for component_raw in data.get("Components", ()):
            component = _mapping(component_raw)
            requested = []
            for grant_raw in component.get("RequestedGrants", ()):
                grant = _mapping(grant_raw)
                capability = _mapping(grant["Capability"])
                requested.append(AIcRequestedCapabilityGrant(
                    str(capability["Id"]), int(capability["Version"]),
                    tuple(str(v) for v in grant.get("Permissions", ())),
                ))
            components.append(AIcRequestedComponentGrant(str(component["Id"]), tuple(requested)))
        return AIcEntitlementIssuingRequest(
            format_version=int(data["FormatVersion"]), request_id=str(data["RequestId"]),
            requested_licensing_scope=scope, subject=subject, components=tuple(components),
            generated_at=str(data["GeneratedAt"]) if data.get("GeneratedAt") is not None else None,
            request_digest=str(data["RequestDigest"]) if data.get("RequestDigest") is not None else None,
            metadata=dict(_mapping(data.get("Metadata", {}))),
        )

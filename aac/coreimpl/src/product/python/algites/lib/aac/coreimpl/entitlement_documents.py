from __future__ import annotations

import json
import hashlib
from datetime import date, datetime
from importlib import resources
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from algites.lib.aac.coreintf.entitlement import (
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
from .schema_resources import read_core_schema
from .errors import AIxEntitlementError


class AIcEntitlementDocumentLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcEntitlementDocument:
        raw = _load_yaml(text, source)
        data = _mapping(raw.get("entitlement"))
        format_version = int(data.get("format_version", 0))
        if format_version != 1:
            raise AIxEntitlementError(f"{source}: unsupported entitlement document format_version {format_version}; expected 1")
        _validate(raw, "entitlement-document_1.json", source)
        scope_data = _mapping(data["licensing_scope"])
        subject_data = _mapping(data["subject"])
        subject = AIcEntitlementSubject(
            str(subject_data["id"]),
            str(subject_data["display_name"]) if subject_data.get("display_name") is not None else None,
            dict(_mapping(subject_data.get("attributes", {}))),
        )
        scope = AIcEntitlementLicensingScope(str(scope_data["type"]), subject.id)
        issuer_data = _mapping(data["issuer"])
        issuer = AIcEntitlementIssuer(str(issuer_data["id"]), {str(k): v for k, v in issuer_data.items() if k != "id"})
        components = []
        for component_raw in data.get("components", ()):
            component = _mapping(component_raw)
            grants = []
            for grant_raw in component.get("grants", ()):
                grant = _mapping(grant_raw)
                capability = _mapping(grant["capability"])
                permissions = tuple(
                    AIcEntitlementPermissionGrant(
                        str(_mapping(item)["id"]),
                        str(_mapping(item)["valid_from"]) if _mapping(item).get("valid_from") is not None else None,
                        str(_mapping(item)["valid_until"]) if _mapping(item).get("valid_until") is not None else None,
                        dict(_mapping(_mapping(item).get("constraints", {}))),
                        dict(_mapping(_mapping(item).get("metadata", {}))),
                    )
                    for item in grant.get("permissions", ())
                )
                grants.append(AIcEntitlementCapabilityGrant(str(capability["id"]), int(capability["version"]), permissions))
            components.append(AIcEntitlementComponentGrant(str(component["id"]), tuple(grants)))
        issued_for_request = None
        if data.get("issued_for_request") is not None:
            request_ref = _mapping(data["issued_for_request"])
            issued_for_request = AIcEntitlementRequestReference(
                str(request_ref["request_id"]), str(request_ref["request_digest"])
            )
        return AIcEntitlementDocument(
            format_version=int(data["format_version"]), entitlement_id=str(data["entitlement_id"]),
            issuer=issuer, licensing_scope=scope, subject=subject, components=tuple(components),
            issued_for_request=issued_for_request,
            issued_at=str(data["issued_at"]) if data.get("issued_at") is not None else None,
            valid_from=str(data["valid_from"]) if data.get("valid_from") is not None else None,
            valid_until=str(data["valid_until"]) if data.get("valid_until") is not None else None,
            metadata=dict(_mapping(data.get("metadata", {}))),
        )


class AIcEntitlementIssuingRequestLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcEntitlementIssuingRequest:
        raw = _load_yaml(text, source)
        data = _mapping(raw.get("entitlement_request"))
        format_version = int(data.get("format_version", 0))
        if format_version != 1:
            raise AIxEntitlementError(f"{source}: unsupported entitlement issuing request format_version {format_version}; expected 1")
        _validate(raw, "entitlement-issuing-request_1.json", source)
        scope_data = _mapping(data["requested_licensing_scope"])
        subject_data = _mapping(data["subject"])
        subject = AIcEntitlementSubject(
            str(subject_data["id"]),
            str(subject_data["display_name"]) if subject_data.get("display_name") is not None else None,
            dict(_mapping(subject_data.get("attributes", {}))),
        )
        scope = AIcEntitlementLicensingScope(str(scope_data["type"]), subject.id)
        components = []
        for component_raw in data.get("components", ()):
            component = _mapping(component_raw)
            requested = []
            for grant_raw in component.get("requested_grants", ()):
                grant = _mapping(grant_raw)
                capability = _mapping(grant["capability"])
                requested.append(AIcRequestedCapabilityGrant(
                    str(capability["id"]), int(capability["version"]),
                    tuple(str(v) for v in grant.get("permissions", ())),
                ))
            components.append(AIcRequestedComponentGrant(str(component["id"]), tuple(requested)))
        return AIcEntitlementIssuingRequest(
            format_version=int(data["format_version"]), request_id=str(data["request_id"]),
            requested_licensing_scope=scope, subject=subject, components=tuple(components),
            generated_at=str(data["generated_at"]) if data.get("generated_at") is not None else None,
            request_digest=str(data["request_digest"]) if data.get("request_digest") is not None else None,
            metadata=dict(_mapping(data.get("metadata", {}))),
        )


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


def entitlement_request_digest(request: AIcEntitlementIssuingRequest) -> str:
    """Return a stable SHA-256 digest of the technology-neutral request content.

    The embedded request_digest field is excluded from the digest itself.
    """
    from dataclasses import asdict
    payload = asdict(request)
    payload.pop("request_digest", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()

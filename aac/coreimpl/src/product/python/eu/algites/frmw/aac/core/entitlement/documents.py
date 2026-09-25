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

from .aic_entitlement_document_loader import AIcEntitlementDocumentLoader
from .aic_entitlement_issuing_request_loader import AIcEntitlementIssuingRequestLoader

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

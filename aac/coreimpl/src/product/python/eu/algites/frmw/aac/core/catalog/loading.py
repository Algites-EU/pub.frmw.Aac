from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.authentication.api import AIcAuthenticationMaterial
from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogArtifact,
    AIcCatalogArtifactLocator,
    AIcCatalogCapabilityOffer,
    AIcCatalogCapabilityRequirement,
    AIcCatalogComponent,
    AIcCatalogDocument,
    AIcCatalogEntry,
    AIcCatalogIcon,
    AIcCatalogPublisher,
    AIcCatalogQuery,
    AIcCatalogRelease,
    AIcCatalogPersistentSchema,
    AInCatalogPersistentSchemaKind,
    AIiCatalogProvider,
)
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxPackageManagementError
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.packages.api import AIcPackageSidecar
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService

from .aic_catalog_document_loader import AIcCatalogDocumentLoader
from .aic_static_catalog_provider import AIcStaticCatalogProvider
from .aic_document_catalog_provider import AIcDocumentCatalogProvider
from .aic_filesystem_catalog_provider import AIcFilesystemCatalogProvider
from .aic_http_catalog_provider import AIcHttpCatalogProvider
from .aic_catalog_provider_registry import AIcCatalogProviderRegistry

def _ssl_context(material: AIcAuthenticationMaterial):
    certificate = material.client_certificate
    if certificate is None:
        return None
    import ssl
    context = ssl.create_default_context()
    context.load_cert_chain(
        certificate.certificate_path,
        keyfile=certificate.private_key_path,
        password=certificate.private_key_password,
    )
    return context

def _read_catalog_uri(
    uri: str,
    *,
    authentication: AIcAuthenticationService | None = None,
    authentication_profile_id: str | None = None,
    context: Mapping[str, object] | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    parsed = urlparse(uri)
    if parsed.scheme in {"", "file"}:
        path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(uri)
        return path.read_text(encoding="utf-8")
    if parsed.scheme not in {"http", "https"}:
        raise AIxPackageManagementError(f"unsupported catalog URI scheme {parsed.scheme!r}")
    material = authentication.material(
        authentication_profile_id, transport_kind="HTTP", endpoint=uri, context=dict(context or {})
    ) if authentication is not None else AIcAuthenticationMaterial()
    request = Request(uri, headers={"Accept": "application/json, application/yaml, text/yaml, text/plain", **dict(material.headers)}, method="GET")
    with urlopen(request, timeout=timeout_seconds, context=_ssl_context(material)) as response:
        return response.read().decode("utf-8")

def _render_validation_errors(errors) -> str:
    rendered = []
    for error in errors:
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
        rendered.append(f"{path}: {error.message}")
    return "; ".join(rendered)

def _resolve_relative_uri(base_uri: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme:
        return value
    base = urlparse(base_uri)
    if base.scheme in {"http", "https", "file"}:
        return urljoin(base_uri, value)
    return str((Path(base_uri).parent / value).resolve())

def _matches(query: AIcCatalogQuery, component: AIcCatalogComponent, release: AIcCatalogRelease) -> bool:
    if query.component_id is not None and component.component_id != query.component_id:
        return False
    if query.versions and release.version not in query.versions:
        return False
    if query.provides_capability_id is not None and not any(
        item.capability_id == query.provides_capability_id for item in release.provides
    ):
        return False
    if query.requires_capability_id is not None and not any(
        item.capability_id == query.requires_capability_id for item in release.requires
    ):
        return False
    if query.categories and not set(query.categories).issubset(component.categories):
        return False
    if query.tags and not set(query.tags).issubset(component.tags):
        return False
    if query.text:
        needle = query.text.casefold()
        haystack = " ".join(filter(None, (
            component.component_id,
            component.name.fallback if component.name else None,
            component.description.fallback if component.description else None,
            component.publisher.name.fallback if component.publisher and component.publisher.name else None,
            " ".join(component.categories),
            " ".join(component.tags),
        ))).casefold()
        if needle not in haystack:
            return False
    return True

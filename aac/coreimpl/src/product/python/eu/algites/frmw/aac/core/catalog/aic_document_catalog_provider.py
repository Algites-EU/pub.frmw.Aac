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

class AIcDocumentCatalogProvider(AIiCatalogProvider):
    def __init__(
        self,
        source_id: str,
        uri: str,
        *,
        authentication: AIcAuthenticationService | None = None,
        authentication_profile_id: str | None = None,
        timeout_seconds: float = 30.0,
        context: Mapping[str, object] | None = None,
    ) -> None:
        self.source_id = source_id
        self.uri = uri
        self.authentication = authentication
        self.authentication_profile_id = authentication_profile_id
        self.timeout_seconds = float(timeout_seconds)
        self.context = dict(context or {})

    def document(self) -> AIcCatalogDocument:
        text = _read_catalog_uri(
            self.uri,
            authentication=self.authentication,
            authentication_profile_id=self.authentication_profile_id,
            context=self.context,
            timeout_seconds=self.timeout_seconds,
        )
        return AIcCatalogDocumentLoader.load_text(text, source=self.uri, source_uri=self.uri)

    def query(self, query: AIcCatalogQuery) -> tuple[AIcCatalogEntry, ...]:
        return AIcStaticCatalogProvider(self.source_id, self.document()).query(query)

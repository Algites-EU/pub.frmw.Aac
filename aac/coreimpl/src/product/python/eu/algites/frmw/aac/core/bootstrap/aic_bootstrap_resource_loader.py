from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from pathlib import Path
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.authentication.api import (
    AIcAuthenticationParameter, AIcAuthenticationProfile, AIcSecretProviderRegistration, AIcSecretReference, AIcSecurityBootstrap,
)
from eu.algites.frmw.aac.core.configuration.api import (
    AInWorkspaceConfigurationProfilePolicy,
    AIcConfigurationBootstrap,
    AIcConfigurationProfile,
    AIcConfigurationProfileSourceRegistration,
    AIcConfigurationProviderBinding,
    AIcConfigurationProviderRegistration,
    AIcConfigurationScopeDefinition,
    AIcConfigurationScopeResolverRegistration,
)
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text

class AIcBootstrapResourceLoader:
    """Read trusted bootstrap/profile bytes from file or HTTP(S).

    Whether a supplied URI is trusted is decided by the product/installation. This class
    deliberately does not turn a user-supplied URI into an authority by itself.
    """

    def __init__(self, authentication=None, timeout_seconds: float = 10.0) -> None:
        self.authentication = authentication
        self.timeout_seconds = float(timeout_seconds)

    def read_text(self, uri: str, *, authentication_profile_id: str | None = None, context=None) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(uri)
        if parsed.scheme in {"", "file"}:
            path = Path(parsed.path if parsed.scheme == "file" else uri)
            return path.read_text(encoding="utf-8")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"unsupported bootstrap resource URI scheme {parsed.scheme!r}")
        from urllib.request import Request, urlopen
        headers = {"Accept": "application/yaml, text/yaml, text/plain, application/json"}
        ssl_context = None
        if self.authentication is not None:
            material = self.authentication.material(
                authentication_profile_id, transport_kind="HTTP", endpoint=uri, context=dict(context or {})
            )
            headers.update(material.headers)
            if material.client_certificate is not None:
                import ssl
                ssl_context = ssl.create_default_context()
                cert = material.client_certificate
                ssl_context.load_cert_chain(cert.certificate_path, cert.private_key_path, cert.private_key_password)
        with urlopen(Request(uri, headers=headers), timeout=self.timeout_seconds, context=ssl_context) as response:
            return response.read().decode("utf-8")

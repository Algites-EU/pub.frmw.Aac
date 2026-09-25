from __future__ import annotations

from .schema_resources import read_core_schema

import json
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from algites.frmw.aac.coreintf.authentication import (
    AIcAuthenticationParameter, AIcAuthenticationProfile, AIcSecretProviderRegistration, AIcSecretReference, AIcSecurityBootstrap,
)
from algites.frmw.aac.coreintf.configuration import (
    AInWorkspaceConfigurationProfilePolicy,
    AIcConfigurationBootstrap,
    AIcConfigurationProfile,
    AIcConfigurationProfileSourceRegistration,
    AIcConfigurationProviderBinding,
    AIcConfigurationProviderRegistration,
    AIcConfigurationScopeDefinition,
    AIcConfigurationScopeResolverRegistration,
)
from algites.frmw.aac.coreintf.errors import AIxDescriptorError
from algites.frmw.aac.coreintf.presentation import normalize_display_text


class AIcConfigurationBootstrapLoader:
    """Load the non-recursive fixed-schema configuration bootstrap contract.

    Products may package an equivalent fixed schema of their own; this generic AAC
    implementation ships schema version 1 as the baseline contract.
    """

    @staticmethod
    def load_file(path: str | Path) -> AIcConfigurationBootstrap:
        path = Path(path)
        return AIcConfigurationBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcConfigurationBootstrap:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in configuration bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: configuration bootstrap root must be a mapping")
        AIcConfigurationBootstrapLoader._validate(raw, source)
        try:
            return _parse_bootstrap(raw["configuration_bootstrap"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid configuration bootstrap: {exc}") from exc

    @staticmethod
    def _validate(raw: Mapping[str, Any], source: str) -> None:
        schema_text = read_core_schema("configuration-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered: list[str] = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: configuration bootstrap schema validation failed: " + "; ".join(rendered))


def _parse_bootstrap(raw: Mapping[str, Any]) -> AIcConfigurationBootstrap:
    profiles: list[AIcConfigurationProfile] = []
    for raw_profile in raw.get("configuration_profiles", ()):
        scopes: list[AIcConfigurationScopeDefinition] = []
        for raw_scope in raw_profile.get("configuration_scopes", ()):
            bindings = tuple(
                AIcConfigurationProviderBinding(str(item["id"]), int(item.get("priority", 0)))
                for item in raw_scope.get("configuration_providers", ())
            )
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(raw_scope["id"]),
                configuration_scope_type=str(raw_scope["type"]),
                configuration_scope_resolver_id=str(raw_scope["resolver"]),
                name=normalize_display_text(raw_scope.get("name")),
                description=normalize_display_text(raw_scope.get("description")),
                configuration_providers=bindings,
                policy_authority=bool(raw_scope.get("policy_authority", True)),
                mandatory=bool(raw_scope.get("mandatory", False)),
            ))
        profiles.append(AIcConfigurationProfile(str(raw_profile["id"]), int(raw_profile["version"]), tuple(scopes), name=normalize_display_text(raw_profile.get("name")), description=normalize_display_text(raw_profile.get("description"))))

    providers = tuple(
        AIcConfigurationProviderRegistration(
            id=str(item["id"]), type=str(item["type"]),
            name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
            settings=dict(item.get("settings", {})),
            authentication_profile_id=str(item["authentication_profile_id"]) if item.get("authentication_profile_id") is not None else None,
        )
        for item in raw.get("configuration_providers", ())
    )
    resolvers = tuple(
        AIcConfigurationScopeResolverRegistration(id=str(item["id"]), type=str(item["type"]), name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")), settings=dict(item.get("settings", {})))
        for item in raw.get("configuration_scope_resolvers", ())
    )
    return AIcConfigurationBootstrap(
        schema_version=int(raw["schema_version"]),
        default_configuration_profile_id=str(raw["default_configuration_profile"]),
        configuration_profiles=tuple(profiles),
        configuration_providers=providers,
        configuration_scope_resolvers=resolvers,
        configuration_profile_sources=tuple(
            AIcConfigurationProfileSourceRegistration(
                id=str(item["id"]), uri=str(item["uri"]),
                name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                authentication_profile_id=str(item["authentication_profile_id"]) if item.get("authentication_profile_id") is not None else None,
                required=bool(item.get("required", True)),
            ) for item in raw.get("configuration_profile_sources", ())
        ),
        workspace_configuration_profiles=AInWorkspaceConfigurationProfilePolicy(raw.get("workspace_configuration_profiles", "FORBIDDEN")),
        mandatory_configuration_scope_definition_ids=tuple(str(v) for v in raw.get("mandatory_configuration_scope_definition_ids", ())),
        metadata=dict(raw.get("metadata", {})),
    )




class AIcConfigurationProfileLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcConfigurationProfile:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in configuration profile {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: configuration profile root must be a mapping")
        schema_text = read_core_schema("configuration-profile_1.json")
        errors = sorted(Draft202012Validator(json.loads(schema_text)).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: configuration profile schema validation failed: " + "; ".join(rendered))
        body = raw["configuration_profile"]
        scopes = []
        for item in body.get("configuration_scopes", ()):
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(item["id"]), configuration_scope_type=str(item["type"]),
                configuration_scope_resolver_id=str(item["resolver"]),
                name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                configuration_providers=tuple(AIcConfigurationProviderBinding(str(v["id"]), int(v.get("priority", 0))) for v in item.get("configuration_providers", ())),
                policy_authority=bool(item.get("policy_authority", True)), mandatory=bool(item.get("mandatory", False)),
            ))
        return AIcConfigurationProfile(str(body["id"]), int(body["version"]), tuple(scopes), name=normalize_display_text(body.get("name")), description=normalize_display_text(body.get("description")))


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


class AIcSecurityBootstrapLoader:
    """Load the product-supplied fixed-schema security bootstrap.

    The source itself is an external trust boundary. This loader validates structure; a
    product/installation decides which source path/bytes are trusted before calling it.
    """

    @staticmethod
    def load_file(path: str | Path) -> AIcSecurityBootstrap:
        path = Path(path)
        return AIcSecurityBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcSecurityBootstrap:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in security bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: security bootstrap root must be a mapping")
        schema_text = read_core_schema("security-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: security bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["security_bootstrap"]
            secret_providers = tuple(AIcSecretProviderRegistration(
                id=str(item["id"]), type=str(item["type"]),
                name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                settings=dict(item.get("settings", {})), bootstrap_safe=bool(item.get("bootstrap_safe", False))
            ) for item in body.get("secret_providers", ()))
            profiles = []
            for item in body.get("authentication_profiles", ()):
                parameters = {}
                for key, value in dict(item.get("parameters", {})).items():
                    if isinstance(value, Mapping) and "secret_reference" in value:
                        ref = value["secret_reference"]
                        parameters[str(key)] = AIcAuthenticationParameter(secret_reference=AIcSecretReference(
                            str(ref["secret_provider_id"]), str(ref["key"]),
                            str(ref["version"]) if ref.get("version") is not None else None,
                            dict(ref.get("metadata", {})),
                        ))
                    else:
                        parameters[str(key)] = AIcAuthenticationParameter(value=value)
                profiles.append(AIcAuthenticationProfile(
                    id=str(item["id"]), mechanism=str(item["mechanism"]),
                    name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                    parameters=parameters, metadata=dict(item.get("metadata", {}))
                ))
            return AIcSecurityBootstrap(
                int(body["schema_version"]), secret_providers, tuple(profiles), dict(body.get("metadata", {}))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid security bootstrap: {exc}") from exc


class AIcEntitlementBootstrapLoader:
    @staticmethod
    def load_file(path: str | Path):
        path = Path(path)
        return AIcEntitlementBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>"):
        from algites.frmw.aac.coreintf.entitlement import (
            AIcEntitlementBootstrap, AIcEntitlementProfile, AIcEntitlementProviderBinding,
            AIcEntitlementProviderRegistration, AIcEntitlementLicensingScopeDefinition,
            AIcEntitlementLicensingScopeResolverRegistration, AIcTrustedEntitlementIssuerRule,
        )
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in entitlement bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: entitlement bootstrap root must be a mapping")
        body_probe = raw.get("entitlement_bootstrap")
        if not isinstance(body_probe, Mapping):
            raise AIxDescriptorError(f"{source}: entitlement bootstrap requires entitlement_bootstrap object")
        schema_version = int(body_probe.get("schema_version", 0))
        if schema_version != 1:
            raise AIxDescriptorError(f"{source}: unsupported entitlement bootstrap schema_version {schema_version}; expected 1")
        schema_text = read_core_schema("entitlement-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: entitlement bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["entitlement_bootstrap"]
            profiles = []
            for raw_profile in body.get("entitlement_profiles", ()):
                definitions = []
                raw_scope_definitions = raw_profile.get("licensing_scopes", ())
                for item in raw_scope_definitions:
                    definitions.append(AIcEntitlementLicensingScopeDefinition(
                        id=str(item["id"]),
                        licensing_scope_type=str(item["type"]),
                        licensing_scope_resolver_id=str(item["resolver"]),
                        name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                        entitlement_providers=tuple(AIcEntitlementProviderBinding(str(v["id"])) for v in item.get("entitlement_providers", ())),
                        mandatory=bool(item.get("mandatory", False)),
                    ))
                profiles.append(AIcEntitlementProfile(str(raw_profile["id"]), int(raw_profile["version"]), tuple(definitions), name=normalize_display_text(raw_profile.get("name")), description=normalize_display_text(raw_profile.get("description"))))
            return AIcEntitlementBootstrap(
                schema_version=int(body["schema_version"]),
                default_entitlement_profile_id=str(body["default_entitlement_profile"]),
                entitlement_profiles=tuple(profiles),
                entitlement_providers=tuple(AIcEntitlementProviderRegistration(id=str(v["id"]), type=str(v["type"]), name=normalize_display_text(v.get("name")), description=normalize_display_text(v.get("description")), settings=dict(v.get("settings", {}))) for v in body.get("entitlement_providers", ())),
                licensing_scope_resolvers=tuple(
                    AIcEntitlementLicensingScopeResolverRegistration(
                        id=str(v["id"]), type=str(v["type"]),
                        name=normalize_display_text(v.get("name")),
                        description=normalize_display_text(v.get("description")),
                        settings=dict(v.get("settings", {})),
                    )
                    for v in body.get("licensing_scope_resolvers", ())
                ),
                trusted_issuers=tuple(AIcTrustedEntitlementIssuerRule(
                    issuer_id=str(v["issuer_id"]), component_ids=tuple(str(x) for x in v.get("component_ids", ())),
                    evidence_types=tuple(str(x) for x in v.get("evidence_types", ())),
                    signer_identities=tuple(str(x) for x in v.get("signer_identities", ())),
                ) for v in body.get("trusted_issuers", ())),
                metadata=dict(body.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid entitlement bootstrap: {exc}") from exc


class AIcCatalogBootstrapLoader:
    """Load product/technology-scoped AAC catalog source registrations."""

    @staticmethod
    def load_file(path: str | Path):
        path = Path(path)
        return AIcCatalogBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>"):
        from algites.frmw.aac.coreintf.catalog import AIcCatalogBootstrap, AIcCatalogSourceRegistration
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in catalog bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: catalog bootstrap root must be a mapping")
        schema_text = read_core_schema("catalog-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: catalog bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["catalog_bootstrap"]
            return AIcCatalogBootstrap(
                schema_version=int(body["schema_version"]),
                product_id=str(body["product_id"]),
                technology_id=str(body["technology_id"]),
                sources=tuple(AIcCatalogSourceRegistration(
                    id=str(item["id"]),
                    type=str(item["type"]),
                    uri=str(item["uri"]),
                    authentication_profile_id=(str(item["authentication_profile_id"]) if item.get("authentication_profile_id") is not None else None),
                    priority=int(item.get("priority", 0)),
                    settings=dict(item.get("settings", {})),
                    name=normalize_display_text(item.get("name")),
                    description=normalize_display_text(item.get("description")),
                ) for item in body.get("sources", ())),
                metadata=dict(body.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid catalog bootstrap: {exc}") from exc

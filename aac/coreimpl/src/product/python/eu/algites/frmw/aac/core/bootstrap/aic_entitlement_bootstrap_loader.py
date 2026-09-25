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

class AIcEntitlementBootstrapLoader:
    @staticmethod
    def load_file(path: str | Path):
        path = Path(path)
        return AIcEntitlementBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>"):
        from eu.algites.frmw.aac.core.entitlement.api import (
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

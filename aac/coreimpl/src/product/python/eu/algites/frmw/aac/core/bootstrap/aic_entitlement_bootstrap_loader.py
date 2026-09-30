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
        body_probe = raw.get("EntitlementBootstrap")
        if not isinstance(body_probe, Mapping):
            raise AIxDescriptorError(f"{source}: entitlement bootstrap requires entitlement_bootstrap object")
        schema_version = int(body_probe.get("SchemaVersion", 0))
        if schema_version != 1:
            raise AIxDescriptorError(f"{source}: unsupported entitlement bootstrap schema_version {schema_version}; expected 1")
        schema_text = read_core_schema("entitlement-bootstrap_1.jsondef.schema.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: entitlement bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["EntitlementBootstrap"]
            profiles = []
            for raw_profile in body.get("EntitlementProfiles", ()):
                definitions = []
                raw_scope_definitions = raw_profile.get("LicensingScopes", ())
                for item in raw_scope_definitions:
                    definitions.append(AIcEntitlementLicensingScopeDefinition(
                        id=str(item["Id"]),
                        licensing_scope_type=str(item["Type"]),
                        licensing_scope_resolver_id=str(item["Resolver"]),
                        name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")),
                        entitlement_providers=tuple(AIcEntitlementProviderBinding(str(v["Id"])) for v in item.get("EntitlementProviders", ())),
                        mandatory=bool(item.get("Mandatory", False)),
                    ))
                profiles.append(AIcEntitlementProfile(str(raw_profile["Id"]), int(raw_profile["Version"]), tuple(definitions), name=normalize_display_text(raw_profile.get("Name")), description=normalize_display_text(raw_profile.get("Description"))))
            return AIcEntitlementBootstrap(
                schema_version=int(body["SchemaVersion"]),
                default_entitlement_profile_id=str(body["DefaultEntitlementProfile"]),
                entitlement_profiles=tuple(profiles),
                entitlement_providers=tuple(AIcEntitlementProviderRegistration(id=str(v["Id"]), type=str(v["Type"]), name=normalize_display_text(v.get("Name")), description=normalize_display_text(v.get("Description")), settings=dict(v.get("Settings", {}))) for v in body.get("EntitlementProviders", ())),
                licensing_scope_resolvers=tuple(
                    AIcEntitlementLicensingScopeResolverRegistration(
                        id=str(v["Id"]), type=str(v["Type"]),
                        name=normalize_display_text(v.get("Name")),
                        description=normalize_display_text(v.get("Description")),
                        settings=dict(v.get("Settings", {})),
                    )
                    for v in body.get("LicensingScopeResolvers", ())
                ),
                trusted_issuers=tuple(AIcTrustedEntitlementIssuerRule(
                    issuer_id=str(v["IssuerId"]), component_ids=tuple(str(x) for x in v.get("ComponentIds", ())),
                    evidence_types=tuple(str(x) for x in v.get("EvidenceTypes", ())),
                    signer_identities=tuple(str(x) for x in v.get("SignerIdentities", ())),
                ) for v in body.get("TrustedIssuers", ())),
                metadata=dict(body.get("Metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid entitlement bootstrap: {exc}") from exc

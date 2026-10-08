from __future__ import annotations

from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_1 import AIigEntitlementBootstrap_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_1 import AIigEntitlementBootstrapEntitlementBootstrap_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_entitlement_profiles_items_1 import AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_entitlement_profiles_items_licensing_scopes_items_1 import AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_entitlement_profiles_items_licensing_scopes_items_entitlement_providers_items_1 import AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItemsEntitlementProvidersItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_entitlement_providers_items_1 import AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_licensing_scope_resolvers_items_1 import AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1
from eu.algites.frmw.aac.core.entitlement.aiig_entitlement_bootstrap_entitlement_bootstrap_trusted_issuers_items_1 import AIigEntitlementBootstrapEntitlementBootstrapTrustedIssuersItems_1
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
        body_probe = raw.get(AIigEntitlementBootstrap_1.SCHEMA_FIELD_NAME__ENTITLEMENT_BOOTSTRAP)
        if not isinstance(body_probe, Mapping):
            raise AIxDescriptorError(f"{source}: entitlement bootstrap requires entitlement_bootstrap object")
        schema_version = int(body_probe.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION, 0))
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
            body = raw[AIigEntitlementBootstrap_1.SCHEMA_FIELD_NAME__ENTITLEMENT_BOOTSTRAP]
            profiles = []
            for raw_profile in body.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__ENTITLEMENT_PROFILES, ()):
                definitions = []
                raw_scope_definitions = raw_profile.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1.SCHEMA_FIELD_NAME__LICENSING_SCOPES, ())
                for item in raw_scope_definitions:
                    definitions.append(AIcEntitlementLicensingScopeDefinition(
                        id=str(item[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__ID]),
                        licensing_scope_type=str(item[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__TYPE]),
                        licensing_scope_resolver_id=str(item[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__RESOLVER]),
                        name=normalize_display_text(item.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                        entitlement_providers=tuple(AIcEntitlementProviderBinding(str(v[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItemsEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__ID])) for v in item.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__ENTITLEMENT_PROVIDERS, ())),
                        mandatory=bool(item.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItemsLicensingScopesItems_1.SCHEMA_FIELD_NAME__MANDATORY, False)),
                    ))
                profiles.append(AIcEntitlementProfile(str(raw_profile[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1.SCHEMA_FIELD_NAME__ID]), int(raw_profile[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1.SCHEMA_FIELD_NAME__VERSION]), tuple(definitions), name=normalize_display_text(raw_profile.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(raw_profile.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProfilesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION))))
            return AIcEntitlementBootstrap(
                schema_version=int(body[AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]),
                default_entitlement_profile_id=str(body[AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__DEFAULT_ENTITLEMENT_PROFILE]),
                entitlement_profiles=tuple(profiles),
                entitlement_providers=tuple(AIcEntitlementProviderRegistration(id=str(v[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__ID]), type=str(v[AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__TYPE]), name=normalize_display_text(v.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(v.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)), settings=dict(v.get(AIigEntitlementBootstrapEntitlementBootstrapEntitlementProvidersItems_1.SCHEMA_FIELD_NAME__SETTINGS, {}))) for v in body.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__ENTITLEMENT_PROVIDERS, ())),
                licensing_scope_resolvers=tuple(
                    AIcEntitlementLicensingScopeResolverRegistration(
                        id=str(v[AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1.SCHEMA_FIELD_NAME__ID]), type=str(v[AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1.SCHEMA_FIELD_NAME__TYPE]),
                        name=normalize_display_text(v.get(AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1.SCHEMA_FIELD_NAME__NAME)),
                        description=normalize_display_text(v.get(AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                        settings=dict(v.get(AIigEntitlementBootstrapEntitlementBootstrapLicensingScopeResolversItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})),
                    )
                    for v in body.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__LICENSING_SCOPE_RESOLVERS, ())
                ),
                trusted_issuers=tuple(AIcTrustedEntitlementIssuerRule(
                    issuer_id=str(v[AIigEntitlementBootstrapEntitlementBootstrapTrustedIssuersItems_1.SCHEMA_FIELD_NAME__ISSUER_ID]), component_ids=tuple(str(x) for x in v.get(AIigEntitlementBootstrapEntitlementBootstrapTrustedIssuersItems_1.SCHEMA_FIELD_NAME__COMPONENT_IDS, ())),
                    evidence_types=tuple(str(x) for x in v.get(AIigEntitlementBootstrapEntitlementBootstrapTrustedIssuersItems_1.SCHEMA_FIELD_NAME__EVIDENCE_TYPES, ())),
                    signer_identities=tuple(str(x) for x in v.get(AIigEntitlementBootstrapEntitlementBootstrapTrustedIssuersItems_1.SCHEMA_FIELD_NAME__SIGNER_IDENTITIES, ())),
                ) for v in body.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__TRUSTED_ISSUERS, ())),
                metadata=dict(body.get(AIigEntitlementBootstrapEntitlementBootstrap_1.SCHEMA_FIELD_NAME__METADATA, {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid entitlement bootstrap: {exc}") from exc

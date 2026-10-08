from __future__ import annotations

from eu.algites.frmw.aac.core.configuration.aiig_configuration_profile_1 import AIigConfigurationProfile_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_profile_configuration_profile_1 import AIigConfigurationProfileConfigurationProfile_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_profile_configuration_profile_configuration_scopes_items_1 import AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_profile_configuration_profile_configuration_scopes_items_configuration_providers_items_1 import AIigConfigurationProfileConfigurationProfileConfigurationScopesItemsConfigurationProvidersItems_1
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

class AIcConfigurationProfileLoader:
    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcConfigurationProfile:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in configuration profile {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: configuration profile root must be a mapping")
        schema_text = read_core_schema("configuration-profile_1.jsondef.schema.json")
        errors = sorted(Draft202012Validator(json.loads(schema_text)).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: configuration profile schema validation failed: " + "; ".join(rendered))
        body = raw[AIigConfigurationProfile_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROFILE]
        scopes = []
        for item in body.get(AIigConfigurationProfileConfigurationProfile_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCOPES, ()):
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(item[AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__ID]), configuration_scope_type=str(item[AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__TYPE]),
                configuration_scope_resolver_id=str(item[AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__RESOLVER]),
                name=normalize_display_text(item.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                configuration_providers=tuple(AIcConfigurationProviderBinding(str(v[AIigConfigurationProfileConfigurationProfileConfigurationScopesItemsConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__ID]), int(v.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItemsConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__PRIORITY, 0))) for v in item.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROVIDERS, ())),
                policy_authority=bool(item.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__POLICY_AUTHORITY, True)), mandatory=bool(item.get(AIigConfigurationProfileConfigurationProfileConfigurationScopesItems_1.SCHEMA_FIELD_NAME__MANDATORY, False)),
            ))
        return AIcConfigurationProfile(str(body[AIigConfigurationProfileConfigurationProfile_1.SCHEMA_FIELD_NAME__ID]), int(body[AIigConfigurationProfileConfigurationProfile_1.SCHEMA_FIELD_NAME__VERSION]), tuple(scopes), name=normalize_display_text(body.get(AIigConfigurationProfileConfigurationProfile_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(body.get(AIigConfigurationProfileConfigurationProfile_1.SCHEMA_FIELD_NAME__DESCRIPTION)))

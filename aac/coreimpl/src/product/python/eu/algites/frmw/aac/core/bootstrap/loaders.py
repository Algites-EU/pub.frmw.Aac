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

from .aic_configuration_bootstrap_loader import AIcConfigurationBootstrapLoader
from .aic_configuration_profile_loader import AIcConfigurationProfileLoader
from .aic_bootstrap_resource_loader import AIcBootstrapResourceLoader
from .aic_security_bootstrap_loader import AIcSecurityBootstrapLoader
from .aic_entitlement_bootstrap_loader import AIcEntitlementBootstrapLoader
from .aic_catalog_bootstrap_loader import AIcCatalogBootstrapLoader

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

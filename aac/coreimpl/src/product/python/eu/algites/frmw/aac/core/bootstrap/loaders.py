from __future__ import annotations

from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_1 import AIigConfigurationBootstrapConfigurationBootstrap_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_profiles_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_profiles_items_configuration_scopes_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_profiles_items_configuration_scopes_items_configuration_providers_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItemsConfigurationProvidersItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_profile_sources_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_providers_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_bootstrap_configuration_bootstrap_configuration_scope_resolvers_items_1 import AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1
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
    for raw_profile in raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROFILES, ()):
        scopes: list[AIcConfigurationScopeDefinition] = []
        for raw_scope in raw_profile.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCOPES, ()):
            bindings = tuple(
                AIcConfigurationProviderBinding(str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItemsConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__ID]), int(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItemsConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__PRIORITY, 0)))
                for item in raw_scope.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROVIDERS, ())
            )
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(raw_scope[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__ID]),
                configuration_scope_type=str(raw_scope[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__TYPE]),
                configuration_scope_resolver_id=str(raw_scope[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__RESOLVER]),
                name=normalize_display_text(raw_scope.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__NAME)),
                description=normalize_display_text(raw_scope.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                configuration_providers=bindings,
                policy_authority=bool(raw_scope.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__POLICY_AUTHORITY, True)),
                mandatory=bool(raw_scope.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItemsConfigurationScopesItems_1.SCHEMA_FIELD_NAME__MANDATORY, False)),
            ))
        profiles.append(AIcConfigurationProfile(str(raw_profile[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1.SCHEMA_FIELD_NAME__ID]), int(raw_profile[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1.SCHEMA_FIELD_NAME__VERSION]), tuple(scopes), name=normalize_display_text(raw_profile.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(raw_profile.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfilesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION))))

    providers = tuple(
        AIcConfigurationProviderRegistration(
            id=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__ID]), type=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__TYPE]),
            name=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
            settings=dict(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})),
            authentication_profile_id=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID]) if item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProvidersItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID) is not None else None,
        )
        for item in raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROVIDERS, ())
    )
    resolvers = tuple(
        AIcConfigurationScopeResolverRegistration(id=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1.SCHEMA_FIELD_NAME__ID]), type=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1.SCHEMA_FIELD_NAME__TYPE]), name=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)), settings=dict(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationScopeResolversItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})))
        for item in raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCOPE_RESOLVERS, ())
    )
    return AIcConfigurationBootstrap(
        schema_version=int(raw[AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]),
        default_configuration_profile_id=str(raw[AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__DEFAULT_CONFIGURATION_PROFILE]),
        configuration_profiles=tuple(profiles),
        configuration_providers=providers,
        configuration_scope_resolvers=resolvers,
        configuration_profile_sources=tuple(
            AIcConfigurationProfileSourceRegistration(
                id=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__ID]), uri=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__URI]),
                name=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                authentication_profile_id=str(item[AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID]) if item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID) is not None else None,
                required=bool(item.get(AIigConfigurationBootstrapConfigurationBootstrapConfigurationProfileSourcesItems_1.SCHEMA_FIELD_NAME__REQUIRED, True)),
            ) for item in raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__CONFIGURATION_PROFILE_SOURCES, ())
        ),
        workspace_configuration_profiles=AInWorkspaceConfigurationProfilePolicy(raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__WORKSPACE_CONFIGURATION_PROFILES, "forbidden")),
        mandatory_configuration_scope_definition_ids=tuple(str(v) for v in raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__MANDATORY_CONFIGURATION_SCOPE_DEFINITION_IDS, ())),
        metadata=dict(raw.get(AIigConfigurationBootstrapConfigurationBootstrap_1.SCHEMA_FIELD_NAME__METADATA, {})),
    )

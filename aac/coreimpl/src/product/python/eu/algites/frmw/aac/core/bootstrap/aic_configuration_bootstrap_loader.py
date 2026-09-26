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

def _parse_bootstrap(raw: Mapping[str, Any]) -> AIcConfigurationBootstrap:
    profiles: list[AIcConfigurationProfile] = []
    for raw_profile in raw.get("ConfigurationProfiles", ()):
        scopes: list[AIcConfigurationScopeDefinition] = []
        for raw_scope in raw_profile.get("ConfigurationScopes", ()):
            bindings = tuple(
                AIcConfigurationProviderBinding(str(item["Id"]), int(item.get("Priority", 0)))
                for item in raw_scope.get("ConfigurationProviders", ())
            )
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(raw_scope["Id"]),
                configuration_scope_type=str(raw_scope["Type"]),
                configuration_scope_resolver_id=str(raw_scope["Resolver"]),
                name=normalize_display_text(raw_scope.get("Name")),
                description=normalize_display_text(raw_scope.get("Description")),
                configuration_providers=bindings,
                policy_authority=bool(raw_scope.get("PolicyAuthority", True)),
                mandatory=bool(raw_scope.get("Mandatory", False)),
            ))
        profiles.append(AIcConfigurationProfile(str(raw_profile["Id"]), int(raw_profile["Version"]), tuple(scopes), name=normalize_display_text(raw_profile.get("Name")), description=normalize_display_text(raw_profile.get("Description"))))

    providers = tuple(
        AIcConfigurationProviderRegistration(
            id=str(item["Id"]), type=str(item["Type"]),
            name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")),
            settings=dict(item.get("Settings", {})),
            authentication_profile_id=str(item["AuthenticationProfileId"]) if item.get("AuthenticationProfileId") is not None else None,
        )
        for item in raw.get("ConfigurationProviders", ())
    )
    resolvers = tuple(
        AIcConfigurationScopeResolverRegistration(id=str(item["Id"]), type=str(item["Type"]), name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")), settings=dict(item.get("Settings", {})))
        for item in raw.get("ConfigurationScopeResolvers", ())
    )
    return AIcConfigurationBootstrap(
        schema_version=int(raw["SchemaVersion"]),
        default_configuration_profile_id=str(raw["DefaultConfigurationProfile"]),
        configuration_profiles=tuple(profiles),
        configuration_providers=providers,
        configuration_scope_resolvers=resolvers,
        configuration_profile_sources=tuple(
            AIcConfigurationProfileSourceRegistration(
                id=str(item["Id"]), uri=str(item["Uri"]),
                name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")),
                authentication_profile_id=str(item["AuthenticationProfileId"]) if item.get("AuthenticationProfileId") is not None else None,
                required=bool(item.get("Required", True)),
            ) for item in raw.get("ConfigurationProfileSources", ())
        ),
        workspace_configuration_profiles=AInWorkspaceConfigurationProfilePolicy(raw.get("WorkspaceConfigurationProfiles", "forbidden")),
        mandatory_configuration_scope_definition_ids=tuple(str(v) for v in raw.get("MandatoryConfigurationScopeDefinitionIds", ())),
        metadata=dict(raw.get("Metadata", {})),
    )

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
            return _parse_bootstrap(raw["ConfigurationBootstrap"])
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

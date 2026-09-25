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

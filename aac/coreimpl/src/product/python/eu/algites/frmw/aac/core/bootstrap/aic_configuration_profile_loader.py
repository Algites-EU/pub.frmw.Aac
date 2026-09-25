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

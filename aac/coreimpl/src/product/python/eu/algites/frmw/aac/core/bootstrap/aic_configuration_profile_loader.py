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
        schema_text = read_core_schema("configuration-profile_1.jsondef.schema.json")
        errors = sorted(Draft202012Validator(json.loads(schema_text)).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: configuration profile schema validation failed: " + "; ".join(rendered))
        body = raw["ConfigurationProfile"]
        scopes = []
        for item in body.get("ConfigurationScopes", ()):
            scopes.append(AIcConfigurationScopeDefinition(
                id=str(item["Id"]), configuration_scope_type=str(item["Type"]),
                configuration_scope_resolver_id=str(item["Resolver"]),
                name=normalize_display_text(item.get("Name")), description=normalize_display_text(item.get("Description")),
                configuration_providers=tuple(AIcConfigurationProviderBinding(str(v["Id"]), int(v.get("Priority", 0))) for v in item.get("ConfigurationProviders", ())),
                policy_authority=bool(item.get("PolicyAuthority", True)), mandatory=bool(item.get("Mandatory", False)),
            ))
        return AIcConfigurationProfile(str(body["Id"]), int(body["Version"]), tuple(scopes), name=normalize_display_text(body.get("Name")), description=normalize_display_text(body.get("Description")))

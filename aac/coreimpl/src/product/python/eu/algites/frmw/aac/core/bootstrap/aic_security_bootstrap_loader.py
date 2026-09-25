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

class AIcSecurityBootstrapLoader:
    """Load the product-supplied fixed-schema security bootstrap.

    The source itself is an external trust boundary. This loader validates structure; a
    product/installation decides which source path/bytes are trusted before calling it.
    """

    @staticmethod
    def load_file(path: str | Path) -> AIcSecurityBootstrap:
        path = Path(path)
        return AIcSecurityBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcSecurityBootstrap:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in security bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: security bootstrap root must be a mapping")
        schema_text = read_core_schema("security-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: security bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["security_bootstrap"]
            secret_providers = tuple(AIcSecretProviderRegistration(
                id=str(item["id"]), type=str(item["type"]),
                name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                settings=dict(item.get("settings", {})), bootstrap_safe=bool(item.get("bootstrap_safe", False))
            ) for item in body.get("secret_providers", ()))
            profiles = []
            for item in body.get("authentication_profiles", ()):
                parameters = {}
                for key, value in dict(item.get("parameters", {})).items():
                    if isinstance(value, Mapping) and "secret_reference" in value:
                        ref = value["secret_reference"]
                        parameters[str(key)] = AIcAuthenticationParameter(secret_reference=AIcSecretReference(
                            str(ref["secret_provider_id"]), str(ref["key"]),
                            str(ref["version"]) if ref.get("version") is not None else None,
                            dict(ref.get("metadata", {})),
                        ))
                    else:
                        parameters[str(key)] = AIcAuthenticationParameter(value=value)
                profiles.append(AIcAuthenticationProfile(
                    id=str(item["id"]), mechanism=str(item["mechanism"]),
                    name=normalize_display_text(item.get("name")), description=normalize_display_text(item.get("description")),
                    parameters=parameters, metadata=dict(item.get("metadata", {}))
                ))
            return AIcSecurityBootstrap(
                int(body["schema_version"]), secret_providers, tuple(profiles), dict(body.get("metadata", {}))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid security bootstrap: {exc}") from exc

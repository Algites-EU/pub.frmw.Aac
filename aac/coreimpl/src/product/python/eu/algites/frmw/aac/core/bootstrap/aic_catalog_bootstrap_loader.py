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

class AIcCatalogBootstrapLoader:
    """Load product/technology-scoped AAC catalog source registrations."""

    @staticmethod
    def load_file(path: str | Path):
        path = Path(path)
        return AIcCatalogBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>"):
        from eu.algites.frmw.aac.core.catalog.api import AIcCatalogBootstrap, AIcCatalogSourceRegistration
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in catalog bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: catalog bootstrap root must be a mapping")
        schema_text = read_core_schema("catalog-bootstrap_1.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: catalog bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw["catalog_bootstrap"]
            return AIcCatalogBootstrap(
                schema_version=int(body["schema_version"]),
                product_id=str(body["product_id"]),
                technology_id=str(body["technology_id"]),
                sources=tuple(AIcCatalogSourceRegistration(
                    id=str(item["id"]),
                    type=str(item["type"]),
                    uri=str(item["uri"]),
                    authentication_profile_id=(str(item["authentication_profile_id"]) if item.get("authentication_profile_id") is not None else None),
                    priority=int(item.get("priority", 0)),
                    settings=dict(item.get("settings", {})),
                    name=normalize_display_text(item.get("name")),
                    description=normalize_display_text(item.get("description")),
                ) for item in body.get("sources", ())),
                metadata=dict(body.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid catalog bootstrap: {exc}") from exc

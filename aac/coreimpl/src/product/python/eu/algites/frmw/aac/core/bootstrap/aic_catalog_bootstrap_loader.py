from __future__ import annotations

from eu.algites.frmw.aac.core.catalog.aiig_catalog_bootstrap_1 import AIigCatalogBootstrap_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_bootstrap_catalog_bootstrap_1 import AIigCatalogBootstrapCatalogBootstrap_1
from eu.algites.frmw.aac.core.catalog.aiig_catalog_bootstrap_catalog_bootstrap_sources_items_1 import AIigCatalogBootstrapCatalogBootstrapSourcesItems_1
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
        schema_text = read_core_schema("catalog-bootstrap_1.jsondef.schema.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: catalog bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw[AIigCatalogBootstrap_1.SCHEMA_FIELD_NAME__CATALOG_BOOTSTRAP]
            return AIcCatalogBootstrap(
                schema_version=int(body[AIigCatalogBootstrapCatalogBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]),
                product_id=str(body[AIigCatalogBootstrapCatalogBootstrap_1.SCHEMA_FIELD_NAME__PRODUCT_ID]),
                technology_id=str(body[AIigCatalogBootstrapCatalogBootstrap_1.SCHEMA_FIELD_NAME__TECHNOLOGY_ID]),
                sources=tuple(AIcCatalogSourceRegistration(
                    id=str(item[AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__ID]),
                    type=str(item[AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__TYPE]),
                    uri=str(item[AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__URI]),
                    authentication_profile_id=(str(item[AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID]) if item.get(AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILE_ID) is not None else None),
                    priority=int(item.get(AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__PRIORITY, 0)),
                    settings=dict(item.get(AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})),
                    name=normalize_display_text(item.get(AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__NAME)),
                    description=normalize_display_text(item.get(AIigCatalogBootstrapCatalogBootstrapSourcesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                ) for item in body.get(AIigCatalogBootstrapCatalogBootstrap_1.SCHEMA_FIELD_NAME__SOURCES, ())),
                metadata=dict(body.get(AIigCatalogBootstrapCatalogBootstrap_1.SCHEMA_FIELD_NAME__METADATA, {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid catalog bootstrap: {exc}") from exc

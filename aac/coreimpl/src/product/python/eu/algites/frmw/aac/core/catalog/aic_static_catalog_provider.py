from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.authentication.api import AIcAuthenticationMaterial
from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogArtifact,
    AIcCatalogArtifactLocator,
    AIcCatalogCapabilityOffer,
    AIcCatalogCapabilityRequirement,
    AIcCatalogComponent,
    AIcCatalogDocument,
    AIcCatalogEntry,
    AIcCatalogIcon,
    AIcCatalogPublisher,
    AIcCatalogQuery,
    AIcCatalogRelease,
    AIcCatalogPersistentSchema,
    AInCatalogPersistentSchemaKind,
    AIiCatalogProvider,
)
from eu.algites.frmw.aac.core.capability.api import AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxPackageManagementError
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.packages.api import AIcPackageSidecar
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService

def _matches(query: AIcCatalogQuery, component: AIcCatalogComponent, release: AIcCatalogRelease) -> bool:
    if query.component_id is not None and component.component_id != query.component_id:
        return False
    if query.versions and release.version not in query.versions:
        return False
    if query.provides_capability_id is not None and not any(
        item.capability_id == query.provides_capability_id for item in release.provides
    ):
        return False
    if query.requires_capability_id is not None and not any(
        item.capability_id == query.requires_capability_id for item in release.requires
    ):
        return False
    if query.categories and not set(query.categories).issubset(component.categories):
        return False
    if query.tags and not set(query.tags).issubset(component.tags):
        return False
    if query.text:
        needle = query.text.casefold()
        haystack = " ".join(filter(None, (
            component.component_id,
            component.name.fallback if component.name else None,
            component.description.fallback if component.description else None,
            component.publisher.name.fallback if component.publisher and component.publisher.name else None,
            " ".join(component.categories),
            " ".join(component.tags),
        ))).casefold()
        if needle not in haystack:
            return False
    return True

class AIcStaticCatalogProvider(AIiCatalogProvider):
    def __init__(self, source_id: str, document: AIcCatalogDocument) -> None:
        self.source_id = source_id
        self.document = document

    def query(self, query: AIcCatalogQuery) -> tuple[AIcCatalogEntry, ...]:
        if query.product_id != self.document.product_id or query.technology_id != self.document.technology_id:
            return ()
        result = [
            AIcCatalogEntry(self.source_id, self.document.product_id, self.document.technology_id, component, release)
            for component in self.document.components
            for release in component.releases
            if _matches(query, component, release)
        ]
        result.sort(key=lambda item: (item.component_id, -item.component_version, item.source_id))
        return tuple(result)

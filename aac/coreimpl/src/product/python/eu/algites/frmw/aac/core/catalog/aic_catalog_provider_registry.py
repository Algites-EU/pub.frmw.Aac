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

class AIcCatalogProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, tuple[int, AIiCatalogProvider]] = {}

    def register(self, source_id: str, provider: AIiCatalogProvider, *, priority: int = 0) -> None:
        if not source_id:
            raise ValueError("catalog source id must not be empty")
        self._providers[source_id] = (int(priority), provider)

    def get(self, source_id: str) -> AIiCatalogProvider:
        return self._providers[source_id][1]

    def query(self, query: AIcCatalogQuery) -> tuple[AIcCatalogEntry, ...]:
        result: list[tuple[int, AIcCatalogEntry]] = []
        for priority, provider in self._providers.values():
            result.extend((priority, entry) for entry in provider.query(query))
        result.sort(key=lambda item: (item[1].component_id, -item[1].component_version, -item[0], item[1].source_id))
        return tuple(entry for _, entry in result)

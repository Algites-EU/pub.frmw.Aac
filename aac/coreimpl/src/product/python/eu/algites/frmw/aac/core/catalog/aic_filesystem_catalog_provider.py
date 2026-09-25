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

from .aic_document_catalog_provider import AIcDocumentCatalogProvider

class AIcFilesystemCatalogProvider(AIcDocumentCatalogProvider):
    pass

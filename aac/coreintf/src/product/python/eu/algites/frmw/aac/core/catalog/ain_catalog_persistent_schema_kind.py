from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

class AInCatalogPersistentSchemaKind(str, Enum):
    COMPONENT_CONFIGURATION = "COMPONENT_CONFIGURATION"
    PROVIDER_CONFIGURATION = "PROVIDER_CONFIGURATION"
    DATA_ENTITY = "DATA_ENTITY"

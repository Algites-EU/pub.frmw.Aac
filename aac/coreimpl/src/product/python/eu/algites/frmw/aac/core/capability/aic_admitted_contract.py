from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping
import yaml
from eu.algites.frmw.aac.core.capability.api import (
    AIcAuthorizationPermissionDescriptor,
    AIcCapabilityContract,
    AInCapabilityOperationInteractionKind,
    AIcCapabilityOperationInteraction,
    AIcSchemaRef,
    AIcCapabilityGroup,
    AIcCapabilityOperation,
    AIcCapabilityRef,
    AIcOperationAuthorizationRequirement,
)
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.implementation.errors import AIxContractAdmissionError, AIxContractConflictError, AIxContractNegotiationError
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

@dataclass(frozen=True, slots=True)
class AIcAdmittedContract:
    contract: AIcCapabilityContract
    source: str
    fingerprint: str

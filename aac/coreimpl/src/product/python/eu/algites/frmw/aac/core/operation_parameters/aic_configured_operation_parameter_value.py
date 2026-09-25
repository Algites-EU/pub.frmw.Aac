from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Mapping
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcOperationParameterDefinitionDescriptor,
    AIcProviderDefinitionDescriptor,
)
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore

@dataclass(frozen=True, slots=True)
class AIcConfiguredOperationParameterValue:
    value: object
    written_by_component_version: int

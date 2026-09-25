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

from .aic_configured_operation_parameter_value import AIcConfiguredOperationParameterValue
from .aic_operation_parameter_configuration_store import AIcOperationParameterConfigurationStore
from .aic_operation_parameter_resolver import AIcOperationParameterResolver

_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE = "aac.operation-parameter-configuration"

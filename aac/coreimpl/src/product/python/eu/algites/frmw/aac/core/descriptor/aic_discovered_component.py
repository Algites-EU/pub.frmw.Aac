from __future__ import annotations
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from zipfile import ZipFile, BadZipFile, is_zipfile
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcPermissionDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcCapabilityEntitlementDescriptor,
    AIcDataEntityRequirementDescriptor,
    AIcDataEntitySupportDescriptor,
    AIcPersistedSchemaDescriptor,
    AIcSchemaMigrationStepDescriptor,
    AInDataEntityAccess,
    AIcInitialProviderInstanceDescriptor,
    AIcLifecycleHooksDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderImplementationClassDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
    AIcCapabilityProviderOperationDescriptor,
    AIcCapabilityProviderOperationInteractionDescriptor,
    AIcOperationParameterDefinitionDescriptor,
    AIcOperationParameterEnumValueDescriptor,
)
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.instances.api import AInProviderAccessMode
from eu.algites.frmw.aac.core.interaction_types import AInStateResultDeliveryMode
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.readiness.api import AInReadinessRequirementSource, AInReadinessState, AIcReadinessRequirementDescriptor

@dataclass(frozen=True, slots=True)
class AIcDiscoveredComponent:
    descriptor: AIcComponentDescriptor
    package: str | None
    source: str
    artifact_path: str | None = None

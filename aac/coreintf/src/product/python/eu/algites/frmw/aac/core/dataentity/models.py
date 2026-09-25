from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

from .ain_data_entity_state import AInDataEntityState
from .aic_data_entity_identity import AIcDataEntityIdentity
from .aic_data_entity_envelope import AIcDataEntityEnvelope
from .aic_data_entity_migration_request import AIcDataEntityMigrationRequest
from .aic_data_entity_migration_result import AIcDataEntityMigrationResult
from .aic_data_entity_reference_definition import AIcDataEntityReferenceDefinition
from .aic_typed_data_entity_envelope import AIcTypedDataEntityEnvelope

T = TypeVar("T")

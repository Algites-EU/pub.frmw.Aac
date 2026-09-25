from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_change import AIcConfigurationChange
from .aic_configuration_target import AIcConfigurationTarget

@dataclass(frozen=True, slots=True)
class AIcConfigurationChangeSet:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_target: AIcConfigurationTarget
    changes: tuple[AIcConfigurationChange, ...]
    expected_record_revision: str | int | None = None
    configuration_schema_id: str | None = None
    configuration_schema_version: int | None = None
    written_by_component_version: int | None = None
    actor_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")
        if not self.changes:
            raise ValueError("configuration change-set must contain at least one change")
        schema_fields = (self.configuration_schema_id, self.configuration_schema_version, self.written_by_component_version)
        if any(value is not None for value in schema_fields) and not all(value is not None for value in schema_fields):
            raise ValueError("configuration schema id/version and written_by_component_version must be supplied together")
        if self.configuration_schema_version is not None and self.configuration_schema_version < 1:
            raise ValueError("configuration_schema_version must be >= 1")
        if self.written_by_component_version is not None and self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")
        identities = [(c.property_id, c.operation.value) for c in self.changes]
        if len(identities) != len(set(identities)):
            raise ValueError("configuration change-set contains duplicate property/operation changes")

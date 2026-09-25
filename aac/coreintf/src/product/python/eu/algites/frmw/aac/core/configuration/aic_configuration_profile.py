from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_scope_definition import AIcConfigurationScopeDefinition

@dataclass(frozen=True, slots=True)
class AIcConfigurationProfile:
    id: str
    version: int
    configuration_scopes: tuple[AIcConfigurationScopeDefinition, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("configuration profile id must not be empty")
        if self.version < 1:
            raise ValueError("configuration profile version must be >= 1")
        if not self.configuration_scopes:
            raise ValueError("configuration profile must define at least one configuration-scope")
        definition_ids = [item.id for item in self.configuration_scopes]
        if len(definition_ids) != len(set(definition_ids)):
            raise ValueError("configuration-scope definition ids must be unique inside a profile")

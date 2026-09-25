from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_provider_binding import AIcConfigurationProviderBinding

@dataclass(frozen=True, slots=True)
class AIcConfigurationScopeDefinition:
    id: str
    configuration_scope_type: str
    configuration_scope_resolver_id: str
    configuration_providers: tuple[AIcConfigurationProviderBinding, ...] = ()
    policy_authority: bool = True
    mandatory: bool = False
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("configuration-scope definition id must not be empty")
        if not self.configuration_scope_type:
            raise ValueError("configuration_scope_type must not be empty")
        if not self.configuration_scope_resolver_id:
            raise ValueError("configuration_scope_resolver_id must not be empty")
        provider_ids = [item.configuration_provider_id for item in self.configuration_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("configuration-provider bindings must be unique inside one configuration-scope definition")

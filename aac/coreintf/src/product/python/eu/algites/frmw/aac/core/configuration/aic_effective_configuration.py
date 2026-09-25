from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_target import AIcConfigurationTarget
from .aic_effective_configuration_value import AIcEffectiveConfigurationValue
from .aic_resolved_configuration_scope import AIcResolvedConfigurationScope
from .ain_configuration_value_source_kind import AInConfigurationValueSourceKind

@dataclass(frozen=True, slots=True)
class AIcEffectiveConfiguration:
    configuration_target: AIcConfigurationTarget
    values: Mapping[str, AIcEffectiveConfigurationValue]
    configuration_scopes: tuple[AIcResolvedConfigurationScope, ...]
    diagnostics: tuple[str, ...] = ()

    def plain_values(self) -> dict[str, object | None]:
        return {key: value.value for key, value in self.values.items() if value.source_kind is not AInConfigurationValueSourceKind.UNDEFINED}

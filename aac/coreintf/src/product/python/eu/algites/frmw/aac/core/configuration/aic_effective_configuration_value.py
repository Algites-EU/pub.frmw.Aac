from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_contribution_provenance import AIcConfigurationContributionProvenance
from .aic_effective_configuration_policy import AIcEffectiveConfigurationPolicy
from .ain_configuration_value_source_kind import AInConfigurationValueSourceKind

@dataclass(frozen=True, slots=True)
class AIcEffectiveConfigurationValue:
    property_id: str
    value: object | None
    source_kind: AInConfigurationValueSourceKind
    provenance: AIcConfigurationContributionProvenance | None
    effective_policy: AIcEffectiveConfigurationPolicy
    shadowed_provenance: tuple[AIcConfigurationContributionProvenance, ...] = ()

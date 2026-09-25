from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_contribution_provenance import AIcConfigurationContributionProvenance
from .aic_configuration_policy import AIcConfigurationPolicy

@dataclass(frozen=True, slots=True)
class AIcEffectiveConfigurationPolicy:
    lock: object | None = None
    has_lock: bool = False
    minimum: object | None = None
    maximum: object | None = None
    in_set: tuple[object, ...] | None = None
    not_in_set: tuple[object, ...] = ()
    provenance: tuple[tuple[AIcConfigurationPolicy, AIcConfigurationContributionProvenance], ...] = ()

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .ain_configuration_policy_mode import AInConfigurationPolicyMode

@dataclass(frozen=True, slots=True)
class AIcConfigurationPolicy:
    mode: AInConfigurationPolicyMode
    value: object

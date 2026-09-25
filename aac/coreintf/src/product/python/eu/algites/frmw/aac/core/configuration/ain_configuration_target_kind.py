from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInConfigurationTargetKind(str, Enum):
    COMPONENT = "COMPONENT"
    PROVIDER_INSTANCE = "PROVIDER_INSTANCE"

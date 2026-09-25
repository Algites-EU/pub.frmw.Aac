from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInWorkspaceConfigurationProfilePolicy(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    ALLOWED = "ALLOWED"
    ALLOWED_IF_SIGNED = "ALLOWED_IF_SIGNED"

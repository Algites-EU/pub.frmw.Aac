from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInConfigurationValueSourceKind(str, Enum):
    EXPLICIT = "EXPLICIT"
    POLICY_LOCK = "POLICY_LOCK"
    POLICY_DEFAULT = "POLICY_DEFAULT"
    SCHEMA_DEFAULT = "SCHEMA_DEFAULT"
    UNDEFINED = "UNDEFINED"

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInConfigurationPolicyMode(str, Enum):
    LOCK = "LOCK"
    MIN = "MIN"
    MAX = "MAX"
    IN_SET = "IN_SET"
    NOT_IN_SET = "NOT_IN_SET"
    DEFAULT = "DEFAULT"

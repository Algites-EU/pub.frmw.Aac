from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInConfigurationProviderCapability(str, Enum):
    READ = "READ"
    WRITE_VALUE = "WRITE_VALUE"
    DELETE_VALUE = "DELETE_VALUE"
    WRITE_POLICY = "WRITE_POLICY"
    DELETE_POLICY = "DELETE_POLICY"
    ATOMIC_CHANGE_SET = "ATOMIC_CHANGE_SET"

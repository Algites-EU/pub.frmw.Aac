from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

class AInConfigurationMutationOperation(str, Enum):
    SET_VALUE = "SET_VALUE"
    DELETE_VALUE = "DELETE_VALUE"
    SET_POLICY = "SET_POLICY"
    DELETE_POLICY = "DELETE_POLICY"

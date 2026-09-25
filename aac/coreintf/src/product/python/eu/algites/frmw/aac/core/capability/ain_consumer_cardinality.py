from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

class AInConsumerCardinality(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"

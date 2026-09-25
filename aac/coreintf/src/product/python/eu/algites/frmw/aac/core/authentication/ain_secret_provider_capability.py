from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

class AInSecretProviderCapability(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"

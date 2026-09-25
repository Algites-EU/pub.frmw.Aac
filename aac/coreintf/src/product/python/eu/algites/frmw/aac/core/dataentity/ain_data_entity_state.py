from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

class AInDataEntityState(str, Enum):
    ACTIVE = "ACTIVE"
    TOMBSTONE = "TOMBSTONE"

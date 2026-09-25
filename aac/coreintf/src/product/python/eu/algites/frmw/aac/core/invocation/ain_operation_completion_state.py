from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar

class AInOperationCompletionState(str, Enum):
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

class AInRecordRevisionKind(str, Enum):
    """Schema/persistence-contract declaration for record revision representation."""

    MONOTONIC_INTEGER = "MONOTONIC_INTEGER"
    OPAQUE_STRING = "OPAQUE_STRING"

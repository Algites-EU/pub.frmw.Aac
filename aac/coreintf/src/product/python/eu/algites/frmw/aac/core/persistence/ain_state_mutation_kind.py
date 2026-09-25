from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

class AInStateMutationKind(str, Enum):
    PUT = "PUT"
    DELETE = "DELETE"
